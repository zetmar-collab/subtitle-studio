"""Render the editable application vector into Windows ICO sizes and a PNG preview."""
from pathlib import Path
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer
from PIL import Image

root = Path(__file__).resolve().parents[1]
app = QGuiApplication.instance() or QGuiApplication([])
frame = QImage(512,512,QImage.Format.Format_ARGB32)
frame.fill(Qt.GlobalColor.transparent)
renderer = QSvgRenderer(str(root/'assets/icon.svg'))
assert renderer.isValid()
painter = QPainter(frame)
renderer.render(painter)
painter.end()
assert frame.save(str(root/'assets/icon.png'))
with Image.open(root/'assets/icon.png') as img:
    img.save(root/'assets/icon.ico',sizes=[(s,s) for s in (16,20,24,32,40,48,64,128,256)])
print(root/'assets/icon.ico')
