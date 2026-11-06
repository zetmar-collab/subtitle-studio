import json
import os
import shutil
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMimeData, QSettings, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from srtstudio.project import Project, Segment, issues
from srtstudio.ui import Window
from .test_dictionaries import pair


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("SZEPT_DATA_DIR", str(tmp_path))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    app = QApplication.instance() or QApplication([])
    w = Window()
    w.project = Project(duration=10, language="en", segments=[Segment(0, 4, "hello helllo", "hello helllo"), Segment(5, 8, "world", "world")])
    w.reset_history()
    w.render()
    yield w
    w.dirty = False
    w.close()


def wait_for(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(.02)
    assert predicate()


def test_highlighting_and_ui_rebuild_do_not_edit_project(window):
    w = window
    before = w.project.dumps()
    w.spell_cache["en"] = {"hello": True, "helllo": False}
    w.rehighlight()
    assert w.project.dumps() == before and not w.dirty
    assert any(r.start == 6 and r.length == 6 for r in w.segment_edit.document().firstBlock().layout().formats())
    for language in ("pl", "en"):
        w.ui_language = language
        w.build_ui()
        w.render()
        QApplication.processEvents()
        assert w.project.dumps() == before and not w.dirty


def test_read_only_and_stale_suggestions_cannot_change_text(window):
    w, editor = window, window.segment_edit
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(12, QTextCursor.MoveMode.KeepAnchor)
    revision = editor.text_generation
    w.rehighlight()
    assert editor.text_generation == revision
    w.set_busy(True)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    w.replace_suggestion(editor, cursor, "helllo", revision, "hello")
    assert editor.toPlainText() == "hello helllo"
    w.set_busy(False)
    editor.insertPlainText("edited ")
    before = editor.toPlainText()
    w.replace_suggestion(editor, cursor, "helllo", revision, "hello")
    assert editor.toPlainText() == before


def test_cross_segment_cut_and_paste_preserve_project(window):
    w = window
    before = w.project.dumps()
    w.full_edit.selectAll()
    w.full_edit.cut()
    data = QMimeData()
    data.setText("replacement")
    w.full_edit.insertFromMimeData(data)
    assert w.project.dumps() == before


def test_dictionary_install_refreshes_language_choices(window, tmp_path):
    pair(tmp_path / "dictionaries" / "eo")
    window.restart_spelling()
    assert window.spell.findData("eo") >= 0
    window.project.language = "eo"
    assert window.spell_language(0) == "eo"


def test_suggestions_and_spellcheck_run_independently(window):
    w = window
    w.request_suggestions("en", "helllo")
    w.check_spelling()
    wait_for(lambda: w.spell_cache.get("en", {}).get("helllo") is False)
    wait_for(lambda: "hello" in w.suggestion_cache.get(("en", "helllo"), []))
    assert w.spell_process.pid != w.suggest_process.pid
    w.ignore_word("en", "helllo")
    assert not w.segment_edit.document().firstBlock().layout().formats()


def test_source_recording_protected_and_empty_project_clears_player(window, tmp_path):
    source = tmp_path / "audio.wav"
    source.write_bytes(b"recording data")
    window.project.source = str(source)
    with pytest.raises(ValueError):
        window.protect_source(source)
    assert source.read_bytes() == b"recording data"
    window.project.source = ""
    window.set_audio_source()
    assert window.player.source().isEmpty()


@pytest.mark.parametrize("change", [{"profile": {"width": 0}}, {"language": "../outside"},
    {"profile": {"minimum": 9, "maximum": 1}}, {"segments": [{"start": 0, "end": 1, "text": 123}]}])
def test_malformed_project_rejected(change):
    data = json.loads(Project().dumps())
    data.update(change)
    with pytest.raises((ValueError, TypeError)):
        Project.loads(json.dumps(data))


def test_nonfinite_validation_reports_error():
    assert issues(Project(segments=[Segment(float("inf"), 2, "text")]), 0)[0] == ["time"]


def test_typing_coalesces_and_does_not_undo_into_middle_of_word(window):
    window.segment_edit.setPlainText("hello correction")
    window.segment_edit.setPlainText("hello corrected")
    window.undo()
    assert window.project.segments[0].text == "hello helllo"
    window.redo()
    assert window.project.segments[0].text == "hello corrected"


def test_real_polish_spelling_suggestions_and_replacement(window, tmp_path):
    from pathlib import Path
    source = Path(__file__).resolve().parent.parent / "test-artifacts/dictionary-test/dictionaries/pl"
    if not source.exists():
        pytest.skip("Explicitly downloaded Polish test fixture is absent")
    (tmp_path / "dictionaries").mkdir(exist_ok=True)
    shutil.copytree(source, tmp_path / "dictionaries/pl")
    w = window
    w.project.language = "pl"
    w.project.segments = [Segment(0, 4, "który ktury", "który ktury")]
    w.reset_history()
    w.render()
    w.restart_spelling()
    w.check_spelling()
    wait_for(lambda: "ktury" in w.spell_cache.get("pl", {}))
    assert w.spell_cache["pl"]["który"] and not w.spell_cache["pl"]["ktury"]
    w.request_suggestions("pl", "ktury")
    wait_for(lambda: "który" in w.suggestion_cache.get(("pl", "ktury"), []))
    editor = w.segment_edit
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    w.replace_suggestion(editor, cursor, "ktury", editor.text_generation, "który")
    assert w.project.segments[0].text == "który który"
    assert w.project.segments[0].original == "który ktury"


def test_cancel_from_worker_event_is_safe(window, tmp_path):
    import wave
    from srtstudio.jobs import Job
    source = tmp_path / "short.wav"
    with wave.open(str(source), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(bytes(3200))
    job = Job(window)
    results = []
    job.event.connect(lambda event: job.cancel() if event[0] == "metadata" else None)
    job.finished.connect(results.append)
    job.start("probe", dict(source=str(source)))
    work = job.work
    wait_for(lambda: bool(results))
    assert results == [False] and not job.active and not work.exists()
