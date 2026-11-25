"""Audit fixes and features added on top of 0.8.0: IPC, jobs, banners, keyframes,
timeline layers, safe areas, templates, MCP log/revert, translation and framing."""
import json
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QImage

from core.compositor.render import compose, fit_frame, fitted_size, position
from core.projects.model import Banner, Logo, Project, Segment, Track, set_keyframe, validate_keyframes


@pytest.fixture
def workspace(app, monkeypatch, tmp_path):
    from ui.window import Window
    from ui.workspace import Workspace
    monkeypatch.setattr(Window, 'recover', lambda self: None)
    w = Workspace(); w.editor.autotimer.stop(); w.editor.autopath = tmp_path/'recovery.json'
    w.automation.start(tmp_path)
    w.automation.template_path = tmp_path/'templates.json'
    yield w
    w.editor.player.stop(); w.editor.dirty = False
    if w.transcription: w.transcription.dirty = False
    w.close(); app.processEvents()
    # Destroy the window (not only hide it): many leaked workspaces slow down
    # later time-limited tests in the same process.
    from PySide6.QtCore import QEvent
    w.deleteLater(); app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()


def black(width=400, height=200):
    frame = QImage(width, height, QImage.Format.Format_RGB888); frame.fill(QColor('black'))
    return frame


# --- audit fixes -----------------------------------------------------------

def test_ipc_request_executes_once_even_if_more_bytes_arrive(workspace, app):
    from PySide6.QtNetwork import QLocalSocket
    import time
    socket = QLocalSocket(); socket.connectToServer(workspace.automation.endpoint)
    assert socket.waitForConnected(2000)
    line = json.dumps({'command': 'banner', 'arguments': {'properties': {'text': 'Raz'}}}).encode()+b'\n'
    socket.write(line); socket.flush()
    deadline = time.monotonic()+5; data = b''
    while b'\n' not in data and time.monotonic() < deadline:
        app.processEvents(); socket.waitForReadyRead(20); data += bytes(socket.readAll())
    assert b'banner_id' in data
    socket.write(line); socket.flush()  # a second copy on the same connection
    for _ in range(20):
        app.processEvents(); socket.waitForReadyRead(10)
    assert len(workspace.editor.project.banners) == 1
    assert workspace.automation.history[-1]['command'] == 'banner'


def test_job_result_survives_undo_but_not_a_different_document(workspace, tmp_path):
    a = workspace.automation
    key = a.document_key()
    a.call('banner', {'properties': {'text': 'A'}})
    workspace.editor.undo()  # replaces the Project object
    assert a.document_key() == key

    class Process:
        def deleteLater(self): pass
    temp = tempfile.TemporaryDirectory()
    status = Path(temp.name)/'status.json'; status.write_text(json.dumps({'done': True}))
    job = dict(id='x', kind='transcribe', state='running', percent=0, target=None, error='', process=Process(),
               temp=temp, status=status, cancel=Path(temp.name)/'cancel', auto_open=False,
               document=('other.json', 'other.mp4', 'id'), result_file=Path(temp.name)/'missing.json')
    tracks = len(workspace.editor.project.tracks)
    a.finished(job, 0)
    assert job['state'] == 'error' and 'not applied' in job['error']
    assert len(workspace.editor.project.tracks) == tracks


def test_cancel_unknown_job_and_transcribe_without_video(workspace):
    a = workspace.automation
    with pytest.raises(ValueError, match='Unknown job id'):
        a.call('cancel', {'job_id': 'nope'})
    with pytest.raises(ValueError, match='Open or create a video first'):
        a.call('transcribe', {'model_path': '.'})


def test_mutating_command_rejected_while_another_waits(workspace):
    a = workspace.automation
    a.in_call = True
    try:
        with pytest.raises(ValueError, match='Finish the running job'):
            a.call('banner', {'properties': {}})
        assert a.call('fonts', {})['fonts']  # read-only commands still work
    finally:
        a.in_call = False


def test_status_writer_retries_locked_file(tmp_path, monkeypatch):
    import os
    from core import automation_worker
    calls = []
    real = os.replace
    def flaky(src, dst):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError('locked by reader')
        return real(src, dst)
    monkeypatch.setattr(automation_worker.os, 'replace', flaky)
    monkeypatch.setattr(automation_worker.time, 'sleep', lambda s: None)
    assert automation_worker.write_status(tmp_path/'status.json', {'done': True})
    assert json.loads((tmp_path/'status.json').read_text())['done'] and len(calls) == 3
    calls.clear()
    monkeypatch.setattr(automation_worker.os, 'replace', lambda *a: (_ for _ in ()).throw(PermissionError()))
    assert not automation_worker.write_status(tmp_path/'p.json', {'percent': 5}, required=False)


