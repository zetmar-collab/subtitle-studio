from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QImage
from core.compositor.render import compose, fit_frame
from math import floor, log10


class Preview(QWidget):
    moved = Signal(float, float)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = QImage()
        self.project = None
        self.ms = 0
        self.output_size = None
        self.rect = QRectF()
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
            if self.project:
                frame = compose(frame, self.project, self.ms)
            size = frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            self.rect = QRectF((self.width()-size.width())/2, (self.height()-size.height())/2, size.width(), size.height())
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(self.rect, frame)
        p.end()

    def mousePressEvent(self, event):
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.rect.contains(event.position()):
            self.moved.emit((event.position().x()-self.rect.x())/self.rect.width()*100,
                            (event.position().y()-self.rect.y())/self.rect.height()*100)


class Timeline(QWidget):
    seek = Signal(int)
    segmentSelected = Signal(int, int)
    segmentEdited = Signal(int, int, int, int)
    zoomChanged = Signal(float)

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
            for logo in self.project.logos:
                if logo.visible:
                    p.fillRect(QRectF(self.x_at(logo.start), self.height()-10,
                                      max(2, self.x_at(min(duration, logo.end)-logo.start)), 6), QColor('#3cbea0'))
        if self.ghost:
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
            hit = self.hit(event.position())
            cursor = Qt.CursorShape.ArrowCursor
            if hit:
                cursor = Qt.CursorShape.OpenHandCursor
                if hit[2] != 'move':
                    cursor = Qt.CursorShape.SizeHorCursor
            self.setCursor(cursor)

    def mouseReleaseEvent(self, event):
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
