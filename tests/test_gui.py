from core.projects.model import Segment
from ui.window import Window, timecode, parse_time


def test_new_project_toolbar_preserves_on_cancel_then_resets(app, monkeypatch, tmp_path):
    from PySide6.QtGui import QAction, QImage
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(Window, 'recover', lambda self: None)
    window = Window()
    window.autopath = tmp_path / 'recovery.json'
    window.autopath.write_text('{}')
    window.path = str(tmp_path / 'old.subtitlelogo.json')
    window.project.tracks[0].segments = [Segment(0, 500, 'Stary napis')]
    window.preview.frame = QImage(16, 16, QImage.Format.Format_RGB888)
    window.preview.output_size = (720, 1280)
    window.timeline.wave = [0.5]
    window.checkpoint()
    window.refresh()
    action = next(action for action in window.findChildren(QAction) if action.shortcut().toString() == 'Ctrl+N')
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Cancel)
    action.trigger()
    assert window.table.rowCount() == 1 and window.autopath.exists()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Discard)
    action.trigger()
    assert window.path is None and not window.dirty and not window.history
    assert window.table.rowCount() == 0 and not window.autopath.exists()
    assert window.preview.frame.isNull() and window.preview.output_size is None
    assert window.timeline.wave == [] and window.player.source().isEmpty()
    window.close()


def test_editor_undo_language_and_properties(app, monkeypatch, tmp_path):
    monkeypatch.setattr(Window,'recover',lambda self: None)
    w = Window()
    w.autotimer.stop()
    w.project.tracks[0].segments = [Segment(1000,2000,'Literuwka')]
    w.refresh()
    w.table.item(0,2).setText('Literówka')
    assert w.track().segments[0].text == 'Literówka'
    w.undo()
    assert w.track().segments[0].text == 'Literuwka'
    w.redo()
    assert w.track().segments[0].text == 'Literówka'
    w.lang.setCurrentIndex(1)
    assert w.project.language == 'en'
    assert w.table.horizontalHeaderItem(2).text() == 'Text'
    w.size.setValue(72)
    assert w.track().style.size == 72
    w.theme.setCurrentIndex(1)
    assert w.project.theme == 'light'
    w.dirty = False
    w.close()


def test_timecodes():
    assert timecode(3723456) == '01:02:03.456'
    assert parse_time('01:02:03.456') == 3723456
    assert parse_time('500') == 500


def test_offscreen_can_render_real_fonts(app):
    from PySide6.QtGui import QFontDatabase
    assert 'Arial' in QFontDatabase.families()


def test_background_job_delivers_result(app):
    import time
    from PySide6.QtCore import QThreadPool
    from ui.jobs import Job
    results = []
    QThreadPool.globalInstance().start(Job(lambda: 42,results.append,results.append))
    deadline = time.monotonic()+3
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert results == [42]


def test_gui_worker_pipeline(app,tmp_path,monkeypatch):
    import time
    from pathlib import Path
    from core.media.tools import probe
    from core.projects.model import load
    monkeypatch.setattr(Window,'recover',lambda self: None)
    w = Window(); w.autotimer.stop()
    errors = []; monkeypatch.setattr(w,'error',errors.append)
    demo = Path(__file__).resolve().parents[1]/'examples/Demo.subtitlelogo.json'
    w.project = load(demo); w.info = probe(w.project.video); w.refresh()
    target = tmp_path/'GUI render.mp4'
    w.start_export(str(target),dict(width=320,height=180,fps=12,seconds=1))
    deadline = time.monotonic()+30
    while w.export_process is not None and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.02)
    assert w.export_process is None
    assert errors == []
    assert target.exists()
    w.dirty = False; w.close()
