from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import os
import tempfile
import math
import copy
from uuid import uuid4
from core.projects.safety import protect_output


@dataclass
class Segment:
    start: int = 0
    end: int = 0
    text: str = ''
    language: str = 'pl'
    words: list = field(default_factory=list)
    timed: bool = True
    original: str = ''
    review: bool = False
    checked: bool = False


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

    def validate(self):
        from PySide6.QtGui import QColor
        def number(value, low, high):
            return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
        if (not isinstance(self.font, str) or len(self.font) > 256 or type(self.bold) is not bool
                or any(type(value) is not int for value in (self.size,self.stroke,self.animation_ms))
                or not number(self.size, 8, 300) or not number(self.x, 0, 100)
                or not number(self.y, 0, 100) or not number(self.width, 1, 100)
                or not number(self.stroke, 0, 15) or not number(self.animation_ms, 1, 5000)
                or self.effect not in ('static','fade','left','right','up','typewriter','words','highlight','pop')
                or any(not isinstance(value, str) or not QColor(value).isValid()
                       for value in (self.color,self.outline,self.background,self.active_color))):
            raise ValueError('Nieprawidłowy styl napisów / Invalid subtitle style.')
        return self


@dataclass
class Track:
    name: str = 'Napisy'
    visible: bool = True
    segments: list[Segment] = field(default_factory=list)
    style: Style = field(default_factory=Style)
    source: str = ''
    track_id: str = field(default_factory=lambda: uuid4().hex)


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
    version: int = 2
    video: str = ''
    tracks: list[Track] = field(default_factory=lambda: [Track()])
    logos: list[Logo] = field(default_factory=list)
    language: str = 'pl'
    theme: str = 'dark'
    quality: dict = field(default_factory=lambda: dict(cps=22, line=42, minimum=600))
    range_start: int = 0
    range_end: int | None = None
    transcript: dict | None = None
    linked_track: str = ''

    def data(self):
        return asdict(self)

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict):
            raise ValueError('Projekt musi być obiektem JSON / Project must be a JSON object.')
        if data.get('version') not in (1,2):
            raise ValueError('Nieobsługiwana wersja projektu / Unsupported project version')
        d = copy.deepcopy(data)
        d['version'] = 2
        d['tracks'] = [Track(name=t['name'], visible=t['visible'],
                            style=Style(**t['style']), segments=[Segment(**s) for s in t['segments']], source=t.get('source',''),
                            track_id=t.get('track_id') or uuid4().hex)
                       for t in d['tracks']]
        d['logos'] = [Logo(**l) for l in d['logos']]
        if not d['tracks']:
            d['tracks'] = [Track()]
        result = cls(**d)
        if not isinstance(result.video,str) or not isinstance(result.linked_track,str):
            raise ValueError('Nieprawidłowe źródło lub powiązanie / Invalid source or link')
        if result.transcript is not None:
            from srtstudio.project import Project as SpeechProject
            SpeechProject.loads(json.dumps(result.transcript,allow_nan=False))
        if len({track.track_id for track in result.tracks}) != len(result.tracks):
            raise ValueError('Powtórzone identyfikatory ścieżek / Duplicate track identifiers')
        if type(result.range_start) is not int or not 0 <= result.range_start <= 2147483647:
            raise ValueError('Nieprawidłowy początek zakresu.')
        if result.range_end is not None and (type(result.range_end) is not int or not result.range_start <= result.range_end <= 2147483647):
            raise ValueError('Nieprawidłowy koniec zakresu.')
        if result.language not in ('pl','en') or result.theme not in ('dark','light','system'):
            raise ValueError('Nieprawidłowy język lub motyw projektu.')
        if sum(len(t.segments) for t in result.tracks) > 100000 or len(result.logos) > 64:
            raise ValueError('Przekroczono limit segmentów lub warstw.')
        if (not isinstance(result.quality,dict) or set(result.quality) != {'cps','line','minimum'}
                or any(type(value) not in (int,float) or not math.isfinite(value) or value<=0
                       for value in result.quality.values())):
            raise ValueError('Nieprawidłowy profil jakości / Invalid quality profile')
        for track in result.tracks:
            s = track.style
            s.validate()
            if not isinstance(track.name, str) or not isinstance(track.source, str) or type(track.visible) is not bool:
                raise ValueError('Nieprawidłowa ścieżka / Invalid track.')
            if not isinstance(track.track_id,str) or not track.track_id or len(track.track_id)>128:
                raise ValueError('Nieprawidłowy identyfikator ścieżki / Invalid track identifier')
            for segment in track.segments:
                if (type(segment.start) is not int or type(segment.end) is not int
                        or not isinstance(segment.text,str) or len(segment.text) > 100000
                        or not isinstance(segment.language,str) or type(segment.timed) is not bool
                        or not isinstance(segment.words,list) or not isinstance(segment.original,str)
                        or type(segment.review) is not bool or type(segment.checked) is not bool):
                    raise ValueError('Nieprawidłowy segment.')
                previous = segment.start
                for index, word in enumerate(segment.words):
                    if (not isinstance(word,dict) or type(word.get('start')) is not int or type(word.get('end')) is not int
                            or not segment.start <= word['start'] < word['end'] <= segment.end
                            or word['start'] < previous or not isinstance(word.get('text',''),str)):
                        raise ValueError(f'Nieprawidłowy czas słowa / Invalid word timing: {index+1}')
                    previous = word['end']
                    if 'probability' in word and (type(word['probability']) not in (int,float)
                            or not math.isfinite(word['probability']) or not 0 <= word['probability'] <= 1):
                        raise ValueError('Nieprawidłowa ocena słowa / Invalid word score')
                if segment.words and len(segment.words) != len(segment.text.split()):
                    raise ValueError('Liczba czasów słów nie odpowiada tekstowi / Word count differs from text.')
                if (segment.words and all('text' in word for word in segment.words)
                        and ' '.join(' '.join(word['text'] for word in segment.words).split()) != ' '.join(segment.text.split())):
                    raise ValueError('Czasy słów nie odpowiadają treści / Word alignment differs from text')
        for logo in result.logos:
            if (not isinstance(logo.path,str) or type(logo.start) is not int or type(logo.end) is not int
                    or type(logo.visible) is not bool or not 0<=logo.start<logo.end
                    or not (0 <= logo.x <= 100 and 0 <= logo.y <= 100 and 1 <= logo.width <= 100 and 0 <= logo.opacity <= 100)):
                raise ValueError('Nieprawidłowe właściwości logo.')
        return result


def save(project, path):
    path = protect_output(project, path, '.json')
    Project.from_data(project.data())
    d = project.data()
    resources = [(d, 'video')] + [(l, 'path') for l in d['logos']] + [(t, 'source') for t in d['tracks']]
    if d.get('transcript'):
        resources.append((d['transcript'],'source'))
    for obj, key in resources:
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
    # Validate structure before traversing fields from an untrusted document.
    Project.from_data(d)
    resources = [(d,'video')] + [(l,'path') for l in d.get('logos',[])] + [(t,'source') for t in d['tracks']]
    if d.get('transcript'):
        resources.append((d['transcript'],'source'))
    for obj, key in resources:
        if obj.get(key):
            obj[key] = str((path.parent / obj[key]).resolve())
    return Project.from_data(d)
