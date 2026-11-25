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


def fit_frame(source, width, height, mode='fit', crop_x=50):
    """Place source in a width×height frame: 'fit' adds bars, 'crop' fills the frame.

    crop_x (0..100) chooses which horizontal part survives a crop, matching the
    FFmpeg crop expression used by the export worker."""
    out = QImage(width, height, QImage.Format.Format_RGB888)
    out.fill(Qt.GlobalColor.black)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    aspect = Qt.AspectRatioMode.KeepAspectRatio if mode == 'fit' else Qt.AspectRatioMode.KeepAspectRatioByExpanding
    scaled = source.size().scaled(width, height, aspect)
    left = (width-scaled.width())/2 if mode == 'fit' else (width-scaled.width())*crop_x/100
    p.drawImage(QRectF(left, (height-scaled.height())/2, scaled.width(), scaled.height()), source)
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
            x, y, scale = position(logo, ms)
            lw = w * logo.width / 100 * scale
            lh = lw * img.height() / img.width()
            p.setOpacity(logo.opacity / 100)
            p.drawImage(QRectF(w*x/100-lw/2, h*y/100-lh/2, lw, lh), img)
            p.setOpacity(1)
        for banner in project.banners:
            if banner.visible and banner.start <= ms < banner.end:
                draw_banner(p, banner, w, h, ms)
    finally:
        p.end()
    return out


_fit_cache = OrderedDict()
_fit_lock = RLock()


def fitted_size(banner, font, size, rect, flags):
    """Largest pixel size <= size whose wrapped text fits rect.

    Export calls this for every frame, so results are cached and the search is
    binary (about 9 measurements instead of up to several hundred)."""
    key = (banner.text, banner.font, banner.bold, size, round(rect.width(), 2), round(rect.height(), 2), flags)
    with _fit_lock:
        if key in _fit_cache:
            _fit_cache.move_to_end(key)
            return _fit_cache[key]
    def fits(value):
        font.setPixelSize(value)
        bounds = QFontMetricsF(font).boundingRect(rect, flags, banner.text)
        return bounds.height() <= rect.height() and bounds.width() <= rect.width()
    low, high = 1, size
    if not fits(high):
        while low < high:
            middle = (low + high + 1) // 2
            if fits(middle):
                low = middle
            else:
                high = middle - 1
    with _fit_lock:
        _fit_cache[key] = high
        while len(_fit_cache) > 512:
            _fit_cache.popitem(last=False)
    return high


def position(layer, ms):
    """Center (x %, y %) and scale factor of a logo/banner at ms.

    Without keyframes this is the static position. With keyframes the value is
    linearly interpolated and held before the first and after the last key."""
    frames = getattr(layer, 'keyframes', None)
    if not frames:
        return layer.x, layer.y, 1.0
    if ms <= frames[0]['ms']:
        frame = frames[0]
        return frame['x'], frame['y'], frame['scale'] / 100
    for before, after in zip(frames, frames[1:]):
        if ms < after['ms']:
            t = (ms - before['ms']) / (after['ms'] - before['ms'])
            return tuple(before[key] + (after[key] - before[key]) * t for key in ('x', 'y')) + (
                (before['scale'] + (after['scale'] - before['scale']) * t) / 100,)
    frame = frames[-1]
    return frame['x'], frame['y'], frame['scale'] / 100


def banner_motion(banner, ms):
    """Entrance/exit animation: (opacity factor, dx, dy as fraction of size, scale factor)."""
    if banner.animation == 'none' or ms is None:
        return 1.0, 0.0, 0.0, 1.0
    progress = min(1.0, max(0.0, (ms - banner.start) / banner.animation_ms),
                   max(0.0, (banner.end - ms) / banner.animation_ms))
    eased = 1 - (1 - progress) ** 3
    rest = 1 - eased
    offsets = {'slide_up': (0, rest), 'slide_down': (0, -rest), 'slide_left': (rest, 0), 'slide_right': (-rest, 0)}
    dx, dy = offsets.get(banner.animation, (0, 0))
    scale = 0.6 + 0.4 * eased if banner.animation == 'pop' else 1.0
    return eased, dx, dy, scale


def banner_geometry(banner, width, height, ms=None):
    """Rectangle of the banner background in output pixels at ms (keyframes + animation)."""
    x, y, key_scale = position(banner, ms if ms is not None else banner.start)
    _, dx, dy, pop = banner_motion(banner, ms)
    bw = width * banner.width / 100 * key_scale * pop
    bh = height * banner.height / 100 * key_scale * pop
    cx, cy = width * x / 100 + dx * bw, height * y / 100 + dy * bh
    return QRectF(cx - bw / 2, cy - bh / 2, bw, bh), key_scale * pop


def draw_banner(p, banner, width, height, ms=None):
    """Render the same explicit rectangle in preview and encoded frames."""
    rect, factor = banner_geometry(banner, width, height, ms)
    bw, bh = rect.width(), rect.height()
    scale = height / 1080 * factor
    fade = banner_motion(banner, ms)[0]
    p.save()
    try:
        p.setOpacity(banner.opacity / 100 * fade)
        p.setBrush(QColor(banner.background))
        p.setPen(QPen(QColor(banner.border_color), banner.border_width * scale)
                 if banner.border_width else Qt.PenStyle.NoPen)
        radius = min(banner.radius * scale, bw / 2, bh / 2)
        p.drawRoundedRect(rect, radius, radius)
        pad = min(banner.padding * scale, bw / 3, bh / 3)
        text_rect = rect.adjusted(pad, pad, -pad, -pad)
        p.setClipRect(text_rect)
        font = QFont(banner.font)
        font.setBold(banner.bold)
        size = max(1, round(banner.font_size * scale))
        flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignVCenter | {
            'left': Qt.AlignmentFlag.AlignLeft, 'center': Qt.AlignmentFlag.AlignHCenter,
            'right': Qt.AlignmentFlag.AlignRight}[banner.align]
        if banner.auto_fit:
            size = fitted_size(banner, font, size, text_rect, int(flags))
        font.setPixelSize(size)
        p.setFont(font)
        p.setPen(QColor(banner.color))
        p.drawText(text_rect, int(flags), banner.text)
    finally:
        p.restore()


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
