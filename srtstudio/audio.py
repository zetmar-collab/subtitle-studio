import json
import math
import os
import shutil
import subprocess
import wave
from pathlib import Path

from core.media.tools import binary


def run(args, timeout=60):
    result = subprocess.run(args, capture_output=True, timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace")[-1500:])
    return result.stdout


def probe(path):
    d = json.loads(run([binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))
    stream = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    if stream is None:
        raise ValueError("no_audio")
    duration = float(d.get("format", {}).get("duration", stream.get("duration", 0)))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration")
    return dict(duration=duration, codec=stream.get("codec_name", "?"),
                rate=int(stream.get("sample_rate", 0)), channels=stream.get("channels", 0))


def decode_chunk(source, destination, offset, duration):
    if shutil.disk_usage(Path(destination).parent).free < duration * 32000 + 20_000_000:
        raise OSError("disk_space")
    run([binary("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", str(offset), "-i", str(source),
         "-map", "0:a:0", "-t", str(duration), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destination)],
        timeout=max(120, duration * 3))


def read_pcm16(path):
    """Read our bounded canonical WAV without a second FFmpeg/PyAV decode."""
    import numpy as np
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2 or stream.getframerate() != 16000:
            raise ValueError("Expected mono PCM16 at 16000 Hz")
        data = stream.readframes(stream.getnframes())
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
