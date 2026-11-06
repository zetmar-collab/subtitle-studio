from pathlib import Path
import re
import pysubs2
from charset_normalizer import from_bytes
from core.projects.model import Segment


def read(path, encoding=None, fps=25):
    raw = Path(path).read_bytes()
    if len(raw) > 20_000_000:
        raise ValueError('Plik napisów jest zbyt duży (20 MB).')
    if encoding:
        text = raw.decode(encoding)
    else:
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            match = from_bytes(raw).best()
            if match is None:
                raise ValueError('Nie rozpoznano kodowania. Wybierz je ręcznie.')
            text = str(match)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if Path(path).suffix.lower() == '.sbv':
        result = []
        for block in re.split(r'\n\s*\n', text.strip()):
            timing, _, body = block.partition('\n')
            values = timing.split(',')
            if len(values) != 2:
                raise ValueError('Nieprawidłowy plik SBV.')
            def timestamp(value):
                h, m, s = value.strip().split(':')
                return round((int(h)*3600+int(m)*60+float(s))*1000)
            result.append(Segment(timestamp(values[0]), timestamp(values[1]), body))
        return result
    if Path(path).suffix.lower() == '.txt' and '-->' not in text and not re.search(r'\[\d+\]\[\d+\]', text):
        return [Segment(text=line, timed=False) for line in text.splitlines() if line.strip()]
    subs = pysubs2.SSAFile.from_string(text, fps=fps)
    return [Segment(s.start, s.end, s.plaintext.replace('\r\n','\n')) for s in subs if not s.is_comment]


def write(segments, path):
    if any(not s.timed or s.end <= s.start or s.start < 0 for s in segments):
        raise ValueError('Nadaj poprawne czasy wszystkim segmentom przed eksportem.')
    subs = pysubs2.SSAFile()
    subs.events = [pysubs2.SSAEvent(start=s.start, end=s.end, text=s.text.replace('\n', r'\N')) for s in segments]
    subs.save(str(path), encoding='utf-8')


def shift(segments, ms):
    if any(s.start + ms < 0 for s in segments):
        raise ValueError('Przesunięcie spowodowałoby ujemny czas.')
    for s in segments:
        s.start += ms
        s.end += ms
        for w in s.words:
            w['start'] += ms
            w['end'] += ms


def stretch(segments, a, b, target_a, target_b):
    if b <= a or target_b <= target_a:
        raise ValueError('Punkty odniesienia muszą rosnąć.')
    scale = (target_b-target_a)/(b-a)
    convert = lambda t: round(target_a+(t-a)*scale)
    if any(convert(s.start) < 0 for s in segments):
        raise ValueError('Wynik zawiera ujemne czasy.')
    for s in segments:
        s.start, s.end = convert(s.start), convert(s.end)
        for w in s.words:
            w['start'], w['end'] = convert(w['start']), convert(w['end'])


def warnings(segments, duration, cps=22, line=42, minimum=600):
    overlaps = overlap_flags(segments)
    out = []
    for index, s in enumerate(segments):
        errors = []
        if not s.timed:
            errors.append('Brak czasów / Untimed')
        if s.start < 0 or s.end <= s.start:
            errors.append('Nieprawidłowy czas / Invalid time')
        elif s.end-s.start < minimum:
            errors.append('Krótki / Short')
        if duration and s.end > duration:
            errors.append('Poza filmem / Outside video')
        if any(len(l) > line for l in s.text.splitlines()):
            errors.append('Długi wiersz / Long line')
        if len(s.text)/max(.001, (s.end-s.start)/1000) > cps:
            errors.append('Za szybko / Too fast')
        if overlaps[index]:
            errors.append('Nakładanie / Overlap')
        out.append('; '.join(errors))
    return out


def overlap_flags(segments):
    flags = [False] * len(segments)
    maximum, owner = float('-inf'), None
    for index in sorted(range(len(segments)), key=lambda i: segments[i].start):
        segment = segments[index]
        if segment.end <= segment.start:
            continue
        if segment.start < maximum:
            flags[index] = flags[owner] = True
        if segment.end > maximum:
            maximum, owner = segment.end, index
    return flags
