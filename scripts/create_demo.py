from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import subprocess
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont
from PySide6.QtCore import Qt
from core.media.tools import binary, FLAGS
from core.projects.model import Project, Segment, Logo, save
from core.subtitles.service import write

app = QGuiApplication.instance() or QGuiApplication([])
root = Path(__file__).resolve().parents[1]/'examples'
root.mkdir(exist_ok=True)
video = root/'Film demonstracyjny.mp4'
subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','testsrc2=size=1920x1080:rate=24',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','8',
                '-c:v','libx264','-preset','ultrafast','-crf','24','-c:a','aac',str(video)],check=True,creationflags=FLAGS)
logo = QImage(320,110,QImage.Format.Format_ARGB32); logo.fill(Qt.GlobalColor.transparent)
painter = QPainter(logo); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
painter.setBrush(QColor('#a4a7ff')); painter.setPen(Qt.PenStyle.NoPen); painter.drawRoundedRect(logo.rect(),20,20)
font = QFont('Segoe UI',24); font.setBold(True); painter.setFont(font); painter.setPen(QColor('#10141d'))
painter.drawText(logo.rect(),Qt.AlignmentFlag.AlignCenter,'TWOJE LOGO'); painter.end()
logo_path = root/'Logo przezroczyste.png'; logo.save(str(logo_path))
project = Project(video=str(video.resolve()),logos=[Logo(path=str(logo_path.resolve()),width=18,opacity=75)])
project.tracks[0].name = 'Polskie napisy'
project.tracks[0].style.effect = 'highlight'
project.tracks[0].style.size = 64
project.tracks[0].segments = [
    Segment(500,3000,'Twój film. Twoje napisy.',words=[dict(text='Twój',start=500,end=1000),dict(text='film.',start=1000,end=1600),dict(text='Twoje',start=1600,end=2200),dict(text='napisy.',start=2200,end=3000)]),
    Segment(3500,7500,'Zażółć gęślą jaźń — działamy lokalnie.'),
]
save(project,root/'Demo.subtitlelogo.json')
write(project.tracks[0].segments,root/'Polskie napisy.srt')
(root/'Tekst bez czasów.txt').write_text('Tu ustaw własny początek i koniec.\nTen tekst nie jest automatycznie zsynchronizowany.',encoding='utf-8')
print(root)
