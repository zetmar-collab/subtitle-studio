"""Regression checks for the shared desktop interface and export choices."""
from pathlib import Path
import pytest
from PySide6.QtCore import QSettings, QCoreApplication, QEvent
from PySide6.QtWidgets import QCheckBox
from core.projects.model import Logo
from srtstudio.project import Segment as SpeechSegment


@pytest.fixture
def host(app, monkeypatch, tmp_path):
    import ui.window as editor_ui
    import srtstudio.ui as speech_ui
    from ui.workspace import Workspace
    monkeypatch.setenv('SZEPT_DATA_DIR', str(tmp_path / 'speech'))
    monkeypatch.setattr(editor_ui.Window, 'recover', lambda self: None)
    monkeypatch.setattr(speech_ui.Window, 'recover', lambda self: None)
    monkeypatch.setattr(speech_ui.Window, 'restart_spelling', lambda self: None)
    for module in (editor_ui, speech_ui):
        monkeypatch.setattr(module, 'QSettings', lambda *args: QSettings(str(tmp_path / 'ui.ini'), QSettings.Format.IniFormat))
    window = Workspace()
    window.editor.autotimer.stop()
    yield window
    window.editor.confirm_unsaved = lambda: True
    if window.transcription:
        window.transcription.confirm_save = lambda: True
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_language_theme_and_scale_keep_transcript_and_history(host, app):
    speech = host.speech()
    speech.project.segments = [SpeechSegment(0, 1, 'Zachowaj ten tekst')]
    speech.dirty = True
    speech.record()
    history = list(speech.history)
    app.processEvents()  # dispose of the old placeholder before changing language
    host.editor.lang.setCurrentIndex(1)
    host.editor.theme.setCurrentIndex(1)
    host.editor.interface_size.setCurrentIndex(2)
    assert host.tabs.tabText(1) == 'Speech recognition'
    assert speech.ui_language == 'en'
    assert speech.project.segments[0].text == 'Zachowaj ten tekst'
    assert speech.history == history and speech.dirty
    assert '#eef1f7' in speech.styleSheet() and 'font-size:18px' in speech.styleSheet()
    assert speech.styleSheet() == host.styleSheet() == host.editor.styleSheet()
    host.editor.lang.setCurrentIndex(0)
    assert host.editor.transport_buttons[0][0].accessibleName() == 'Poprzednia klatka'


def test_context_properties_hide_unrelated_controls_without_changing_style(host):
    editor = host.editor
    original = editor.track().style.size
    editor.project.logos.append(Logo(path='logo.png'))
    editor.active_logo = 0
    editor.show_properties()
    assert not editor.properties_form.isRowVisible(editor.font_combo)
    assert editor.properties_form.isRowVisible(editor.logo_width)
    editor.active_logo = -1
    editor.show_properties()
    assert editor.properties_form.isRowVisible(editor.font_combo)
    assert not editor.properties_form.isRowVisible(editor.logo_width)
    assert editor.track().style.size == original


def test_export_defaults_and_advanced_controls(host, app):
    from ui.export_dialog import ExportDialog
    dialog = ExportDialog(host.editor)
    dialog.show()
    app.processEvents()
    assert dialog.profile.currentIndex() == 0 and dialog.size.currentIndex() == 0
    assert dialog.crf.value() == 20 and not dialog.advanced.isVisible()
    dialog.quality.setCurrentIndex(1)
    assert dialog.crf.value() == 17
    toggle = next(box for box in dialog.findChildren(QCheckBox) if box.text() == 'Zaawansowane ustawienia')
    toggle.setChecked(True)
    assert dialog.advanced.isVisible()
    dialog.crf.setValue(23)
    assert dialog.crf.value() == 23
    dialog.reject()


def test_small_window_and_large_text_remain_scrollable(host, app):
    host.show()
    host.resize(1366, 768)
    app.processEvents()
    assert host.width() <= 1366 and host.height() <= 768
    speech = host.speech()
    host.editor.interface_size.setCurrentIndex(2)
    host.resize(1366, 768)
    app.processEvents()
    assert host.width() <= 1366 and host.height() <= 768
    assert speech.centralWidget().verticalScrollBar().maximum() > 0
    # Keep review artifacts alongside the automated checks, outside tracked source.
    output = Path('output/ux')
    output.mkdir(parents=True, exist_ok=True)
    host.grab().save(str(output / 'speech-large.png'))


def test_export_selected_range_and_quality_reach_worker(host, monkeypatch, tmp_path):
    from ui.export_dialog import ExportDialog
    from PySide6.QtWidgets import QFileDialog
    editor = host.editor
    editor.project.video = str(tmp_path / 'source.mp4')
    editor.info.update(width=1920, height=1080, duration=20000, fps=25)
    editor.project.range_start = 4000
    editor.project.range_end = 18000
    def accept(dialog):
        dialog.selected_range.setChecked(True)
        dialog.test.setChecked(True)
        dialog.quality.setCurrentIndex(1)
        return 1
    monkeypatch.setattr(ExportDialog, 'exec', accept)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'result.mp4'), ''))
    calls = []
    monkeypatch.setattr(editor, 'start_export', lambda target, options: calls.append(options))
    editor.export_video()
    assert calls[0]['start'] == 4 and calls[0]['seconds'] == 10
    assert calls[0]['crf'] == 17 and calls[0]['codec'] == 'libx264'


def test_successful_export_exposes_result_and_correct_folder(host, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from PySide6.QtGui import QDesktopServices
    import json
    editor = host.editor
    editor.export_target = str(tmp_path / 'gotowy film.mp4')
    Path(editor.export_target).write_bytes(b'result')
    editor.export_status = tmp_path / 'status.json'
    editor.export_status.write_text(json.dumps({'done': True, 'percent': 100}))
    editor.export_cancel = tmp_path / 'cancel'
    editor.export_process = SimpleNamespace(deleteLater=lambda: None)
    editor.export_temp = SimpleNamespace(cleanup=lambda: None)
    editor.finish_export(0, None)
    assert not editor.export_result.isHidden()
    assert 'gotowy film.mp4' in editor.export_result_label.text()
    urls = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: urls.append(url.toLocalFile()))
    editor.open_export()
    editor.open_export(True)
    assert list(map(Path, urls)) == [Path(editor.export_target), tmp_path]


def test_export_failure_offers_retry_after_worker_cleanup(host, app, monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from PySide6.QtWidgets import QMessageBox
    editor = host.editor
    editor.export_status = tmp_path / 'status.json'
    editor.export_status.write_text(json.dumps({'error': 'internal diagnostic'}))
    editor.export_cancel = tmp_path / 'cancel'
    cleaned = []
    editor.export_process = SimpleNamespace(deleteLater=lambda: cleaned.append('process'))
    editor.export_temp = SimpleNamespace(cleanup=lambda: cleaned.append('temporary files'))
    boxes = []
    monkeypatch.setattr(QMessageBox, 'open', lambda box: boxes.append(box))
    retries = []
    monkeypatch.setattr(editor, 'export_video', lambda: retries.append(editor.export_process))
    editor.finish_export(1, None)
    assert cleaned == ['process', 'temporary files']
    assert boxes[0].detailedText() == 'internal diagnostic'
    assert 'internal diagnostic' not in boxes[0].text()
    retry = next(button for button in boxes[0].buttons() if button.text() == 'Spróbuj ponownie…')
    retry.click()
    app.processEvents()
    assert retries == [None]
