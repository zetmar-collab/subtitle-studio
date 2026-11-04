from pathlib import Path
import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from core.fonts import initialize_fonts
from ui.window import Window

app = QApplication([])
initialize_fonts()
app.setApplicationName('Subtitle Studio')
app.setOrganizationName('LocalTools')
w = Window()
w.open_project(str(root/'examples/Demo.subtitlelogo.json'))
w.show()
QTimer.singleShot(500,lambda: (w.player.play(),w.player.setPosition(1700)))
def capture():
    w.player.pause()
    w.grab().save(str(root/'docs/colors-ui.png'))
    def capture_dialog():
        dialog = app.activeModalWidget()
        if dialog:
            dialog.grab().save(str(root/'docs/color-picker.png'))
            dialog.reject()
        w.dirty = False
        QTimer.singleShot(0,app.quit)
    QTimer.singleShot(300,capture_dialog)
    w.color.click()
QTimer.singleShot(1400,capture)
app.exec()