def test_fitted_size_matches_linear_search_and_is_cached(app):
    from PySide6.QtGui import QFontMetricsF
    banner = Banner(text='Bardzo długi tekst baneru, który musi się zmieścić w prostokącie', font_size=300)
    rect = QRectF(0, 0, 500, 120); flags = 0x1000 | 0x0080 | 0x0004
    linear = 300; font = QFont(banner.font)
    while linear > 1:
        font.setPixelSize(linear)
        bounds = QFontMetricsF(font).boundingRect(rect, flags, banner.text)
        if bounds.height() <= rect.height() and bounds.width() <= rect.width():
            break
        linear -= 1
    assert fitted_size(banner, QFont(banner.font), 300, rect, flags) == linear
    assert fitted_size(banner, QFont(banner.font), 300, rect, flags) == linear


def test_logo_validation_rejects_wrong_types():
    for change in ({'x': True}, {'width': '20'}, {'opacity': float('nan')}):
        with pytest.raises(ValueError):
            Project.from_data(dict(Project(logos=[Logo(path='a.png', **change)]).data()))


def test_layer_up_on_top_banner_does_not_add_undo_step(workspace):
    editor = workspace.editor
    editor.project.banners.append(Banner()); editor.active_banner = 0; editor.refresh()
    history = len(editor.history)
    editor.layer_up()
    assert len(editor.history) == history


# --- keyframes and animation ----------------------------------------------

def test_keyframe_interpolation_and_validation():
    banner = Banner(keyframes=[{'ms': 0, 'x': 10, 'y': 50, 'scale': 100},
                               {'ms': 1000, 'x': 90, 'y': 50, 'scale': 300}]).validate()
    assert position(banner, -50) == (10, 50, 1.0)
    assert position(banner, 500) == (50.0, 50.0, 2.0)
    assert position(banner, 5000) == (90, 50, 3.0)
    for frames in ([{'ms': 5, 'x': 1, 'y': 1, 'scale': 100}]*2, [{'ms': 0, 'x': 1, 'y': 1}],
                   [{'ms': 0, 'x': 101, 'y': 1, 'scale': 100}], [{'ms': 0, 'x': 1, 'y': 1, 'scale': 5}]):
        with pytest.raises(ValueError):
            validate_keyframes(frames)
    logo = Logo(path='a.png')
    set_keyframe(logo, 500, 20, 30); set_keyframe(logo, 100, 1, 2); set_keyframe(logo, 500, 40, 30)
    assert [f['ms'] for f in logo.keyframes] == [100, 500] and logo.keyframes[1]['x'] == 40


def test_project_versions_with_keyframes():
    plain = Project(logos=[Logo(path='a.png')])
    assert plain.data()['version'] == 2 and 'keyframes' not in plain.data()['logos'][0]
    moving = Project(logos=[Logo(path='a.png', keyframes=[{'ms': 0, 'x': 1, 'y': 2, 'scale': 100}])])
    assert moving.data()['version'] == 3
    assert Project.from_data(moving.data()).logos[0].keyframes == moving.logos[0].keyframes


def test_logo_keyframes_move_rendered_logo(app, tmp_path):
    logo_image = QImage(20, 20, QImage.Format.Format_RGB888); logo_image.fill(QColor('red'))
    logo_image.save(str(tmp_path/'logo.png'))
    logo = Logo(path=str(tmp_path/'logo.png'), width=10, keyframes=[{'ms': 0, 'x': 10, 'y': 50, 'scale': 100},
                                                                    {'ms': 1000, 'x': 90, 'y': 50, 'scale': 100}])
    project = Project(logos=[logo])
    assert compose(black(), project, 0).pixelColor(40, 100) == QColor('red')
    assert compose(black(), project, 1000).pixelColor(40, 100) == QColor('black')
    assert compose(black(), project, 1000).pixelColor(360, 100) == QColor('red')


def test_banner_animation_fades_and_slides(app):
    banner = Banner(text='', background='#ff0000', radius=0, x=50, y=50, width=40, height=40,
                    start=1000, end=5000, animation='slide_up', animation_ms=400)
    project = Project(banners=[banner])
    assert compose(black(), project, 1000).pixelColor(200, 100) == QColor('black')  # invisible first frame
    assert compose(black(), project, 1500).pixelColor(200, 100) == QColor('red')    # settled
    assert compose(black(), project, 4999).pixelColor(200, 100).red() < 60           # leaving
    with pytest.raises(ValueError):
        Banner(animation='spin').validate()


# --- timeline layers ------------------------------------------------------

