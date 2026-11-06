"""Offline catalog and validated, transactional Hunspell pack installation."""
import hashlib
import json
import importlib.util
import os
import re
import shutil
import urllib.request
import uuid
import zipfile
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name("dictionary_catalog.json").read_text(encoding="utf-8"))
PACKS = CATALOG["packs"]
MAX_AFF = 8 * 1024 * 1024
MAX_DIC = 64 * 1024 * 1024


def language_code(code):
    if not isinstance(code, str) or not re.fullmatch(r"[a-z]{2,3}(?:_[A-Za-z0-9]{2,8}){0,2}", code):
        raise ValueError("Invalid dictionary language code")
    return code


def installed(root):
    folder = Path(root) / "dictionaries"
    return {p.name for p in folder.glob("*") if p.is_dir() and not p.is_symlink()
            and re.fullmatch(r"[a-z]{2,3}(?:_[A-Za-z0-9]{2,8}){0,2}", p.name)
            and (p / "dictionary.aff").is_file() and (p / "dictionary.dic").is_file()}


def resolve(root, language, present=None):
    if not language or language in {"off", "auto"}:
        return "off"
    language = language_code(language.replace("-", "_"))
    present = (installed(root) if present is None else present) | {"en"}
    if language in present or "_" in language:
        return language
    variants = sorted(code for code in present if code.startswith(language + "_"))
    if language == "pt" and "pt_PT" in variants:
        return "pt_PT"
    return variants[0] if variants else {"pt": "pt_PT", "no": "nb"}.get(language, language)


def load_dictionary(root, code):
    language_code(code)
    base = Path(root) / "dictionaries" / code / "dictionary"
    if base.with_suffix(".aff").exists() or base.with_suffix(".dic").exists():
        if not base.with_suffix(".aff").is_file() or not base.with_suffix(".dic").is_file():
            raise ValueError("Incomplete dictionary pair")
        return open_dictionary(base)
    if code == "en":
        spec = importlib.util.find_spec("spylls")
        folder = Path(next(iter(spec.submodule_search_locations))) / "hunspell" / "data" / "en"
        return open_dictionary(folder / "en_US")
    raise FileNotFoundError(code)


def open_dictionary(base):
    if os.name == "nt":
        from .hunspell_native import NativeDictionary
        return NativeDictionary(base)
    from spylls.hunspell import Dictionary
    dictionary = Dictionary.from_files(str(base))
    dictionary.entry_count = len(dictionary.dic.words)
    return dictionary


def validate(staging):
    staging = Path(staging)
    aff, dic = staging / "dictionary.aff", staging / "dictionary.dic"
    if not 0 < aff.stat().st_size <= MAX_AFF or not 0 < dic.stat().st_size <= MAX_DIC:
        raise ValueError("Dictionary file size is invalid")
    raw = aff.read_bytes()
    if not re.search(rb"(?m)^SET\s+\S+", raw.lstrip(b"\xef\xbb\xbf")):
        raise ValueError("Hunspell SET encoding is missing")
    dictionary = open_dictionary(staging / "dictionary")
    count = dictionary.entry_count
    del dictionary
    if not count:
        raise ValueError("Dictionary has no entries")
    return count


def publish(staging, root, code):
    code = language_code(code)
    folder = Path(root) / "dictionaries"
    return publish_directory(staging, folder, code)


def publish_directory(staging, folder, name):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if target.is_symlink() or target.resolve().parent != folder.resolve():
        raise ValueError("Unsafe dictionary destination")
    backup = folder / (".backup-" + name + "-" + uuid.uuid4().hex)
    if target.exists():
        target.rename(backup)
    try:
        Path(staging).rename(target)
    except OSError:
        if backup.exists():
            backup.rename(target)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    return target


def download_pack(args, output):
    code = language_code(args.get("code", "pl"))
    pack = PACKS[code]
    staging = Path(args["work"])
    total = sum(f["size"] for f in pack["files"])
    if shutil.disk_usage(staging).free < total * 2 + 20_000_000:
        raise OSError("disk_space")
    done = 0
    for i, item in enumerate(pack["files"]):
        path, size = item["path"], item["size"]
        name = ("dictionary" + Path(path).suffix) if i < 2 else f"NOTICE-{i:02}-{Path(path).name}"
        digest = hashlib.sha1(f"blob {size}\0".encode("ascii"))
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{CATALOG['repo']}/{CATALOG['revision']}/{path}", timeout=45) as response, (staging / name).open("wb") as stream:
            received = 0
            while chunk := response.read(256 * 1024):
                received += len(chunk)
                if received > size:
                    raise ValueError("Unexpected dictionary size")
                stream.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                output.put(("download", done, total))
        if received != size or digest.hexdigest() != item["sha"]:
            raise ValueError("Dictionary integrity check failed")
    output.put(("stage", "validating_dictionary"))
    count = validate(staging)
    (staging / "provenance.json").write_text(json.dumps(dict(repo=CATALOG["repo"], revision=CATALOG["revision"],
        code=code, files=pack["files"], entries=count, license="See bundled NOTICE files"), ensure_ascii=False, indent=2), encoding="utf-8")
    target = publish(staging, args["root"], code)
    output.put(("installed", str(target)))


def archive_pairs(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) > 5000:
            raise ValueError("Too many archive members")
        available = {name.lower(): name for name in names}
        return [(name, available[name[:-4].lower() + ".dic"]) for name in names
                if name.lower().endswith(".aff") and name[:-4].lower() + ".dic" in available]


def import_pack(args, output):
    code = language_code(args["code"])
    staging, source = Path(args["work"]), Path(args["source"])
    if source.suffix.lower() in {".zip", ".oxt"}:
        with zipfile.ZipFile(source) as archive:
            for member, suffix, limit in [(args["aff_member"], ".aff", MAX_AFF), (args["dic_member"], ".dic", MAX_DIC)]:
                info = archive.getinfo(member)
                if info.file_size > limit or info.flag_bits & 1:
                    raise ValueError("Oversized or encrypted dictionary")
                # Read only the selected pair; never extract archive paths to disk.
                with archive.open(info) as reader, (staging / ("dictionary" + suffix)).open("wb") as writer:
                    copied = 0
                    while block := reader.read(256 * 1024):
                        copied += len(block)
                        if copied > limit:
                            raise ValueError("Dictionary exceeds size limit")
                        writer.write(block)
    else:
        for file, suffix, limit in [(source, ".aff", MAX_AFF), (Path(args["dic"]), ".dic", MAX_DIC)]:
            if file.stat().st_size > limit:
                raise ValueError("Dictionary exceeds size limit")
            shutil.copyfile(file, staging / ("dictionary" + suffix))
    output.put(("stage", "validating_dictionary"))
    count = validate(staging)
    (staging / "provenance.json").write_text(json.dumps(dict(source=str(source), code=code, entries=count,
        license="User-supplied dictionary. Retain its provider's license."), ensure_ascii=False), encoding="utf-8")
    target = publish(staging, args["root"], code)
    output.put(("installed", str(target)))
