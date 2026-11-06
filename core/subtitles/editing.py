"""Subtitle timeline operations. Inputs remain intact if validation fails."""
from copy import deepcopy
from core.subtitles.service import shift


def duplicate(segments, rows, duration=0):
    selected = [segments[row] for row in sorted(set(rows))]
    if not selected:
        return deepcopy(segments), []
    if any(not s.timed or s.end <= s.start for s in selected):
        raise ValueError('Najpierw ustaw poprawne czasy zaznaczonych napisów.')
    offset = max(s.end for s in selected) - min(s.start for s in selected)
    copies = deepcopy(selected)
    shift(copies, offset)
    if duration and max(s.end for s in copies) > duration:
        raise ValueError('Duplikat wykracza poza film. Przesuń zaznaczone napisy wcześniej.')
    result = deepcopy(segments) + copies
    result.sort(key=lambda s: s.start)
    return result, [i for i, s in enumerate(result) if any(s is copy for copy in copies)]


def ripple_delete(segments, rows):
    rows = set(rows)
    intervals = sorted((s.start, s.end) for i, s in enumerate(segments) if i in rows)
    if any(start < 0 or end <= start for start, end in intervals):
        raise ValueError('Najpierw ustaw poprawne czasy zaznaczonych napisów.')
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    result = []
    for i, original in enumerate(segments):
        if i in rows:
            continue
        if any(start < original.end and end > original.start for start, end in merged):
            raise ValueError('Inny napis nakłada się na usuwany przedział. Użyj zwykłego usunięcia lub rozdziel segmenty.')
        item = deepcopy(original)
        removed = sum(end-start for start, end in merged if end <= item.start)
        shift([item], -removed)
        result.append(item)
    return result
