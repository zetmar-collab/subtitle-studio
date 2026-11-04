from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QImage
from core.compositor.render import compose, fit_frame


class Preview(QWidget):
    moved = Signal(float, float)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = QImage()
        self.project = None
        self.ms = 0
        self.output_size = None
        self.rect = QRectF()
        self.setMinimumSize(400, 225)

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
    def __init__(self):
        super().__init__()
        self.duration = 1
        self.ms = 0
        self.project = None
        self.wave = []
        self.setMinimumHeight(100)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#171c26'))
        duration = max(1, self.duration)
        p.setPen(QColor('#768298'))
        for i in range(11):
            x = self.width()*i/10
            p.drawLine(int(x), 0, int(x), self.height())
            p.drawText(int(x)+3, 15, f'{duration*i/10000:.1f}s')
        p.setPen(QColor('#426983'))
        for i, value in enumerate(self.wave):
            x = int(i/max(1, len(self.wave))*self.width())
            p.drawLine(x, 42-int(value*20), x, 42+int(value*20))
        if self.project:
            for index, track in enumerate(self.project.tracks):
                if not track.visible:
                    continue
                for s in track.segments:
                    p.fillRect(QRectF(s.start/duration*self.width(), 68+index*12,
                                      max(2, (s.end-s.start)/duration*self.width()), 9), QColor('#7e83ff'))
            for logo in self.project.logos:
                if logo.visible:
                    p.fillRect(QRectF(logo.start/duration*self.width(), self.height()-12,
                                      max(2, (min(duration, logo.end)-logo.start)/duration*self.width()), 6), QColor('#3cbea0'))
        p.setPen(QColor('#ffcf70'))
        x = int(self.ms/duration*self.width())
        p.drawLine(x, 0, x, self.height())
        p.end()

    def mousePressEvent(self, event):
        self.seek.emit(round(event.position().x()/max(1, self.width())*self.duration))

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.mousePressEvent(event)
