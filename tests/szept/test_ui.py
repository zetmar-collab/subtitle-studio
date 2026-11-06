import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from PySide6.QtGui import QTextCursor

from srtstudio.project import Project, Segment
from srtstudio.ui import Window


def test_editor_history_split_spell_and_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("SZEPT_DATA_DIR", str(tmp_path))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    app = QApplication.instance() or QApplication([])
    w = Window()
    from srtstudio.managers import ModelManager
    manager = ModelManager(w)
    manager.show()
    app.processEvents()
    assert manager.table.rowCount() == 5
    manager.close()
    w.project = Project(duration=10, language="en", segments=[Segment(0, 4, "hello helllo", "hello helllo"), Segment(5, 8, "world", "world")])
    w.reset_history()
    w.render()
    w.table.selectRow(0)
    w.segment_edit.setPlainText("hello corrected")
    assert w.project.segments[0].text == "hello corrected"
    assert w.full_edit.toPlainText().startswith("hello corrected")
    w.undo()
    assert w.project.segments[0].text == "hello helllo"
    w.redo()
    assert w.project.segments[0].text == "hello corrected"
    cursor = w.segment_edit.textCursor()
    cursor.setPosition(6)
    w.segment_edit.setTextCursor(cursor)
    w.split()
    assert len(w.project.segments) == 3
    assert w.project.segments[0].review
    w.undo()
    assert len(w.project.segments) == 2
    w.undo()
    w.spell_timer.stop()
    w.check_spelling()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and w.spell_cache.get("en", {}).get("helllo") is not False:
        app.processEvents()
        time.sleep(.05)
    assert w.spell_cache["en"]["hello"] is True
    assert w.spell_cache["en"]["helllo"] is False
    w.add_user_word("en", "helllo")
    assert "helllo" in w.custom_words["en"]
    w.dirty = True
    w.autosave()
    assert Project.loads(w.autosave_path().read_text(encoding="utf-8")).segments[0].text == "hello helllo"
    for lang in ("pl", "en"):
        w.ui_language = lang
        w.build_ui()
        w.render()
        assert w.start_button.text() == ("Transkrybuj" if lang == "pl" else "Transcribe")
    for theme in ("light", "dark", "system"):
        w.settings.setValue("theme", theme)
        w.apply_theme()
    w.dirty = False
    w.close()


def test_worker_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv("SZEPT_DATA_DIR", str(tmp_path))
    from srtstudio.jobs import Job
    app = QApplication.instance() or QApplication([])
    job = Job()
    job.start("probe", dict(source=str(tmp_path / "missing.wav")))
    process = job.process
    work = job.work
    job.cancel()
    assert not job.active
    assert not work.exists()
