from pathlib import Path
import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QColorDialog, QDialog
from core.projects.model import Segment, Project, save, load
from core.compositor.render import compose
from ui.window import Window
from ui.colors import ColorButton


@pytest.fixture
def window(app,monkeypatch):
    monkeypatch.setattr(Window,'recover',lambda self: None)
    w = Window()
    w.autotimer.stop()
    yield w
    w.dirty = False
    w.close()


def test_picker_previews_and_commits_as_one_undo(window,monkeypatch):
    w = window
    original = w.track().style.color
    def choose(dialog):
        dialog.setCurrentColor(QColor('#42c5f5'))
        assert w.track().style.color == '#42c5f5'
        assert len(w.history) == 0
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QColorDialog,'exec',choose)
    w.choose_color('color',w.color)
    assert w.track().style.color == '#42c5f5'
    assert w.dirty and len(w.history) == 1
    assert '●' in w.windowTitle()
    w.undo()
    assert w.track().style.color == original
    assert w.color.value() == original
    w.redo()
    assert w.track().style.color == '#42c5f5'


def test_cancel_restores_alpha_and_does_not_create_history_or_autosave(window,monkeypatch,tmp_path):
    w = window
    w.dirty = True
    w.autopath = tmp_path/'must-not-exist.json'
    original = w.track().style.background
    def cancel(dialog):
        assert dialog.testOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        dialog.setCurrentColor(QColor('#8066aaff'))
        assert w.track().style.background == '#8066aaff'
        w.autosave()
        assert not w.autopath.exists()
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QColorDialog,'exec',cancel)
    w.choose_color('background',w.background)
    assert w.track().style.background == original
    assert w.background.value() == original
    assert w.dirty and w.history == []
    assert not w._color_session


@pytest.mark.parametrize('field,button_name,color',[
    ('outline','outline_color','#aa2255'),('active_color','active_color','#33bb77'),('background','background','#70445566')])
def test_all_color_fields_roundtrip(window,monkeypatch,tmp_path,field,button_name,color):
    def choose(dialog):
        dialog.setCurrentColor(QColor(color))
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QColorDialog,'exec',choose)
    window.choose_color(field,getattr(window,button_name))
    path = tmp_path/'colors.subtitlelogo.json'
    save(window.project,path)
    result = load(path)
    assert getattr(result.tracks[0].style,field) == color


def test_swatch_shows_opacity_and_icon(app):
    button = ColorButton('#8066aaff')
    assert '50%' in button.text() and '#8066AAFF' in button.text()
    assert not button.icon().isNull()
    assert button.color().alpha() == 128


def test_outline_does_not_cover_letter_fill(app):
    p = Project()
    p.tracks[0].segments = [Segment(0,2000,'Kolor napisów')]
    p.tracks[0].style.color = '#22cc66'
    frame = QImage(640,360,QImage.Format.Format_RGB888)
    frame.fill(QColor('#101218'))
    rendered = compose(frame,p,1000)
    # Even with the default outline, enough interior pixels retain the chosen color.
    chosen = QColor('#22cc66').rgb()
    count = sum(rendered.pixel(x,y) == chosen for y in range(285,340) for x in range(180,460))
    assert count > 100


def test_program_icon_present(window):
    assert not window.windowIcon().isNull()
    import struct
    icon = Path(__file__).resolve().parents[1]/'assets/icon.ico'
    data = icon.read_bytes()
    count = struct.unpack_from('<H',data,4)[0]
    sizes = {(data[6+i*16] or 256,data[7+i*16] or 256) for i in range(count)}
    assert {(16,16),(32,32),(48,48),(256,256)} <= sizes


def test_picker_uses_polish_translation_only_during_session(window,monkeypatch):
    from PySide6.QtCore import QCoreApplication
    def cancel(dialog):
        assert QCoreApplication.translate('QColorDialog','&Basic colors') != '&Basic colors'
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QColorDialog,'exec',cancel)
    window.choose_color('color',window.color)
    assert QCoreApplication.translate('QColorDialog','&Basic colors') == '&Basic colors'
