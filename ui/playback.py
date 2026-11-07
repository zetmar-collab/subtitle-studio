"""Offer playback without blocking render cleanup or starting another job."""
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox


def play_video(parent, target, translate):
    path = Path(target).resolve()
    if not path.is_file():
        QMessageBox.warning(parent, translate('Nie znaleziono filmu', 'Video not found'),
                            translate('Plik został przeniesiony lub usunięty. Sprawdź folder eksportu.',
                                      'The file was moved or deleted. Check the export folder.'))
        return False
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        QMessageBox.warning(parent, translate('Nie można odtworzyć filmu', 'Cannot play video'),
                            translate('Wybierz domyślny odtwarzacz filmów w ustawieniach Windows i spróbuj ponownie.',
                                      'Choose a default video player in Windows settings and try again.'))
        return False
    return True


def offer_playback(parent, target, translate):
    # Capture this export's path; a later export must not change the answer's target.
    path = str(Path(target).resolve())
    box = QMessageBox(parent)
    box.setWindowTitle(translate('Film gotowy', 'Video ready'))
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(translate('Eksport zakończony. Czy odtworzyć film?',
                          'Export complete. Play the video now?'))
    box.setInformativeText(Path(path).name + '\n' + translate(
        'Film otworzy się w domyślnym odtwarzaczu systemowym.',
        'The video will open in your default system player.'))
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    box.button(QMessageBox.StandardButton.Yes).setText(translate('Odtwórz film', 'Play video'))
    box.button(QMessageBox.StandardButton.No).setText(translate('Nie teraz', 'Not now'))
    box.finished.connect(lambda result: play_video(parent, path, translate)
                         if result == QMessageBox.StandardButton.Yes else None)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.setWindowModality(Qt.WindowModality.NonModal)
    box.show()
    return box
