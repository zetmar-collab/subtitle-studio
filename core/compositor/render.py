from functools import lru_cache
from math import ceil
import re
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QFont, QFontMetricsF, QPainterPath, QColor, QPen


@lru_cache(maxsize=32)
def image(path):
    img = QImage(path)
    if img.isNull() or img.width()*img.height() > 80_000_000:
        raise ValueError('Nie można odczytać grafiki lub jest zbyt duża.')
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


def draw_text(p, segment, style, ms, width, height):
    text = visible_text(segment.text)
    elapsed = ms-segment.start
    duration = segment.end-segment.start
    animation = min(style.animation_ms, duration)
    progress = min(1, elapsed/max(1, animation))
    if style.effect == 'typewriter':
        text = text[:ceil(len(text)*progress)]
    elif style.effect == 'words':
        words = text.split()
        text = ' '.join(words[:max(1, ceil(len(words)*progress))])
    if not text:
        return
    scale = height/1080
    font = QFont(style.font)
    font.setPixelSize(max(8, round(style.size*scale)))
    font.setBold(style.bold)
    fm = QFontMetricsF(font)
    p.setFont(font)
    max_width = width*style.width/100
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split(' '):
            candidate = (line+' '+word).strip()
            if line and fm.horizontalAdvance(candidate) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
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
        opacity = min(1, elapsed/fade_duration, (segment.end-ms)/fade_duration)
    p.save()
    p.setOpacity(opacity)
    if style.effect == 'pop':
        p.translate(center_x, center_y)
        p.scale(.8+.2*progress, .8+.2*progress)
        p.translate(-center_x, -center_y)
    bg = QColor(style.background)
    if bg.alpha():
        box_width = max(fm.horizontalAdvance(l) for l in lines)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(center_x-box_width/2-12*scale, center_y-total_h/2-6*scale,
                                 box_width+24*scale, total_h+12*scale), 8*scale, 8*scale)
    # Word indices advance across wrapped lines; timing uses absolute media milliseconds.
    word_index = 0
    active = -1
    if style.effect == 'highlight':
        if segment.words:
            active = next((i for i, word in enumerate(segment.words) if word['start'] <= ms < word['end']), -1)
        else:
            active = int(elapsed * len(text.split()) / duration)
    for index, line in enumerate(lines):
        x = center_x-fm.horizontalAdvance(line)/2
        y = center_y-total_h/2+index*line_height+fm.ascent()
        for token in re.findall(r'\S+|\s+', line):
            path = QPainterPath()
            path.addText(QPointF(x, y), font, token)
            pen = QPen(QColor(style.outline), style.stroke*scale*2, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            color = style.active_color if style.effect == 'highlight' and active == word_index and not token.isspace() else style.color
            if style.stroke:
                p.strokePath(path,pen)
            p.fillPath(path,QColor(color))
            x += fm.horizontalAdvance(token)
            if not token.isspace():
                word_index += 1
    p.restore()
