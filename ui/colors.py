from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QPushButton


class ColorButton(QPushButton):
    """A checkerboard swatch makes both the color and its alpha visible."""

    def __init__(self, color='#ffffff', parent=None):
        super().__init__(parent)
        self.setIconSize(QSize(42, 22))
        self.setMinimumWidth(145)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_color(color)

    def color(self):
        return QColor(self._color)

    def value(self):
        form = QColor.NameFormat.HexArgb if self._color.alpha() < 255 else QColor.NameFormat.HexRgb
        return self._color.name(form)

    def set_color(self, value):
        color = QColor(value)
        if not color.isValid():
            raise ValueError('Invalid color')
        self._color = color
        swatch = QPixmap(42, 22)
        swatch.fill(Qt.GlobalColor.transparent)
        painter = QPainter(swatch)
        for y in range(0, 22, 6):
            for x in range(0, 42, 6):
                painter.fillRect(x, y, 6, 6, QColor('#eeeeee' if (x//6+y//6) % 2 else '#a0a0a0'))
        painter.fillRect(0, 0, 42, 22, color)
        painter.setPen(QPen(QColor('#727888'), 1))
        painter.drawRect(0, 0, 41, 21)
        painter.end()
        self.setIcon(QIcon(swatch))
        opacity = round(color.alphaF()*100)
        self.setText(self.value().upper()+(f' · {opacity}%' if opacity < 100 else ''))
        self.setToolTip(f'RGB: {color.red()}, {color.green()}, {color.blue()} · Krycie / Opacity: {opacity}%')
        self.setAccessibleDescription(self.toolTip())