def test_timeline_layer_drag_rules(app):
    from ui.preview import Timeline
    timeline = Timeline(); timeline.duration = 10000
    timeline.project = Project(logos=[Logo(path='a.png', start=1000)], banners=[Banner(start=2000, end=4000)])
    logo, banner = timeline.project.logos[0], timeline.project.banners[0]
    assert timeline.layer_drag(logo, 'move', 3000) == (4000, timeline.FOREVER)   # open end stays open
    assert timeline.layer_drag(banner, 'move', 7000) == (8000, 10000)            # clamped to the video
    assert timeline.layer_drag(banner, 'start', 5000) == (3999, 4000)
    assert timeline.layer_drag(banner, 'end', -5000) == (2000, 2001)
    assert timeline.required_height() >= timeline.lanes_top() + 2*timeline.LANE


def test_moving_layer_on_timeline_moves_its_keyframes(workspace):
    editor = workspace.editor
    editor.project.banners.append(Banner(start=1000, end=3000,
        keyframes=[{'ms': 1000, 'x': 10, 'y': 10, 'scale': 100}, {'ms': 2000, 'x': 90, 'y': 10, 'scale': 100}]))
    editor.refresh()
    editor.edit_timeline_layer('banner', 0, 1500, 3500, 'move')
    assert [f['ms'] for f in editor.project.banners[0].keyframes] == [1500, 2500]
    editor.edit_timeline_layer('banner', 0, 1500, 3000, 'end')
    assert [f['ms'] for f in editor.project.banners[0].keyframes] == [1500, 2500]
    editor.undo(); editor.undo()
    assert editor.project.banners[0].start == 1000


def test_add_keyframe_and_drag_keys_position(workspace):
    editor = workspace.editor
    editor.project.banners.append(Banner(start=0, end=5000, x=20, y=20)); editor.active_banner = 0
    editor.refresh(); editor.preview.ms = 2000
    editor.add_keyframe()
    assert [f['ms'] for f in editor.project.banners[0].keyframes] == [0, 2000]
    editor.move_layer(70, 40)
    frame = editor.project.banners[0].keyframes[1]
    assert (frame['x'], frame['y']) == (70, 40) and editor.project.banners[0].x == 20
    editor.clear_keyframes()
    assert not editor.project.banners[0].keyframes and editor.project.banners[0].x == 70


# --- safe areas and framing ----------------------------------------------

def test_safe_area_and_vertical_preview(workspace, app):
    editor = workspace.editor
    editor.preview.frame = black(640, 360); editor.preview.resize(400, 400)
    workspace.toggle_vertical_preview(True)
    assert editor.preview.framing[:3] == (1080, 1920, 'crop') and editor.preview.safe_area == 'tiktok'
    assert workspace.safe_area_actions['tiktok'].isChecked()
    editor.preview.grab()  # paints the guide without errors
    assert editor.preview.rect.height() > editor.preview.rect.width()
    workspace.toggle_vertical_preview(False); editor.set_safe_area(None)
    assert editor.preview.framing is None and editor.ui_settings.value('safe_area') == ''


def test_fit_frame_crop_position(app):
    source = QImage(400, 100, QImage.Format.Format_RGB888); source.fill(QColor('blue'))
    for x in range(200, 400):
        for y in range(100):
            source.setPixelColor(x, y, QColor('green'))
    assert fit_frame(source, 100, 100, 'crop', 0).pixelColor(50, 50) == QColor('blue')
    assert fit_frame(source, 100, 100, 'crop', 100).pixelColor(50, 50) == QColor('green')
    assert fit_frame(source, 100, 100).pixelColor(50, 5) == QColor('black')  # fit keeps bars


def test_export_rejects_invalid_crop_position(workspace):
    with pytest.raises(ValueError):
        workspace.automation.framing('crop', 120)
    with pytest.raises(ValueError):
        workspace.automation.framing('stretch', 50)


# --- templates, MCP log and revert ---------------------------------------

def test_banner_templates_roundtrip(tmp_path):
    from core.projects import banner_templates as templates
    path = tmp_path/'t.json'
    assert 'Tytuł / Title' in templates.all_templates(path)
    templates.save_user('Mój', Banner(background='#123456', text='nie zapisuj', animation='pop'), path)
    assert templates.load_user(path)['Mój']['background'] == '#123456'
    assert 'text' not in templates.load_user(path)['Mój']
    applied = templates.apply(Banner(text='Zostaje'), 'Mój', path)
    assert applied.text == 'Zostaje' and applied.background == '#123456' and applied.animation == 'pop'
    with pytest.raises(ValueError):
        templates.save_user('Tytuł / Title', Banner(), path)
    path.write_text(json.dumps({'zły': {'width': 0}, 'dobry': {'radius': 3}}), encoding='utf-8')
    assert list(templates.load_user(path)) == ['dobry']  # damaged entries are skipped
    templates.delete_user('dobry', path)
    assert templates.load_user(path) == {}


