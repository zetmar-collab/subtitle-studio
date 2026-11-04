from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import os
import tempfile


@dataclass
class Segment:
    start: int = 0
    end: int = 0
    text: str = ''
    language: str = 'pl'
    words: list = field(default_factory=list)
    timed: bool = True


@dataclass
class Style:
    font: str = 'Arial'
    size: int = 48
    bold: bool = True
    color: str = '#ffffff'
    outline: str = '#111111'
    stroke: int = 3
    background: str = '#00000000'
    x: float = 50
    y: float = 88
    width: float = 88
    effect: str = 'static'
    animation_ms: int = 400
    active_color: str = '#ffdc55'


@dataclass
class Track:
    name: str = 'Napisy'
    visible: bool = True
    segments: list[Segment] = field(default_factory=list)
    style: Style = field(default_factory=Style)
    source: str = ''


@dataclass
class Logo:
    path: str = ''
    x: float = 88
    y: float = 12
    width: float = 15
    opacity: float = 100
    start: int = 0
    end: int = 2147483647
    visible: bool = True


@dataclass
class Project:
    version: int = 1
    video: str = ''
    tracks: list[Track] = field(default_factory=lambda: [Track()])
    logos: list[Logo] = field(default_factory=list)
    language: str = 'pl'
    theme: str = 'dark'
    quality: dict = field(default_factory=lambda: dict(cps=22, line=42, minimum=600))

    def data(self):
        return asdict(self)

    @classmethod
    def from_data(cls, data):
        if data.get('version') != 1:
            raise ValueError('Nieobsługiwana wersja projektu / Unsupported project version')
        d = dict(data)
        d['tracks'] = [Track(name=t['name'], visible=t['visible'],
                            style=Style(**t['style']), segments=[Segment(**s) for s in t['segments']], source=t.get('source',''))
                       for t in d['tracks']]
        d['logos'] = [Logo(**l) for l in d['logos']]
        if not d['tracks']:
            d['tracks'] = [Track()]
        result = cls(**d)
        if result.language not in ('pl','en') or result.theme not in ('dark','light','system'):
            raise ValueError('Nieprawidłowy język lub motyw projektu.')
        if sum(len(t.segments) for t in result.tracks) > 100000 or len(result.logos) > 64:
            raise ValueError('Przekroczono limit segmentów lub warstw.')
        for track in result.tracks:
            s = track.style
            if not (8 <= s.size <= 300 and 0 <= s.x <= 100 and 0 <= s.y <= 100 and 1 <= s.width <= 100 and 0 <= s.stroke <= 15 and 1 <= s.animation_ms <= 5000):
                raise ValueError('Nieprawidłowy styl napisów.')
            for segment in track.segments:
                if not isinstance(segment.start,int) or not isinstance(segment.end,int) or len(segment.text) > 100000:
                    raise ValueError('Nieprawidłowy segment.')
        for logo in result.logos:
            if not (0 <= logo.x <= 100 and 0 <= logo.y <= 100 and 1 <= logo.width <= 100 and 0 <= logo.opacity <= 100):
                raise ValueError('Nieprawidłowe właściwości logo.')
        return result


def save(project, path):
    path = Path(path).resolve()
    d = project.data()
    for obj, key in [(d, 'video')] + [(l, 'path') for l in d['logos']] + [(t, 'source') for t in d['tracks']]:
        if obj[key]:
            try:
                obj[key] = os.path.relpath(obj[key], path.parent)
            except ValueError:
                pass
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load(path):
    path = Path(path).resolve()
    if path.stat().st_size > 40_000_000:
        raise ValueError('Projekt przekracza limit 40 MB.')
    d = json.loads(path.read_text(encoding='utf-8'))
    for obj, key in [(d, 'video')] + [(l, 'path') for l in d['logos']] + [(t, 'source') for t in d['tracks']]:
        if obj.get(key):
            obj[key] = str((path.parent / obj[key]).resolve())
    return Project.from_data(d)
