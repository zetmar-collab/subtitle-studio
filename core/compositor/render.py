from collections import OrderedDict
from threading import RLock
from math import ceil
import re
from PySide6.QtCore import Qt, QRectF, QPointF, QTextBoundaryFinder
from PySide6.QtGui import QImage, QImageReader, QPainter, QFont, QFontMetricsF, QPainterPath, QColor, QPen
from pathlib import Path


_images = OrderedDict()
_image_bytes = 0
IMAGE_CACHE_BYTES = 128 * 1024 * 1024
_image_lock = RLock()


def image(path):
    global _image_bytes
    source = Path(path)
    stat = source.stat()
    key = (str(source.resolve()),stat.st_mtime_ns,stat.st_size)
    with _image_lock:
        if key in _images:
            _images.move_to_end(key)
            return _images[key]
    reader = QImageReader(str(source)); reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width()*size.height() > 80_000_000:
        raise ValueError('Nie można odczytać grafiki lub jest zbyt duża.')
    if size.width()*size.height()*4 > IMAGE_CACHE_BYTES:
        from math import sqrt
        from PySide6.QtCore import QSize
        ratio = sqrt(IMAGE_CACHE_BYTES/(size.width()*size.height()*4))
        reader.setScaledSize(QSize(max(1,int(size.width()*ratio)),max(1,int(size.height()*ratio))))
    img = reader.read()
    if img.isNull():
        raise ValueError('Nie można odczytać grafiki lub jest zbyt duża.')
    with _image_lock:
        if key not in _images and img.sizeInBytes() <= IMAGE_CACHE_BYTES:
            while _images and _image_bytes + img.sizeInBytes() > IMAGE_CACHE_BYTES:
                _, old = _images.popitem(last=False)
                _image_bytes -= old.sizeInBytes()
            _images[key] = img
            _image_bytes += img.sizeInBytes()
    return img


def fit_frame(source, width, height):
    out = QImage(width, height, QImage.Format.Format_RGB888)
    out.fill(Qt.GlobalColor.black)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scaled = source.size().scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio)
    p.drawImage(QRectF((width-scaled.width())/2, (height-scaled.height())/2, scaled.width(), scaled.height()), source)
    p.end()
    return out


def compose(frame, project, ms):
    out = frame.convertToFormat(QImage.Format.Format_RGB888)
    w, h = out.width(), out.height()
    p = QPainter(out)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    try:
        for track in project.tracks:
            if not track.visible:
                continue
            for s in track.segments:
                if s.timed and s.start <= ms < s.end:
                    draw_text(p, s, track.style, ms, w, h)
        for logo in project.logos:
            if not logo.visible or not logo.start <= ms < logo.end:
                continue
            img = image(logo.path)
            lw = w * logo.width / 100
            lh = lw * img.height() / img.width()
            p.setOpacity(logo.opacity / 100)
            p.drawImage(QRectF(w*logo.x/100-lw/2, h*logo.y/100-lh/2, lw, lh), img)
            p.setOpacity(1)
    finally:
        p.end()
    return out


def visible_text(text):
    return re.sub(r'<[^>]+>|\{[^}]*\}', '', text)


def graphemes(text):
    """Qt boundaries use UTF-16 offsets; preserve emoji and combining marks."""
    raw = text.encode('utf-16-le')
    finder = QTextBoundaryFinder(QTextBoundaryFinder.BoundaryType.Grapheme, text)
    start = 0
    result = []
    while (end := finder.toNextBoundary()) >= 0:
        result.append(raw[start*2:end*2].decode('utf-16-le'))
        start = end
    # Some Qt builds split regional-indicator flags despite grouping ZWJ emoji.
    merged = []
    pending_flag = False
    for cluster in result:
        regional = len(cluster) == 1 and 0x1F1E6 <= ord(cluster) <= 0x1F1FF
        if regional and pending_flag:
            merged[-1] += cluster
            pending_flag = False
        else:
            merged.append(cluster)
            pending_flag = regional
    return merged


def aligned_words(segment, text):
    tokens = text.split()
    words = segment.words
    if len(words) != len(tokens):
        return []
    previous = segment.start
    for token, word in zip(tokens, words):
        start, end = word.get('start'), word.get('end')
        if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not segment.start <= start < end <= segment.end or start < previous):
            return []
        if 'text' in word and visible_text(word['text']).strip() != token:
            return []
        previous = end
    return words


