from pathlib import Path
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QImage, QPen, QPolygonF
from core.compositor.render import compose, fit_frame, banner_geometry, position
from math import floor, log10


# Approximate areas covered by each platform's interface, as margins in % of the frame
# (left, top, right, bottom). They are guides, not official specifications.
SAFE_AREAS = {
    'tv': {'label': 'Bezpieczny obszar tytułów (90%) / Title safe', 'margins': (5, 5, 5, 5)},
    'tiktok': {'label': 'TikTok (orientacyjnie / approximate)', 'margins': (6, 8, 13, 20)},
    'reels': {'label': 'Instagram Reels (orientacyjnie / approximate)', 'margins': (6, 11, 10, 22)},
    'shorts': {'label': 'YouTube Shorts (orientacyjnie / approximate)', 'margins': (6, 8, 12, 20)},
}


class Preview(QWidget):
    moved = Signal(float, float)
    resized = Signal(float, float)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = QImage()
        self.project = None
        self.ms = 0
        self.output_size = None
        self.rect = QRectF()
        self.banner_index = -1
        self._resizing_banner = False
        self.safe_area = None
        self.framing = None  # (width, height, 'fit'|'crop', crop_x) while previewing another format
        self.setMinimumSize(320, 160)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.contentsRect(), QColor('#101218'))
        if self.frame.isNull():
            p.setPen(QColor('#8792a5'))
            p.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignCenter, 'SUBTITLE STUDIO\n\nImportuj film · Import video')
        else:
            frame = self.frame
            if self.output_size:
                frame = fit_frame(frame, *self.output_size)
            elif self.framing:
                # Editing preview of a vertical/other export: same crop as the worker.
                width, height, mode, crop_x = self.framing
                scale = min(1.0, 960 / max(width, height))
                frame = fit_frame(frame, max(2, round(width*scale)), max(2, round(height*scale)), mode, crop_x)
            if self.project:
                frame = compose(frame, self.project, self.ms)
            size = frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            self.rect = QRectF((self.width()-size.width())/2, (self.height()-size.height())/2, size.width(), size.height())
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(self.rect, frame)
            if self.safe_area in SAFE_AREAS:
                self.draw_safe_area(p)
            if self.project and 0 <= self.banner_index < len(self.project.banners):
                banner = self.project.banners[self.banner_index]
                if banner.visible and banner.start <= self.ms < banner.end:
                    box = self.banner_rect()
                    p.setPen(QColor('#ffffff')); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(box)
                    p.fillRect(QRectF(box.right()-5,box.bottom()-5,10,10),QColor('#ffffff'))
        p.end()

    def draw_safe_area(self, p):
        """Guide only: never part of the exported video."""
        left, top, right, bottom = SAFE_AREAS[self.safe_area]['margins']
        r = self.rect
        safe = QRectF(r.left()+r.width()*left/100, r.top()+r.height()*top/100,
                      r.width()*(100-left-right)/100, r.height()*(100-top-bottom)/100)
        shade = QColor(255, 80, 80, 55)
        p.fillRect(QRectF(r.left(), r.top(), r.width(), safe.top()-r.top()), shade)
        p.fillRect(QRectF(r.left(), safe.bottom(), r.width(), r.bottom()-safe.bottom()), shade)
        p.fillRect(QRectF(r.left(), safe.top(), safe.left()-r.left(), safe.height()), shade)
        p.fillRect(QRectF(safe.right(), safe.top(), r.right()-safe.right(), safe.height()), shade)
        pen = QPen(QColor('#ffcf70')); pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(safe)
        p.drawText(safe.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                   SAFE_AREAS[self.safe_area]['label'])

    def mousePressEvent(self, event):
        box = self.banner_rect()
        self._resizing_banner = bool(not box.isNull() and
            QRectF(box.right()-10,box.bottom()-10,20,20).contains(event.position()))
        self.mouseMoveEvent(event)

    def banner_rect(self):
        if not self.project or not 0 <= self.banner_index < len(self.project.banners):
            return QRectF()
        banner = self.project.banners[self.banner_index]
        box, _ = banner_geometry(banner, self.rect.width(), self.rect.height(), self.ms)
        return box.translated(self.rect.left(), self.rect.top())

    def mouseReleaseEvent(self, event):
        self._resizing_banner = False

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.rect.contains(event.position()):
            x = (event.position().x()-self.rect.x())/self.rect.width()*100
            y = (event.position().y()-self.rect.y())/self.rect.height()*100
            if self._resizing_banner and 0 <= self.banner_index < len(self.project.banners):
                banner = self.project.banners[self.banner_index]
                # Size is stored unscaled; divide by the keyframe scale at this moment.
                cx, cy, scale = position(banner, self.ms)
                self.resized.emit(min(100,max(1,2*(x-cx)/scale)), min(100,max(1,2*(y-cy)/scale)))
            else:
                self.moved.emit(x,y)


