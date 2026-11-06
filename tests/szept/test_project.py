import io
import math
from unittest.mock import patch

import pytest
import srt
import webvtt

from srtstudio.project import (Project, Profile, Segment, atomic_write, export, issues,
                               parse_time, split_segment, timestamp, wrap_text)


def sample():
    return Project(duration=4000, segments=[Segment(1.2, 4.6, "Zażółć gęślą jaźń."), Segment(3601.001, 3604.9, "Drugi fragment.")])


def test_independent_srt_parser():
    p = sample()
    parsed = list(srt.parse(export(p, "srt")))
    assert len(parsed) == 2
    assert parsed[0].content == "Zażółć gęślą jaźń."
    assert parsed[1].start.total_seconds() == 3601.001


def test_independent_vtt_parser():
    p = sample()
    p.segments[0].text = "Ja < Ty & My --> Oni"
    parsed = webvtt.from_buffer(io.StringIO(export(p, "vtt")))
    assert len(parsed) == 2
    assert parsed[0].raw_text == "Ja &lt; Ty &amp; My --&gt; Oni"
    assert parsed[1].start == "01:00:01.001"


@pytest.mark.parametrize("start,end", [(-1, 1), (1, 1), (1.0001, 1.0004), (2, 1)])
def test_invalid_times_block_export(start, end):
    p = Project(segments=[Segment(start, end, "tekst")])
    with pytest.raises(ValueError):
        export(p, "srt")


def test_empty_overlap_and_duration():
    p = Project(duration=10, segments=[Segment(0, 3, "a"), Segment(2, 11, "")])
    assert set(issues(p, 1)[0]) == {"overlap", "beyond", "empty"}
    with pytest.raises(ValueError):
        export(p, "vtt")


def test_recommendations_do_not_block():
    p = Project(segments=[Segment(0, .2, "Bardzo długi tekst " * 20)])
    errors, warnings = issues(p, 0)
    assert not errors
    assert {"lines", "duration", "cps"} <= set(warnings)
    assert "Bardzo" in export(p, "srt")


def test_no_ui_marks_and_current_text():
    p = sample()
    p.segments[0].original = "BŁĄD"
    p.segments[0].text = "Poprawione"
    p.segments[0].review = True
    for fmt in ("txt", "srt", "vtt"):
        result = export(p, fmt)
        assert "Poprawione" in result and "BŁĄD" not in result and "underline" not in result


def test_txt_and_project_roundtrip():
    p = sample()
    assert export(p, "txt").startswith("Zażółć")
    assert "-->" not in export(p, "txt")
    assert export(p, "txt", True).startswith("[00:00:01,200]")
    assert Project.loads(p.dumps()).dumps() == p.dumps()
    with pytest.raises(ValueError):
        Project.loads('{"schema":2}')


def test_atomic_failure_preserves_old_file(tmp_path):
    path = tmp_path / "polskie znaki ą.txt"
    path.write_text("stary", encoding="utf-8")
    with patch("srtstudio.project.os.replace", side_effect=PermissionError("denied")):
        with pytest.raises(PermissionError):
            atomic_write(path, "nowy")
    assert path.read_text(encoding="utf-8") == "stary"
    assert list(tmp_path.iterdir()) == [path]
    atomic_write(path, "zażółć")
    assert path.read_bytes() == "zażółć".encode()


def test_split_with_word_times_and_edited_fallback():
    s = Segment(0, 5, "Ala ma kota", "Ala ma kota", [dict(word="Ala", start=0, end=1), dict(word=" ma", start=1.5, end=2), dict(word=" kota", start=2.5, end=5)])
    left, right = split_segment(s, 4)
    assert left.end == right.start == 1.25
    assert not left.review
    s.text = "Ala chce kota"
    left, right = split_segment(s, 4)
    assert left.review and right.review


def test_wrapping_and_time():
    text = "To jest tekst bez utraty słów i bez rozcinania wyrazów."
    assert wrap_text(text, 15).split() == text.split()
    assert timestamp(3599.9996) == "01:00:00,000"
    assert parse_time("01:02:03,004") == 3723.004
    with pytest.raises(ValueError):
        parse_time("00:99:00")


def test_captions_preserve_words_and_real_timing():
    from srtstudio.engine import caption_segments
    words = [dict(word=(" " if i else "") + word, start=i, end=i + .8)
             for i, word in enumerate("To jest pierwsze zdanie. To jest drugie zdanie.".split())]
    original = "".join(w["word"] for w in words)
    result = caption_segments(0, 8, original, words, False, dict(width=20, lines=2, maximum=7))
    assert len(result) >= 2
    assert " ".join(c["text"] for c in result) == original
    for caption in result:
        assert caption["start"] == caption["words"][0]["start"]
        assert caption["end"] == caption["words"][-1]["end"]


def test_asr_word_mismatch_keeps_authoritative_text():
    from srtstudio.engine import caption_segments
    result = caption_segments(0, 5, "Właściwy tekst", [dict(word="inny", start=1, end=3)], False, {})
    assert result[0]["text"] == "Właściwy tekst"
    assert result[0]["review"]
