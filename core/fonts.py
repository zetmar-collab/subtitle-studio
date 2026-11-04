"""Qt offscreen uses a different font database on Windows; populate it explicitly."""
import os
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QGuiApplication, QFont


def initialize_fonts():
    if os.name == 'nt' and not QFontDatabase.families():
        folders = [Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts',
                   Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft/Windows/Fonts']
        for folder in folders:
            if folder.is_dir():
                for path in folder.iterdir():
                    if path.suffix.lower() in ('.ttf','.otf','.ttc'):
                        QFontDatabase.addApplicationFont(str(path))
    if 'Segoe UI' in QFontDatabase.families():
        QGuiApplication.setFont(QFont('Segoe UI',9))