def test_mcp_banner_template_and_listing(workspace):
    a = workspace.automation
    assert 'Etykieta / Tag' in a.call('banner_templates', {})['templates']
    banner = a.call('banner', {'properties': {'text': 'Nowość', 'radius': 2}, 'template': 'Etykieta / Tag'})
    assert banner['animation'] == 'pop' and banner['radius'] == 2 and banner['text'] == 'Nowość'
    with pytest.raises(ValueError):
        a.call('banner', {'properties': {}, 'template': 'brak'})


def test_ai_log_and_revert_to_baseline(workspace):
    a = workspace.automation
    editor = workspace.editor
    editor.project.tracks[0].segments.append(Segment(start=0, end=500, text='Przed AI'))
    a.call('banner', {'properties': {'text': 'AI'}})
    a.call('banner', {'properties': {'text': 'AI 2'}})
    assert [entry['command'] for entry in a.history][-2:] == ['banner', 'banner']
    a.restore_baseline()
    assert not editor.project.banners and editor.project.tracks[0].segments[0].text == 'Przed AI'
    assert a.baseline is None
    editor.undo()
    assert len(editor.project.banners) == 2
    with pytest.raises(ValueError):
        a.restore_baseline()


def test_disconnect_stops_listening(workspace, app):
    a = workspace.automation
    assert a.call('disconnect', {}) == {'disconnected': True}
    app.processEvents()
    assert not a.server.isListening()


# --- translation ------------------------------------------------------------

class FakeOllama:
    def __init__(self, drop=False):
        self.drop = drop; self.requests = []
    def check_model(self, name):
        return ['completion']
    def call(self, path, data=None, timeout=None):
        self.requests.append(data)
        captions = json.loads(data['prompt'])['captions']
        items = [dict(id=c['id'], text=c['text'].upper()) for c in captions]
        if self.drop:
            items = items[1:]
        return {'response': json.dumps({'translations': items})}


def test_translate_returns_every_caption_and_rejects_gaps():
    from core.ai.ollama import translate
    captions = [dict(id=i, text=f'napis {i}') for i in range(11)]
    client = FakeOllama()
    result = translate(client, 'm', captions, 'en')
    assert sorted(item['id'] for item in result) == list(range(11)) and len(client.requests) == 2
    assert 'English' in client.requests[0]['system']
    with pytest.raises(ValueError, match='skipped'):
        translate(FakeOllama(drop=True), 'm', captions, 'en')
    with pytest.raises(ValueError):
        translate(client, 'm', captions, 'xx')


def test_translated_track_keeps_times_and_style():
    from ui.translate import translated_track
    source = Track(name='PL', segments=[Segment(start=0, end=900, text='Cześć', words=[{'start': 0, 'end': 900, 'text': 'Cześć'}]),
                                        Segment(start=1000, end=1500, text='')])
    source.style.color = '#ff0000'
    track = translated_track(source, [{'id': 0, 'text': 'Hello'}], 'en')
    assert [(s.start, s.end, s.text) for s in track.segments] == [(0, 900, 'Hello'), (1000, 1500, '')]
    assert track.segments[0].words == [] and track.segments[0].language == 'en'
    assert not track.segments[1].review and track.style.color == '#ff0000' and track.track_id != source.track_id
    Project.from_data(Project(tracks=[source, track]).data())


def test_job_reports_running_until_its_result_is_applied(workspace, tmp_path):
    """Applying a result may wait for ffprobe in a nested event loop; clients must
    not see 'done' (and must not edit) before the video is actually loaded."""
    a = workspace.automation

    class Process:
        def deleteLater(self): pass
    temp = tempfile.TemporaryDirectory()
    status = Path(temp.name)/'status.json'; status.write_text(json.dumps({'done': True}))
    job = dict(id='j', kind='color', state='running', percent=0, target=str(tmp_path/'new.mp4'), error='',
               process=Process(), temp=temp, status=status, cancel=Path(temp.name)/'cancel', auto_open=True,
               document=a.document_key())
    a.jobs['j'] = job
    seen = {}
    def background(function, *args):
        seen['state'] = a.call('job', {'job_id': 'j'})['state']
        try:
            a.call('banner', {'properties': {}})
        except ValueError as error:
            seen['edit'] = str(error)
        return dict(width=320, height=180, duration=1000, fps=25, streams=[])
    a.background = background
    a.finished(job, 0)
    assert seen['state'] == 'running' and 'Finish the running job' in seen['edit']
    assert job['state'] in ('done', 'error') and not a.in_call
