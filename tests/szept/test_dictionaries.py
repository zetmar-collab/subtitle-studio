import json
import queue
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from srtstudio.dictionaries import (CATALOG, PACKS, archive_pairs, import_pack, installed,
                                    language_code, load_dictionary, publish, resolve)
from srtstudio.spelling import canonical, word_spans, spell_loop, add_word, user_words, save_user_words


def pair(folder, words=("kot", "dom", "który")):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "dictionary.aff").write_text("SET UTF-8\nTRY aeiou\n", encoding="utf-8")
    (folder / "dictionary.dic").write_text(str(len(words)) + "\n" + "\n".join(words) + "\n", encoding="utf-8")
    return folder


def test_unicode_tokenization_uses_whole_words_and_skips_identifiers():
    text = "😀 zażo\u0301łć don't l’amour e-mail https://example.test/błont a@b.test plik.wav mp3 123abc foo_bar"
    spans = list(word_spans(text))
    assert [word for _, _, word in spans] == ["zażo\u0301łć", "don't", "l’amour", "e-mail"]
    assert all(text[start:end] == word for start, end, word in spans)
    assert canonical("l’amour") == "l'amour"
    assert canonical("zażo\u0301łć") == "zażółć"


def test_user_words_can_be_removed_and_are_language_scoped(tmp_path):
    add_word(tmp_path, "pl", "MójWyraz")
    assert user_words(tmp_path, "pl") == {"mójwyraz"}
    assert not user_words(tmp_path, "en")
    save_user_words(tmp_path, "pl", [])
    assert not user_words(tmp_path, "pl")
    save_user_words(tmp_path, "pl", ["  MójWyraz  ", ""])
    assert user_words(tmp_path, "pl") == {"mójwyraz"}
    with pytest.raises(ValueError):
        add_word(tmp_path, "../outside", "word")


def test_missing_and_invalid_dictionary_are_different(tmp_path):
    commands, output = queue.Queue(), queue.Queue()
    commands.put((1, "check", "pl", "kot"))
    commands.put(None)
    spell_loop(tmp_path, commands, output)
    assert output.get()[3]["kind"] == "missing"
    folder = tmp_path / "dictionaries" / "pl"
    folder.mkdir(parents=True)
    (folder / "dictionary.aff").write_text("SET UTF-8\n", encoding="utf-8")
    commands.put((2, "check", "pl", "kot"))
    commands.put(None)
    spell_loop(tmp_path, commands, output)
    assert output.get()[3]["kind"] == "invalid"


def test_failed_import_preserves_existing_dictionary(tmp_path):
    old = pair(tmp_path / "dictionaries" / "pl")
    before = (old / "dictionary.dic").read_bytes()
    source = pair(tmp_path / "input")
    (source / "dictionary.aff").write_text("not a dictionary", encoding="utf-8")
    work = tmp_path / "staging"
    work.mkdir()
    with pytest.raises(ValueError):
        import_pack(dict(source=str(source / "dictionary.aff"), dic=str(source / "dictionary.dic"),
                         root=str(tmp_path), code="pl", work=str(work)), queue.Queue())
    assert (old / "dictionary.dic").read_bytes() == before


def test_directory_swap_rolls_back_on_failure(tmp_path):
    old = pair(tmp_path / "dictionaries" / "pl")
    staging = pair(tmp_path / "staging", ("nowy",))
    original = Path.rename
    def rename(path, target):
        if path == staging:
            raise PermissionError("replacement denied")
        return original(path, target)
    with patch.object(Path, "rename", rename), pytest.raises(PermissionError):
        publish(staging, tmp_path, "pl")
    assert "który" in (old / "dictionary.dic").read_text(encoding="utf-8")
    assert not list((tmp_path / "dictionaries").glob(".backup-*"))


def test_oxt_import_never_extracts_archive_paths(tmp_path):
    archive = tmp_path / "dictionary.oxt"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../../outside.aff", "SET UTF-8\n")
        z.writestr("../../outside.dic", "2\nkot\ndom\n")
        z.writestr("../../unrelated.txt", "do not extract")
    pairs = archive_pairs(archive)
    assert len(pairs) == 1
    work = tmp_path / "staging"
    work.mkdir()
    import_pack(dict(source=str(archive), root=str(tmp_path), code="pl", work=str(work),
                     aff_member=pairs[0][0], dic_member=pairs[0][1]), queue.Queue())
    assert installed(tmp_path) == {"pl"}
    assert load_dictionary(tmp_path, "pl").lookup("kot")
    assert not (tmp_path.parent / "outside.aff").exists()
    assert not (tmp_path / "unrelated.txt").exists()


def test_language_resolution_preserves_explicit_variants(tmp_path):
    pair(tmp_path / "dictionaries" / "en_GB")
    pair(tmp_path / "dictionaries" / "pt_BR")
    assert resolve(tmp_path, "en") == "en"
    assert resolve(tmp_path, "en_GB") == "en_GB"
    assert resolve(tmp_path, "pt") == "pt_BR"
    assert resolve(tmp_path, "pt_PT") == "pt_PT"
    assert resolve(tmp_path, "off") == "off"


def test_catalog_has_pinned_files_sizes_and_licenses():
    assert len(PACKS) == 22 and len(CATALOG["revision"]) == 40
    for pack in PACKS.values():
        assert pack["files"][0]["path"].endswith(".aff")
        assert pack["files"][1]["path"].endswith(".dic")
        assert len(pack["files"]) > 2
        assert all(f["size"] > 0 and len(f["sha"]) == 40 for f in pack["files"])


def test_native_dictionary_supports_unicode_paths_and_rejects_empty_records(tmp_path):
    from srtstudio.dictionaries import open_dictionary
    folder = pair(tmp_path / "zażółć 日本")
    dictionary = open_dictionary(folder / "dictionary")
    assert dictionary.lookup("który")
    del dictionary
    (folder / "dictionary.dic").write_text("2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        open_dictionary(folder / "dictionary")