def text_lines(text, fm, max_width):
    """Lay out the entire caption once per frame, independently of reveal progress."""
    lines = []
    word_index = 0
    paragraph_offset = 0
    for paragraph in text.split('\n'):
        line = []
        line_text = ''
        for match in re.finditer(r'\S+', paragraph):
            token = match.group()
            pieces = []
            piece = ''
            offset = paragraph_offset + match.start()
            for cluster in graphemes(token):
                if piece and fm.horizontalAdvance(piece + cluster) > max_width:
                    pieces.append((piece, offset))
                    offset += len(piece)
                    piece = ''
                piece += cluster
            if piece:
                pieces.append((piece, offset))
            for part, (piece, offset) in enumerate(pieces):
                gap = ' ' if line and part == 0 else ''
                if line and fm.horizontalAdvance(line_text + gap + piece) > max_width:
                    lines.append((line_text, line))
                    line = []; line_text = ''; gap = ''
                x = fm.horizontalAdvance(line_text + gap)
                line.append((piece, word_index, offset, x))
                line_text += gap + piece
            word_index += 1
        lines.append((line_text, line))
        paragraph_offset += len(paragraph) + 1
    return lines


def draw_text(p, segment, style, ms, width, height):
    text = visible_text(segment.text)
    duration = segment.end-segment.start
    if not text.strip() or duration <= 0 or not segment.start <= ms < segment.end:
        return
    elapsed = ms-segment.start
    animation = min(style.animation_ms, duration)
    progress = max(0, min(1, elapsed/max(1, animation)))
    words = aligned_words(segment, text)
    active = -1
    if style.effect == 'highlight':
        if words:
            # Retain the previous word in a pause instead of flashing all white.
            active = next((i for i in range(len(words)-1, -1, -1) if words[i]['start'] <= ms), -1)
        else:
            active = min(len(text.split())-1, int(elapsed * len(text.split()) / duration))
    revealed_words = len(text.split())
    revealed_chars = len(text)
    if style.effect == 'typewriter':
        clusters = graphemes(text)
        revealed_chars = len(''.join(clusters[:ceil(len(clusters)*progress)]))
        if not revealed_chars:
            return
    elif style.effect == 'words':
        revealed_words = (sum(word['start'] <= ms for word in words) if words
                          else max(1, ceil(len(text.split())*progress)))
        if not revealed_words:
            return
    scale = height/1080
    font = QFont(style.font)
    font.setPixelSize(max(8, round(style.size*scale)))
    font.setBold(style.bold)
    fm = QFontMetricsF(font)
    lines = text_lines(text, fm, width*style.width/100)
    line_height = fm.height()*1.12
    total_h = len(lines)*line_height
    center_x = width*style.x/100
    center_y = height*style.y/100
    if style.effect == 'left':
        center_x -= (1-progress)*width
    elif style.effect == 'right':
        center_x += (1-progress)*width
    elif style.effect == 'up':
        center_y += (1-progress)*height
    opacity = 1
    if style.effect == 'fade':
        fade_duration = max(1, min(style.animation_ms, duration / 2))
        opacity = max(0, min(1, elapsed/fade_duration, (segment.end-ms)/fade_duration))
    p.save()
    try:
        p.setFont(font)
        p.setOpacity(opacity)
        if style.effect == 'pop':
            p.translate(center_x, center_y)
            p.scale(.8+.2*progress, .8+.2*progress)
            p.translate(-center_x, -center_y)
        bg = QColor(style.background)
        if bg.alpha():
            box_width = max(fm.horizontalAdvance(line) for line, _ in lines)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(center_x-box_width/2-12*scale, center_y-total_h/2-6*scale,
                                     box_width+24*scale, total_h+12*scale), 8*scale, 8*scale)
        pen = QPen(QColor(style.outline), style.stroke*scale*2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        for index, (line, runs) in enumerate(lines):
            left = center_x-fm.horizontalAdvance(line)/2
            y = center_y-total_h/2+index*line_height+fm.ascent()
            for token, word_index, offset, x in runs:
                if word_index >= revealed_words:
                    continue
                shown = token[:max(0, revealed_chars-offset)]
                if not shown:
                    continue
                path = QPainterPath()
                path.addText(QPointF(left+x, y), font, shown)
                color = style.active_color if style.effect == 'highlight' and active == word_index else style.color
                if style.stroke:
                    p.strokePath(path, pen)
                p.fillPath(path, QColor(color))
    finally:
        p.restore()
