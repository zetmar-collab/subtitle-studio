from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Segment:
    start: float
    end: float
    text: str
    original: str = ""
    words: list[dict] = field(default_factory=list)
    review: bool = False
    spell_language: str = ""
    checked: bool = False


@dataclass
class Profile:
    width: int = 42
    lines: int = 2
    cps: float = 17
    minimum: float = 1
    maximum: float = 7


@dataclass
class Project:
    schema: int = 1
    source: str = ""
    duration: float = 0
    language: str = "pl"
    model: str = "small"
    segments: list[Segment] = field(default_factory=list)
    profile: Profile = field(default_factory=Profile)
    incomplete: bool = False
    original_text: str = ""

    def dumps(self):
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, allow_nan=False)

    @classmethod
    def loads(cls, text):
        d = json.loads(text)
        if not isinstance(d, dict) or type(d.get("schema")) is not int or d.get("schema") != 1:
            raise ValueError("schema")
        d["segments"] = [Segment(**s) for s in d.get("segments", [])]
        d["profile"] = Profile(**d.get("profile", {}))
        p = cls(**d)
        def number(value):
            return type(value) in (int, float) and math.isfinite(value)
        def code(value, automatic=False):
            return isinstance(value, str) and ((automatic and value == "auto") or bool(re.fullmatch(r"[a-z]{2,3}(?:_[A-Za-z0-9]{2,8}){0,2}", value)))
        if not number(p.duration) or p.duration < 0:
            raise ValueError("duration")
        if not all(isinstance(value, str) for value in (p.source, p.model, p.original_text)) or not code(p.language, True):
            raise ValueError("project")
        if type(p.incomplete) is not bool:
            raise ValueError("incomplete")
        profile = p.profile
        if (type(profile.width) is not int or not 1 <= profile.width <= 1000 or
                type(profile.lines) is not int or not 1 <= profile.lines <= 100 or
                not all(number(v) for v in (profile.cps, profile.minimum, profile.maximum)) or
                profile.cps <= 0 or not 0 <= profile.minimum <= profile.maximum or profile.maximum <= 0):
            raise ValueError("profile")
        for s in p.segments:
            if not number(s.start) or not number(s.end):
                raise ValueError("time")
            if not isinstance(s.text, str) or not isinstance(s.original, str) or type(s.review) is not bool or type(s.checked) is not bool:
                raise ValueError("segment")
            if not isinstance(s.spell_language, str) or (s.spell_language and s.spell_language != "off" and not code(s.spell_language)):
                raise ValueError("spell_language")
            if not isinstance(s.words, list):
                raise ValueError("words")
            for word in s.words:
                if not isinstance(word, dict) or not isinstance(word.get("word"), str) or not all(number(word.get(key)) for key in ("start", "end")):
                    raise ValueError("words")
                if "probability" in word and (not number(word["probability"]) or not 0 <= word["probability"] <= 1):
                    raise ValueError("probability")
        return p


def atomic_write(path: str | Path, text: str):
    path = Path(path)
    fd, temp = tempfile.mkstemp(prefix=".szept-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def wrap_text(text, width=42):
    words = text.split()
    lines, current = [], ""
    for word in words:
        if current and len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    # Avoid leaving a short solitary word on the final line where possible.
    if len(lines) > 1 and len(lines[-1].split()) == 1 and len(lines[-1]) <= 3:
        prev = lines[-2].split()
        if len(prev) > 1 and len(prev[-1]) + 1 + len(lines[-1]) <= width:
            lines[-1] = prev.pop() + " " + lines[-1]
            lines[-2] = " ".join(prev)
    return "\n".join(lines)


def issues(project: Project, index: int):
    s, p = project.segments[index], project.profile
    errors, warnings = [], []
    if not (math.isfinite(s.start) and math.isfinite(s.end)):
        return ["time"], []
    start, end = round(s.start * 1000), round(s.end * 1000)
    if not (math.isfinite(s.start) and math.isfinite(s.end)) or start < 0 or end <= start:
        errors.append("time")
    if not s.text.strip():
        errors.append("empty")
    if project.duration and end > round(project.duration * 1000):
        errors.append("beyond")
    if index and start < round(project.segments[index - 1].end * 1000):
        errors.append("overlap")
    duration = s.end - s.start
    wrapped = wrap_text(s.text, p.width).splitlines()
    if len(wrapped) > p.lines or any(len(line) > p.width for line in wrapped):
        warnings.append("lines")
    if duration < p.minimum or duration > p.maximum:
        warnings.append("duration")
    if duration > 0 and len(s.text.replace("\n", "")) / duration > p.cps:
        warnings.append("cps")
    if s.review and not s.checked:
        warnings.append("review")
    return errors, warnings


def timestamp(seconds: float, separator=","):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{ms:03}"


def parse_time(value):
    value = value.strip().replace(",", ".")
    if ":" not in value:
        result = float(value)
    else:
        h, m, s = value.split(":")
        if not 0 <= int(m) < 60 or not 0 <= float(s) < 60:
            raise ValueError("time")
        result = int(h) * 3600 + int(m) * 60 + float(s)
    if not math.isfinite(result) or result < 0:
        raise ValueError("time")
    return result


def export(project: Project, fmt: str, txt_times=False):
    if fmt == "json":
        return project.dumps()
    if not project.segments:
        raise ValueError("empty")
    if fmt == "txt":
        return "\n\n".join((f"[{timestamp(s.start)}] " if txt_times else "") + s.text.strip()
                           for s in project.segments) + "\n"
    if fmt not in {"srt", "vtt"}:
        raise ValueError("format")
    invalid = [(i + 1, issues(project, i)[0]) for i in range(len(project.segments)) if issues(project, i)[0]]
    if invalid:
        raise ValueError(str(invalid))
    blocks = []
    for i, s in enumerate(project.segments, 1):
        text = wrap_text(s.text, project.profile.width)
        # SRT is plain text; avoid accidental style interpretation in players.
        if fmt == "srt":
            if re.search(r"<[^>]+>", text):
                raise ValueError("markup")
        else:
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        sep = "," if fmt == "srt" else "."
        blocks.append(f"{i}\n{timestamp(s.start, sep)} --> {timestamp(s.end, sep)}\n{text}\n")
    return ("WEBVTT\n\n" if fmt == "vtt" else "") + "\n".join(blocks)


def split_segment(s: Segment, position: int):
    left, right = s.text[:position].strip(), s.text[position:].strip()
    if not left or not right:
        raise ValueError("split")
    boundary = s.start + (s.end - s.start) * len(left) / max(1, len(s.text))
    exact = False
    left_words, right_words = [], []
    if s.words and s.text.strip() == s.original.strip():
        count = 0
        for i, word in enumerate(s.words[:-1]):
            count += len(word["word"])
            if abs(count - position) <= 1:
                boundary = (word["end"] + s.words[i + 1]["start"]) / 2
                left_words, right_words = s.words[:i + 1], s.words[i + 1:]
                exact = True
                break
    return [Segment(s.start, boundary, left, left, left_words, not exact, s.spell_language),
            Segment(boundary, s.end, right, right, right_words, not exact, s.spell_language)]
