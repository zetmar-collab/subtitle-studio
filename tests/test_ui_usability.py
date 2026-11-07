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
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: (urls.append(url.toLocalFile()), True)[1])
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


def test_playback_requires_confirmation_and_keeps_original_export_path(host, app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtGui import QDesktopServices
    from ui.playback import offer_playback
    from PySide6.QtCore import Qt
    first = tmp_path / 'film z napisami ą.mp4'
    first.write_bytes(b'video')
    calls = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: (calls.append(url.toLocalFile()), True)[1])
    box = offer_playback(host.editor, first, host.editor.tr_text)
    assert box.windowModality() == Qt.WindowModality.NonModal
    assert calls == [] and box.defaultButton() == box.button(QMessageBox.StandardButton.No)
    host.editor.export_target = str(tmp_path / 'other.mp4')
    box.done(QMessageBox.StandardButton.Yes)
    app.processEvents()
    assert list(map(Path, calls)) == [first]
    box = offer_playback(host.editor, first, host.editor.tr_text)
    box.done(QMessageBox.StandardButton.No)
    assert len(calls) == 1


def test_missing_file_or_failed_player_has_recovery_message(host, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtGui import QDesktopServices
    from ui.playback import play_video
    warnings, launches = [], []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: (launches.append(url), False)[1])
    target = tmp_path / 'missing.mp4'
    assert not play_video(host.editor, target, host.editor.tr_text)
    assert not launches and 'folder' in warnings[-1]
    target.write_bytes(b'video')
    assert not play_video(host.editor, target, host.editor.tr_text)
    assert len(launches) == 1 and 'Windows' in warnings[-1]


def test_help_from_transcription_shortcuts_and_offline_navigation(host, app):
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtTest import QTest
    host.show()
    speech = host.speech()
    host.tabs.setCurrentIndex(1)
    speech.table.setFocus()
    app.processEvents()
    QTest.keyClick(speech.table, Qt.Key.Key_F1)
    app.processEvents()
    dialog = host.editor.help_dialog
    assert dialog.isVisible()
    assert 'Skróty klawiszowe' in dialog.browser.toPlainText()
    dialog.follow_link(QUrl('OLLAMA.md'))
    assert dialog.current == 'OLLAMA.md'
    dialog.go_back()
    assert dialog.current == 'POMOC.md'
    dialog.search.setText('Ctrl+Shift+Q')
    dialog.find_next()
    assert dialog.browser.textCursor().selectedText() == 'Ctrl+Shift+Q'
    dialog.show_file('POMOC.md', 'skroty')
    app.processEvents()
    assert dialog.browser.verticalScrollBar().value() > 0
    dialog.close()


def test_global_shortcuts_do_not_conflict_with_caption_exports_or_polish_input(host, app, monkeypatch):
    from PySide6.QtGui import QAction
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QFileDialog
    speech = host.speech()
    global_keys = [action.shortcut().toString() for action in host.findChildren(QAction)
                   if action.shortcutContext() == Qt.ShortcutContext.WindowShortcut and not action.shortcut().isEmpty()]
    assert len(global_keys) == len(set(global_keys))
    assert 'Ctrl+Shift+S' in global_keys
    assert not any(key.startswith('Ctrl+Alt+') for key in global_keys)
    exports = [action.shortcut().toString() for action in speech.shortcut_actions]
    assert 'Ctrl+Shift+E' in exports and 'Ctrl+Shift+S' not in exports
    paths = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (paths.append('save as'), ('', ''))[1])
    host.show()
    speech.table.setFocus()
    app.processEvents()
    QTest.keyClick(speech.table, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert paths == ['save as']


def test_no_playback_question_after_cancelled_or_failed_export(host, monkeypatch, tmp_path):
    from types import SimpleNamespace
    import json
    import ui.playback as playback
    from PySide6.QtWidgets import QMessageBox
    questions = []
    monkeypatch.setattr(playback, 'offer_playback', lambda *args: questions.append(args))
    monkeypatch.setattr(QMessageBox, 'open', lambda self: None)
    for cancelled in (False, True):
        editor = host.editor
        editor.export_status = tmp_path / 'status.json'
        editor.export_status.write_text(json.dumps({'error': 'failure'}))
        editor.export_cancel = tmp_path / 'cancel'
        if cancelled:
            editor.export_cancel.touch()
        editor.export_process = SimpleNamespace(deleteLater=lambda: None)
        editor.export_temp = SimpleNamespace(cleanup=lambda: None)
        editor.finish_export(1, None)
    assert questions == []


def test_queue_offers_only_last_result_after_the_whole_series(host, tmp_path):
    from types import SimpleNamespace
    import json
    from core.export.queue import ExportQueue
    queue = ExportQueue(host, tmp_path / 'queue.exports.json')
    queue.timer.stop()
    queue.jobs = [dict(target=str(tmp_path / name), state='queued', percent=0, error='')
                  for name in ('first.mp4', 'last.mp4')]
    results = []
    queue.completed.connect(results.append)
    queue.running = True
    queue.status = tmp_path / 'status.json'
    queue.status.write_text(json.dumps({'done': True}))
    queue.cancel_path = tmp_path / 'cancel'
    for job in queue.jobs:
        queue.current = job
        queue.process = SimpleNamespace(deleteLater=lambda: None)
        queue.temp = SimpleNamespace(cleanup=lambda: None)
        queue.finish(0, None)
        assert results == []
    queue.poll()
    queue.poll()
    assert results == [str(tmp_path / 'last.mp4')]
    assert not queue.running
    queue.release()


def test_media_creator_offers_playback_after_cleanup(host, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from ui.media_job import MediaJobDialog
    import ui.playback as playback
    class Creator(MediaJobDialog):
        def begin(self):
            pass
    dialog = Creator(host.editor)
    dialog.add_job_controls('Start')
    dialog.target = str(tmp_path / 'created.mp4')
    dialog.read_status = lambda: {'done': True}
    dialog.process = SimpleNamespace(deleteLater=lambda: None)
    dialog.temp = SimpleNamespace(cleanup=lambda: None)
    calls = []
    monkeypatch.setattr(playback, 'offer_playback', lambda parent, target, translate:
                        calls.append((target, parent.process, parent.temp)))
    dialog.finish_job(0, None)
    assert calls == [(dialog.target, None, None)]
    dialog.close()


def test_help_is_usable_inside_modal_export_dialog(host, app):
    from ui.export_dialog import ExportDialog
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    host.show()
    dialog = ExportDialog(host.editor)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.show()
    dialog.quality.setFocus()
    app.processEvents()
    QTest.keyClick(dialog.quality, Qt.Key.Key_F1)
    app.processEvents()
    assert dialog.help_dialog.isVisible()
    assert dialog.help_dialog.parent() is dialog
    dialog.help_dialog.close()
    dialog.reject()
