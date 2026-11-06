"""Shared desktop colours, sizing and interaction states."""
from pathlib import Path
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox


def apply_appearance(widget, theme='system', size=14):
    dark = theme == 'dark' or (theme == 'system' and
        QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    bg, panel, text, muted, border = (
        ('#10141d', '#1a2130', '#e9edf5', '#b1bed0', '#566277') if dark else
        ('#eef1f7', '#ffffff', '#202638', '#526078', '#8894a8'))
    accent = '#555bc0'
    focus = '#b4b8ff' if dark else '#4147a8'
    check = (Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'assets' / 'check.svg').as_posix()
    palette = QPalette()
    for role, value in [(QPalette.ColorRole.Window, bg), (QPalette.ColorRole.Base, panel),
                        (QPalette.ColorRole.AlternateBase, bg), (QPalette.ColorRole.WindowText, text),
                        (QPalette.ColorRole.Text, text), (QPalette.ColorRole.Button, panel),
                        (QPalette.ColorRole.ButtonText, text), (QPalette.ColorRole.Highlight, accent),
                        (QPalette.ColorRole.HighlightedText, '#ffffff')]:
        palette.setColor(role, QColor(value))
    widget.setPalette(palette)
    widget.setStyleSheet(f'''
        QWidget {{ background:{bg}; color:{text}; font-family:Segoe UI; font-size:{size}px; }}
        QToolBar, QMenuBar, QMenu, QTabWidget::pane {{ background:{bg}; border:0; }}
        QToolBar {{ spacing:6px; padding:4px; }}
        QPushButton, QToolButton {{ background:{panel}; border:1px solid {border}; border-radius:5px; padding:6px 9px; }}
        QPushButton:hover, QToolButton:hover {{ border-color:{focus}; }}
        QPushButton#primary, QToolButton#primary {{ background:{accent}; color:white; border-color:{accent}; font-weight:600; }}
        QPushButton#primary:disabled, QToolButton#primary:disabled {{ background:{panel}; color:{muted}; border-color:{border}; }}
        QPushButton:disabled, QToolButton:disabled {{ color:{muted}; border-color:{border}; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit,
        QListWidget, QTableWidget {{ background:{panel}; border:1px solid {border}; border-radius:4px;
            padding:3px; selection-background-color:{accent}; selection-color:white; }}
        QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus,
        QSpinBox:focus, QDoubleSpinBox:focus, QTableWidget:focus, QListWidget:focus,
        QTextEdit:focus, QPlainTextEdit:focus {{ border:2px solid {focus}; }}
        QCheckBox:focus, QSlider:focus {{ outline:2px solid {focus}; }}
        QCheckBox::indicator {{ width:16px; height:16px; border:1px solid {muted}; border-radius:3px; background:{panel}; }}
        QCheckBox::indicator:checked {{ background:{accent}; image:url("{check}"); }}
        QCheckBox::indicator:focus {{ border:2px solid {focus}; }}
        QHeaderView::section {{ background:{panel}; color:{text}; padding:5px; border:0; }}
        QTabBar::tab {{ background:{panel}; padding:6px 12px; border-bottom:2px solid transparent; }}
        QTabBar::tab:selected {{ border-bottom-color:{focus}; font-weight:600; }}
        QTabBar::tab:focus {{ border:2px solid {focus}; }}
        QSplitter::handle {{ background:{border}; }}
        QProgressBar {{ border:1px solid {border}; text-align:center; border-radius:4px; }}
        QProgressBar::chunk {{ background:{accent}; }}
        QSlider::groove:horizontal {{ background:{border}; height:4px; }}
        QSlider::handle:horizontal {{ background:{focus}; width:14px; margin:-5px 0; border-radius:6px; }}
        QLabel#muted {{ color:{muted}; }}
        QLabel#brand {{ font-size:20px; font-weight:700; }}
        QLabel#badge {{ color:{muted}; }}
        QLabel#source {{ background:{panel}; padding:6px; border:1px solid {border}; border-radius:4px; }}
        QPlainTextEdit {{ font-size:{size + 1}px; }}
    ''')


def show_error(parent, title, message, translate):
    """Keep diagnostics available without making them the main instruction."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    if isinstance(message, ValueError):
        text = str(message)
        if text.count(' / ') == 1 and '\n' not in text:
            pl, en = text.split(' / ', 1)
            text = translate(pl, en)
        box.setText(text)
    elif isinstance(message, Exception):
        box.setText(translate('Nie udało się wykonać tej czynności.', 'This action could not be completed.'))
        box.setInformativeText(translate(
            'Sprawdź, czy plik jest dostępny, i spróbuj ponownie. Szczegóły błędu są poniżej.',
            'Check that the file is available and try again. Error details are below.'))
        box.setDetailedText(str(message))
    else:
        text = str(message)
        if text.count(' / ') == 1 and '\n' not in text:
            pl, en = text.split(' / ', 1)
            text = translate(pl, en)
        box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
