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
    keyframes: list = field(default_factory=list)


BANNER_ANIMATIONS = ('none', 'fade', 'slide_up', 'slide_down', 'slide_left', 'slide_right', 'pop')


def validate_keyframes(keyframes):
    """Keyframes are [{ms, x, y, scale}] with strictly increasing ms; x/y in %, scale in % (10..400)."""
    def number(value, low, high):
        return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
    if not isinstance(keyframes, list) or len(keyframes) > 200:
        raise ValueError('Limit 200 klatek kluczowych / Limit: 200 keyframes')
    previous = -1
    for frame in keyframes:
        if (not isinstance(frame, dict) or set(frame) != {'ms', 'x', 'y', 'scale'}
                or type(frame['ms']) is not int or not previous < frame['ms'] <= 2147483647
                or not number(frame['x'], 0, 100) or not number(frame['y'], 0, 100)
                or not number(frame['scale'], 10, 400)):
            raise ValueError('Nieprawidłowe klatki kluczowe / Invalid keyframes: {ms, x, y, scale}, rosnące ms')
        previous = frame['ms']
    return keyframes


def set_keyframe(layer, ms, x, y, scale=100):
    """Insert or replace the keyframe at ms, keeping the list sorted."""
    frames = [frame for frame in layer.keyframes if frame['ms'] != ms]
    frames.append({'ms': int(ms), 'x': float(x), 'y': float(y), 'scale': float(scale)})
    layer.keyframes = validate_keyframes(sorted(frames, key=lambda frame: frame['ms']))


@dataclass
class Banner:
    name: str = 'Baner'
    text: str = 'Twój napis'
    x: float = 50
    y: float = 20
    width: float = 70
    height: float = 16
    font: str = 'Arial'
    font_size: int = 64
    bold: bool = True
    color: str = '#ffffff'
    background: str = '#7546c7'
    border_color: str = '#ffffff'
    border_width: int = 0
    radius: int = 20
    padding: int = 16
    opacity: float = 100
    start: int = 0
    end: int = 2147483647
    visible: bool = True
    align: str = 'center'
    auto_fit: bool = True
    banner_id: str = field(default_factory=lambda: uuid4().hex)
    animation: str = 'none'
    animation_ms: int = 400
    keyframes: list = field(default_factory=list)

    def validate(self):
        from PySide6.QtGui import QColor
        def number(value, low, high):
            return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
        if (not isinstance(self.text, str) or len(self.text) > 10000
                or not isinstance(self.name, str) or len(self.name) > 256
                or not isinstance(self.font, str) or len(self.font) > 256
                or not isinstance(self.banner_id, str) or not self.banner_id or len(self.banner_id) > 128
                or any(type(value) is not bool for value in (self.bold, self.visible, self.auto_fit))
                or not all(number(value, 0, 100) for value in (self.x, self.y, self.opacity))
                or not all(number(value, 1, 100) for value in (self.width, self.height))
                or any(type(value) is not int for value in
                       (self.font_size, self.border_width, self.radius, self.padding, self.start, self.end))
                or not 8 <= self.font_size <= 300 or not 0 <= self.border_width <= 30
                or not 0 <= self.radius <= 300 or not 0 <= self.padding <= 200
                or not 0 <= self.start < self.end <= 2147483647
                or self.align not in ('left', 'center', 'right')
                or self.animation not in BANNER_ANIMATIONS
                or type(self.animation_ms) is not int or not 1 <= self.animation_ms <= 5000
                or any(not isinstance(value, str) or not QColor(value).isValid()
                       for value in (self.color, self.background, self.border_color))):
            raise ValueError('Nieprawidłowe właściwości baneru / Invalid banner properties.')
        validate_keyframes(self.keyframes)
        return self


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
    banners: list[Banner] = field(default_factory=list)

    def data(self):
        data = asdict(self)
        # Projects without 0.8 features stay version 2 so 0.7.x can still open them.
        for logo in data['logos']:
            if not logo['keyframes']:
                logo.pop('keyframes')
        if self.banners or any(logo.keyframes for logo in self.logos):
            data['version'] = 3
        else:
            data.pop('banners')
            data['version'] = 2
        return data

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict):
            raise ValueError('Projekt musi być obiektem JSON / Project must be a JSON object.')
        if data.get('version') not in (1,2,3):
            raise ValueError('Nieobsługiwana wersja projektu / Unsupported project version')
        d = copy.deepcopy(data)
        d['version'] = 3 if d.get('banners') or any(
            isinstance(logo, dict) and logo.get('keyframes') for logo in d.get('logos', [])) else 2
        if not isinstance(d.get('banners', []), list) or len(d.get('banners', [])) > 64:
            raise ValueError('Limit 64 banerów / Limit: 64 banners')
        d['banners'] = [Banner(**item).validate() for item in d.get('banners', [])]
        if len({banner.banner_id for banner in d['banners']}) != len(d['banners']):
            raise ValueError('Powtórzony identyfikator baneru / Duplicate banner identifier')
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
        def number(value, low, high):
            return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
        for logo in result.logos:
            if (not isinstance(logo.path,str) or type(logo.start) is not int or type(logo.end) is not int
                    or type(logo.visible) is not bool or not 0<=logo.start<logo.end
                    or not (number(logo.x, 0, 100) and number(logo.y, 0, 100)
                            and number(logo.width, 1, 100) and number(logo.opacity, 0, 100))):
                raise ValueError('Nieprawidłowe właściwości logo.')
            validate_keyframes(logo.keyframes)
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
