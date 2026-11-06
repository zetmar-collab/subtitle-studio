"""Spawn-only workers. All network access lives in explicit resource downloads."""
import hashlib
import json
import os
import shutil
import traceback
import urllib.request
from pathlib import Path

from .audio import decode_chunk, probe, read_pcm16

MODELS = {
    "tiny": ("Systran/faster-whisper-tiny", 75, "1 GB RAM"),
    "base": ("Systran/faster-whisper-base", 145, "1–2 GB RAM"),
    "small": ("Systran/faster-whisper-small", 485, "2–4 GB RAM"),
    "medium": ("Systran/faster-whisper-medium", 1530, "5–8 GB RAM"),
    "large-v3": ("Systran/faster-whisper-large-v3", 3100, "8–12 GB RAM / ~5 GB VRAM int8"),
}
MODEL_FILES = {"config.json", "model.bin", "tokenizer.json", "vocabulary.json", "vocabulary.txt", "preprocessor_config.json"}


def model_ready(folder):
    p = Path(folder)
    return all((p / f).is_file() for f in ("model.bin", "config.json", "tokenizer.json"))


def get_json(url):
    with urllib.request.urlopen(url, timeout=45) as response:
        return json.load(response)


def download(url, target, queue, done=0, total=0, sha=None):
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=45) as response, open(target, "wb") as f:
        while block := response.read(1024 * 1024):
            f.write(block)
            digest.update(block)
            done += len(block)
            queue.put(("download", done, total))
    if sha and digest.hexdigest() != sha:
        raise ValueError("checksum")
    return done


def download_model(args, queue):
    name, root, staging = args["name"], Path(args["root"]), Path(args["work"])
    repo = MODELS[name][0]
    metadata = get_json(f"https://huggingface.co/api/models/{repo}?blobs=true")
    revision = metadata["sha"]
    files = [f for f in metadata["siblings"] if f["rfilename"] in MODEL_FILES or f["rfilename"].lower().startswith(("license", "readme"))]
    total = sum(f.get("size", 0) for f in files)
    if shutil.disk_usage(root).free < total + 100_000_000:
        raise OSError("disk_space")
    done = 0
    for f in files:
        name_on_disk = f["rfilename"]
        done = download(f"https://huggingface.co/{repo}/resolve/{revision}/{name_on_disk}",
                        staging / name_on_disk, queue, done, total, f.get("lfs", {}).get("sha256"))
    (staging / "provenance.json").write_text(json.dumps(dict(repo=repo, revision=revision, license="MIT")), encoding="utf-8")
    if not model_ready(staging):
        raise ValueError("model_missing")
    from .dictionaries import publish_directory
    publish_directory(staging, root, name)
    queue.put(("installed", str(root / name)))


def transcribe(args, queue):
    import math
    if not math.isfinite(args['duration']) or args['duration'] <= 0:
        raise ValueError('Nieprawidłowa długość nagrania / Invalid recording duration')
    import ctranslate2
    from faster_whisper import WhisperModel
    device = args["device"]
    queue.put(("stage", "loading"))
    if device == "cuda":
        if ctranslate2.get_cuda_device_count() < 1:
            raise RuntimeError("No CUDA device")
        # Check reported free memory when the NVIDIA management utility is available.
        import subprocess
        tool = shutil.which("nvidia-smi")
        if tool:
            result = subprocess.run([tool, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=10,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            required = 5000 if "large" in args["model"] else 2500 if "medium" in args["model"] else 1300
            if result.returncode == 0 and int(result.stdout.splitlines()[0]) < required:
                raise RuntimeError(f"Insufficient free GPU memory (recommended minimum: {required} MB)")
    supported = ctranslate2.get_supported_compute_types(device)
    compute = ("int8_float16" if "int8_float16" in supported else "float16") if device == "cuda" else "int8"
    if compute not in supported:
        compute = "float32"
    model = WhisperModel(args["model"], device=device, compute_type=compute, local_files_only=True,
                         cpu_threads=max(1, min(8, (os.cpu_count() or 2) - 1)))
    duration = args["duration"]
    language = args.get("language")
    if language is not None and language not in model.supported_languages:
        raise ValueError(f"Language {language} is not supported by this model")
    # Decode and recognize bounded 10-minute windows, retaining the original timeline.
    # A phrase can be split at a window edge; that boundary is flagged for review.
    window = 600
    for offset in range(0, int(duration) + 1, window):
        length = min(window, duration - offset)
        if length <= 0:
            break
        queue.put(("stage", "decoding"))
        wav = Path(args["work"]) / "audio.wav"
        decode_chunk(args["source"], wav, offset, length)
        queue.put(("stage", "recognizing"))
        audio = read_pcm16(wav)
        segments, info = model.transcribe(audio, language=language, task="transcribe", vad_filter=True,
                                          word_timestamps=True, beam_size=5,
                                          condition_on_previous_text=False)
        if language is None:
            language = info.language
            queue.put(("language", info.language, info.language_probability))
        for s in segments:
            if not s.text.strip():
                continue
            start, end = float(offset + s.start), float(min(duration, offset + s.end))
            if end <= start:
                continue
            words = [dict(start=float(offset + w.start), end=float(min(duration, offset + w.end)), word=w.word,
                          probability=float(w.probability)) for w in (s.words or [])]
            review = bool(s.avg_logprob < -1 or (offset > 0 and s.start < 1) or s.end > window - 1)
            for caption in caption_segments(start, end, s.text.strip(), words, review, args.get("profile", {})):
                queue.put(("segment", caption))
            queue.put(("progress", end / duration))
        wav.unlink(missing_ok=True)
        del audio
        queue.put(("progress", (offset + length) / duration))


def caption_segments(start, end, text, words, review, profile):
    """Use real word boundaries. Guidelines never cause content to be dropped."""
    if not words:
        return [dict(start=start, end=end, text=text, original=text, words=[], review=review)]
    limit = profile.get("width", 42) * profile.get("lines", 2)
    maximum = profile.get("maximum", 7)
    groups, current = [], []
    for word in words:
        proposed = "".join(w["word"] for w in current + [word]).strip()
        if current and (len(proposed) > limit or word["end"] - current[0]["start"] > maximum):
            groups.append(current)
            current = []
        current.append(word)
        if word["word"].rstrip().endswith((".", "!", "?", ";")) and word["end"] - current[0]["start"] >= 1:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    result = []
    for group in groups:
        content = "".join(w["word"] for w in group).strip()
        # If a tokenizer's word strings don't reproduce the recognized text,
        # retain the authoritative ASR segment rather than silently changing it.
        result.append(dict(start=group[0]["start"], end=group[-1]["end"], text=content,
                           original=content, words=group, review=review or group[-1]["end"] <= group[0]["start"]))
    if "".join("".join(w["word"] for w in group) for group in groups).strip() != text:
        return [dict(start=start, end=end, text=text, original=text, words=words, review=True)]
    return result


def download_dictionary(args, queue):
    from .dictionaries import download_pack
    download_pack(args, queue)


def worker(kind, args, queue):
    try:
        if kind == "asr":
            transcribe(args, queue)
        elif kind == "model":
            download_model(args, queue)
        elif kind == "probe":
            queue.put(("metadata", probe(args["source"])))
        elif kind == "dictionary":
            download_dictionary(args, queue)
        elif kind == "import_dictionary":
            from .dictionaries import import_pack
            import_pack(args, queue)
        queue.put(("done",))
    except Exception as error:
        # Only error type and technical message, never recognized speech.
        queue.put(("error", type(error).__name__, str(error)))