class Timeline(QWidget):
    seek = Signal(int)
    segmentSelected = Signal(int, int)
    segmentEdited = Signal(int, int, int, int)
    zoomChanged = Signal(float)
    layerSelected = Signal(str, int)
    layerEdited = Signal(str, int, int, int, str)
    LANE = 16
    FOREVER = 2147483647

    def __init__(self):
        super().__init__()
        self.duration = 1
        self.ms = 0
        self.project = None
        self.wave = []
        self.zoom = 1.0
        self.snapping = True
        self.selection = None
        self.drag = None
        self.ghost = None
        self.layer_selection = None
        self.setMinimumHeight(130)
        self.setMouseTracking(True)

    def set_zoom(self, value):
        value = min(32.0, max(1.0, value))
        viewport = self.parentWidget()
        width = viewport.width() if viewport else 800
        self.zoom = value
        self.setMinimumWidth(0 if value == 1 else round(width * value))
        self.zoomChanged.emit(value)
        self.update()

    def x_at(self, ms):
        return ms / max(1, self.duration) * self.width()

    def time_at(self, x):
        return max(0, min(self.duration, round(x / max(1, self.width()) * self.duration)))

    def segment_rect(self, track, segment):
        return QRectF(self.x_at(segment.start), 70 + track * 24,
                      max(2, self.x_at(segment.end) - self.x_at(segment.start)), 20)

    def layers(self):
        """Logo and banner layers drawn as lanes below the caption tracks."""
        if not self.project:
            return []
        return ([('logo', i, layer) for i, layer in enumerate(self.project.logos)]
                + [('banner', i, layer) for i, layer in enumerate(self.project.banners)])

    def lanes_top(self):
        return 70 + len(self.project.tracks) * 24 + 6 if self.project else 70

    def required_height(self):
        return max(130, self.lanes_top() + len(self.layers()) * self.LANE + 8)

    def layer_rect(self, lane, layer, start=None, end=None):
        start = layer.start if start is None else start
        end = min(self.duration, layer.end if end is None else end)
        return QRectF(self.x_at(start), self.lanes_top() + lane * self.LANE,
                      max(2, self.x_at(end) - self.x_at(start)), self.LANE - 3)

    def layer_hit(self, point):
        for lane, (kind, index, layer) in enumerate(self.layers()):
            rect = self.layer_rect(lane, layer)
            if rect.adjusted(-4, 0, 4, 0).contains(point):
                if abs(point.x() - rect.left()) <= 6:
                    return kind, index, 'start'
                if abs(point.x() - rect.right()) <= 6 and layer.end <= self.duration:
                    return kind, index, 'end'
                return kind, index, 'move'
        return None

    def layer_drag(self, layer, mode, delta):
        """New (start, end) for a dragged layer; an open end ('until the video ends') stays open."""
        start, end = layer.start, layer.end
        open_end = end >= self.duration
        visible_end = min(end, self.duration)
        if mode == 'start':
            start = max(0, min(visible_end - 1, start + delta))
        elif mode == 'end':
            end = min(self.duration, max(start + 1, end + delta))
        elif open_end:
            start = max(0, min(self.duration - 1, start + delta))
        else:
            length = end - start
            start = max(0, min(self.duration - length, start + delta))
            end = start + length
        return start, end

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(event.rect(), QColor('#171c26'))
        duration = max(1, self.duration)
        visible = event.rect()
        raw_step = max(1,duration / max(10,self.width()/100))
        magnitude = 10**floor(log10(raw_step))
        step = next(value*magnitude for value in (1,2,5,10) if value*magnitude >= raw_step)
        first_tick = max(0, int(self.time_at(visible.left()) / step) - 1)
        last_tick = int(self.time_at(visible.right()) / step) + 2
        p.setPen(QColor('#768298'))
        for tick in range(first_tick, last_tick):
            ms = tick * step
            x = int(self.x_at(ms))
            p.drawLine(x, 0, x, self.height())
            p.drawText(x + 3, 15, f'{ms/1000:.2f}s')
        if self.project:
            start = self.project.range_start
            end = self.project.range_end or self.duration
            p.fillRect(QRectF(self.x_at(start), 18, self.x_at(end-start), 5), QColor('#38bda0'))
        p.setPen(QColor('#426983'))
        for i, value in enumerate(self.wave):
            x = int(i / max(1, len(self.wave)) * self.width())
            if visible.left() <= x <= visible.right():
                p.drawLine(x, 44-int(value*18), x, 44+int(value*18))
        if self.project:
            for track_index, track in enumerate(self.project.tracks):
                if not track.visible:
                    continue
                for row, segment in enumerate(track.segments):
                    rect = self.segment_rect(track_index, segment)
                    if not rect.intersects(QRectF(visible)):
                        continue
                    p.fillRect(rect, QColor('#7e83ff'))
                    p.setPen(QColor('#ffffff'))
                    p.drawText(rect.adjusted(5, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter,
                               segment.text.replace('\n', ' ')[:80])
                    if self.selection == (track_index, row):
                        p.setPen(QColor('#ffcf70'))
                        p.drawRect(rect)
            colors = {'logo': QColor('#3cbea0'), 'banner': QColor('#b07cff')}
            for lane, (kind, index, layer) in enumerate(self.layers()):
                start, end = (self.ghost[2], self.ghost[3]) if (
                    self.ghost and self.ghost[0] == 'layer' and self.ghost[1] == (kind, index)) else (layer.start, layer.end)
                rect = self.layer_rect(lane, layer, start, end)
                color = QColor(colors[kind])
                if not layer.visible:
                    color.setAlpha(90)
                p.fillRect(rect, color)
                p.setPen(QColor('#0d1017'))
                label = ('Logo · ' + Path(layer.path).name) if kind == 'logo' else ('Baner · ' + layer.name)
                p.drawText(rect.adjusted(4, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, label)
                for frame in getattr(layer, 'keyframes', []):
                    x = self.x_at(frame['ms'])
                    middle = rect.center().y()
                    p.setBrush(QColor('#ffcf70')); p.setPen(QColor('#3b2a00'))
                    p.drawPolygon(QPolygonF([QPointF(x, middle-5), QPointF(x+4, middle),
                                             QPointF(x, middle+5), QPointF(x-4, middle)]))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                if self.layer_selection == (kind, index):
                    p.setPen(QColor('#ffcf70')); p.drawRect(rect)
        if self.ghost and self.ghost[0] != 'layer':
            track, start, end = self.ghost
            p.fillRect(QRectF(self.x_at(start), 70+track*24, self.x_at(end-start), 20), QColor('#a0ffcf70'))
        p.setPen(QColor('#ffcf70'))
        x = int(self.x_at(self.ms))
        p.drawLine(x, 0, x, self.height())
        p.end()

    def hit(self, point):
        if self.project:
            for track_index, track in enumerate(self.project.tracks):
                if track.visible:
                    for row in range(len(track.segments)-1, -1, -1):
                        segment = track.segments[row]
                        rect = self.segment_rect(track_index, segment)
                        if segment.timed and rect.adjusted(-4, 0, 4, 0).contains(point):
                            if abs(point.x() - rect.left()) <= 6:
                                mode = 'start'
                            elif abs(point.x() - rect.right()) <= 6:
                                mode = 'end'
                            else:
                                mode = 'move'
                            return track_index, row, mode
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self.hit(event.position())
        layer_hit = None if hit else self.layer_hit(event.position())
        if layer_hit:
            kind, index, mode = layer_hit
            self.layer_selection = (kind, index)
            self.drag = ('layer', (kind, index), mode, self.time_at(event.position().x()))
            self.layerSelected.emit(kind, index)
            self.update()
            return
        if hit:
            track, row, mode = hit
            segment = self.project.tracks[track].segments[row]
            self.selection = (track, row)
            self.drag = (track, row, mode, self.time_at(event.position().x()), segment.start, segment.end)
            self.seek.emit(self.time_at(event.position().x()))
            self.segmentSelected.emit(track, row)
            self.update()
        else:
            self.seek.emit(self.time_at(event.position().x()))

    def mouseMoveEvent(self, event):
        if self.drag and self.drag[0] == 'layer':
            if event.buttons() & Qt.MouseButton.LeftButton:
                _, (kind, index), mode, anchor = self.drag
                layers = self.project.logos if kind == 'logo' else self.project.banners
                if index < len(layers):
                    start, end = self.layer_drag(layers[index], mode, self.time_at(event.position().x()) - anchor)
                    self.ghost = ('layer', (kind, index), start, end)
                    self.update()
            return
        if self.drag and event.buttons() & Qt.MouseButton.LeftButton:
            track, row, mode, anchor, original_start, original_end = self.drag
            delta = self.time_at(event.position().x()) - anchor
            start, end = original_start, original_end
            if mode == 'start':
                start += delta
            elif mode == 'end':
                end += delta
            else:
                start += delta
                end += delta
            if self.snapping:
                candidates = [0, self.duration, self.ms]
                for index, segment in enumerate(self.project.tracks[track].segments):
                    if index != row:
                        candidates.extend([segment.start, segment.end])
                edges = [start] if mode == 'start' else [end] if mode == 'end' else [start, end]
                adjustment = min((target-edge for edge in edges for target in candidates), key=abs)
                if abs(adjustment) <= max(1, self.duration*8/self.width()):
                    if mode != 'end':
                        start += adjustment
                    if mode != 'start':
                        end += adjustment
            if mode == 'start':
                start = max(0, min(end-1, start))
            elif mode == 'end':
                end = min(self.duration, max(start+1, end))
            else:
                length = original_end-original_start
                start = max(0, min(self.duration-length, start))
                end = start+length
            self.ghost = (track, start, end)
            self.update()
        elif event.buttons() & Qt.MouseButton.LeftButton:
            self.seek.emit(self.time_at(event.position().x()))
        else:
            hit = self.hit(event.position()) or self.layer_hit(event.position())
            cursor = Qt.CursorShape.ArrowCursor
            if hit:
                cursor = Qt.CursorShape.OpenHandCursor
                if hit[2] != 'move':
                    cursor = Qt.CursorShape.SizeHorCursor
            self.setCursor(cursor)

    def mouseReleaseEvent(self, event):
        if self.drag and self.drag[0] == 'layer':
            if self.ghost and self.ghost[0] == 'layer':
                _, (kind, index), start, end = self.ghost
                self.layerEdited.emit(kind, index, start, end, self.drag[2])
            self.drag = None
            self.ghost = None
            self.update()
            return
        if self.drag and self.ghost:
            track, row, mode, anchor, start, end = self.drag
            _, new_start, new_end = self.ghost
            if new_end > new_start and (start, end) != (new_start, new_end):
                self.segmentEdited.emit(track, row, new_start, new_end)
        self.drag = None
        self.ghost = None
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom * (1.5 if event.angleDelta().y() > 0 else 1/1.5))
            event.accept()
        else:
            event.ignore()
