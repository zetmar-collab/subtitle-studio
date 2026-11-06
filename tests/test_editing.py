from copy import deepcopy
import pytest
from core.projects.model import Segment, Project, save, load
from core.subtitles.editing import duplicate, ripple_delete


def test_duplicate_preserves_source_and_shifts_words():
    source = [Segment(100,400,'raz',words=[dict(start=100,end=400)])]
    result, rows = duplicate(source,[0],1000)
    assert rows == [1]
    assert result[1].start == 400 and result[1].words[0]['start'] == 400
    assert source[0].words[0]['start'] == 100
    with pytest.raises(ValueError):
        duplicate(source,[0],500)


def test_ripple_delete_closes_only_selected_intervals():
    source = [Segment(100,300,'a'),Segment(500,700,'b'),Segment(900,1000,'c'),
              Segment(1200,1400,'d',words=[dict(start=1200,end=1400)])]
    original = deepcopy(source)
    result = ripple_delete(source,[0,2])
    assert [(s.start,s.end) for s in result] == [(300,500),(900,1100)]
    assert result[1].words[0]['start'] == 900
    assert source == original


def test_ripple_rejects_overlapping_survivors_without_mutation():
    source = [Segment(0,500,'a'),Segment(300,700,'b')]
    with pytest.raises(ValueError):
        ripple_delete(source,[0])
    assert source[1].start == 300


def test_range_roundtrip_and_older_project(tmp_path):
    project = Project(range_start=200,range_end=800)
    path = tmp_path/'range.json'
    save(project,path)
    assert load(path).range_start == 200 and load(path).range_end == 800
    data = project.data()
    del data['range_start'], data['range_end']
    assert Project.from_data(data).range_end is None


def test_timeline_drag_snap_and_undo(app,monkeypatch):
    from PySide6.QtCore import Qt, QPoint, QPointF
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from ui.window import Window
    monkeypatch.setattr(Window,'recover',lambda self: None)
    window = Window()
    window.info['duration'] = 10000
    window.timeline.duration = 10000
    window.track().segments = [Segment(1000,3000,'raz'),Segment(5000,6000,'dwa')]
    window.refresh()
    window.show()
    app.processEvents()
    timeline = window.timeline
    rect = timeline.segment_rect(0,window.track().segments[0])
    start = QPoint(round(rect.right()),round(rect.center().y()))
    target = QPoint(round(timeline.x_at(5000))-3,start.y())
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=start)
    event = QMouseEvent(QMouseEvent.Type.MouseMove,QPointF(target),QPointF(timeline.mapToGlobal(target)),
                        Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    app.sendEvent(timeline,event)
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=target)
    assert window.track().segments[0].end == 5000
    assert len(window.history) == 1
    window.undo()
    assert window.track().segments[0].end == 3000
    timeline.set_zoom(2)
    assert timeline.zoom == 2
    window.dirty = False
    window.close()


def test_shortcuts_allow_typing_and_range_undo(app,monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    from ui.window import Window
    monkeypatch.setattr(Window,'recover',lambda self: None)
    window = Window()
    edit = QLineEdit(window)
    edit.show()
    window.show()
    edit.setFocus()
    app.processEvents()
    QTest.keyClicks(edit,'i o b d test')
    assert edit.text() == 'i o b d test'
    window.info['duration'] = 3000
    window.project.range_end = 3000
    window.refresh()
    window.range_in.setValue(1000)
    window.range_out.setValue(2000)
    assert (window.project.range_start,window.project.range_end) == (1000,2000)
    window.undo()
    assert window.project.range_end == 3000
    window.dirty = False
    window.close()
