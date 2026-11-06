import shutil
import wave

import pytest

from srtstudio.audio import decode_chunk, probe, run, binary, read_pcm16


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "nagranie ąę.wav"
    with wave.open(str(path), "wb") as f:
        f.setparams((2, 2, 22050, 0, "NONE", "not compressed"))
        f.writeframes(b"\0" * 22050 * 4 * 2)
    return path


def test_actual_decode_and_probe(audio, tmp_path):
    metadata = probe(audio)
    assert metadata == dict(duration=2, codec="pcm_s16le", rate=22050, channels=2)
    output = tmp_path / "mono.wav"
    decode_chunk(audio, output, .5, 1)
    info = probe(output)
    assert info["duration"] == 1 and info["channels"] == 1 and info["rate"] == 16000
    waveform = read_pcm16(output)
    assert waveform.dtype.name == "float32" and waveform.shape == (16000,)
    assert not waveform.any()
    with pytest.raises(ValueError):
        read_pcm16(audio)


@pytest.mark.parametrize("extension", ["mp3", "flac", "m4a", "ogg", "opus"])
def test_real_formats(audio, tmp_path, extension):
    output = tmp_path / ("próba." + extension)
    run([binary("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", str(audio), str(output)])
    assert probe(output)["duration"] > 1.9
    decode_chunk(output, tmp_path / "decoded.wav", 0, 1)


def test_corrupted_file(tmp_path):
    path = tmp_path / "broken.mp3"
    path.write_bytes(b"corrupted audio")
    with pytest.raises(ValueError):
        probe(path)
