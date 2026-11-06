import copy
import json
import time
import wave
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox
from core.projects.model import Project, Segment, save, load
from srtstudio.project import Project as SpeechProject, Segment as SpeechSegment


@pytest.fixture
def workspace(app, monkeypatch, tmp_path):
    from ui.window import Window
    from srtstudio.ui import Window as SpeechWindow
    import srtstudio.ui as speech_ui
    from ui.workspace import Workspace
    monkeypatch.setenv('SZEPT_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setattr(Window,'recover',lambda self:None)
    monkeypatch.setattr(SpeechWindow,'recover',lambda self:None)
    monkeypatch.setattr(speech_ui,'QSettings',lambda *args:QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat))
    host=Workspace();host.editor.autopath=tmp_path/'recovery.json'
    host.editor.error=lambda e:pytest.fail(str(e))
    yield host
    host.editor.confirm_unsaved=lambda:True
    if host.transcription:
        host.transcription.confirm_save=lambda:True
    host.close();app.processEvents()


def test_common_save_restore_and_new_project(workspace, tmp_path, monkeypatch):
    speech=workspace.speech()
    speech.project=SpeechProject(duration=2,model='tiny',segments=[SpeechSegment(0,1,'hello','original',review=True)])
    speech.dirty=True
    workspace.editor.track().segments=[Segment(0,1000,'film caption')]
    workspace.editor.track().style.size=76
    target=tmp_path/'session.subtitlelogo.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(target),''))
    assert speech.save_project()
    stored=load(target)
    assert stored.version == 2 and stored.transcript['model']=='tiny'
    assert stored.transcript['segments'][0]['original']=='original'
    assert stored.tracks[0].style.size==76
    assert not speech.dirty and not workspace.editor.dirty
    speech.project.segments=[];speech.dirty=False
    workspace.editor.open_project(str(target))
    assert speech.project.segments[0].original=='original'
    assert workspace.editor.new_project()
    assert speech.project.segments==[] and workspace.editor.track().segments==[]
    assert workspace.editor.project.transcript is None


def test_link_update_preserves_style_and_cancel_is_non_mutating(workspace,monkeypatch):
    speech=workspace.speech()
    speech.project=SpeechProject(duration=2,segments=[SpeechSegment(0,1,'one')])
    workspace.send_to_editor()
    count=len(workspace.editor.project.tracks)
    linked=workspace.editor.track();linked.style.size=81
    speech.project.segments[0].text='two'
    before=copy.deepcopy(workspace.editor.project.data())
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.StandardButton.Cancel)
    workspace.send_to_editor()
    assert workspace.editor.project.data()==before
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.StandardButton.Yes)
    workspace.send_to_editor()
    assert len(workspace.editor.project.tracks)==count
    assert workspace.editor.track().style.size==81
    assert workspace.editor.track().segments[0].text=='two'
    workspace.editor.undo()
    assert workspace.editor.track().segments[0].text=='one'


def test_audio_only_project_probes_before_transfer(workspace,app,tmp_path):
    source=tmp_path/'speech.wav'
    with wave.open(str(source),'wb') as audio:
        audio.setparams((1,2,16000,0,'NONE',''));audio.writeframes(b'\0'*64000)
    workspace.editor.track().source=str(source)
    workspace.editor.track().segments=[Segment(0,1000,'hello')]
    workspace.send_to_transcript()
    deadline=time.monotonic()+5
    while (workspace.transcription is None or not workspace.transcription.project.source) and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert workspace.transcription.project.duration==2
    assert workspace.transcription.project.source==str(source)


def test_session_relative_audio_and_legacy_read(tmp_path):
    source=tmp_path/'speech.wav';source.write_bytes(b'preserve')
    project=Project(transcript=json.loads(SpeechProject(source=str(source)).dumps()))
    target=tmp_path/'session.json';save(project,target)
    assert json.loads(target.read_text(encoding='utf-8'))['transcript']['source']=='speech.wav'
    assert load(target).transcript['source']==str(source)
    data=Project().data();data['version']=1;data.pop('transcript');data.pop('linked_track')
    for track in data['tracks']:track.pop('track_id')
    assert Project.from_data(data).version==2


def test_review_queue_marks_checked_and_preserves_original(workspace,app):
    from ui.review import ReviewDialog
    speech=workspace.speech()
    speech.project=SpeechProject(duration=2,original_text='raw ASR',segments=[
        SpeechSegment(0,1,'hello','raw',words=[dict(word='hello',start=0,end=1,probability=.4)],review=True)])
    speech.render();dialog=ReviewDialog(workspace)
    assert dialog.table.rowCount()==1
    dialog.table.selectRow(0);dialog.mark(True)
    assert speech.project.segments[0].checked and speech.project.original_text=='raw ASR'
    assert dialog.table.rowCount()==0
    dialog.show_checked.setChecked(True);dialog.table.selectRow(0);dialog.mark(False)
    assert not speech.project.segments[0].checked
    workspace.capture_session()
    assert workspace.editor.project.transcript['segments'][0]['words'][0]['probability']==.4
    speech.project.segments[0].checked=True
    speech.table.selectRow(0);speech.segment_edit.setPlainText('edited')
    assert not speech.project.segments[0].checked
    dialog.close()


def test_workflow_starts_asr_after_real_probe(workspace,app,monkeypatch):
    from core.media.tools import probe
    from ui.workflow import WorkflowDock
    source=load('examples/Demo.subtitlelogo.json').video
    workspace.editor.set_video(source,probe(source))
    speech=workspace.speech();speech.confirm_save=lambda:True
    started=[];monkeypatch.setattr(speech,'start_asr',lambda:started.append(speech.project.duration))
    dock=WorkflowDock(workspace);dock.transcribe()
    deadline=time.monotonic()+10
    while not started and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert started and started[0]>0
    dock.close()


def test_ollama_ui_apply_keeps_times_original_and_undo(workspace,app,monkeypatch):
    from core.ai.ollama import Ollama
    from ui.ollama import OllamaDialog
    from PySide6.QtCore import Qt
    monkeypatch.setattr(Ollama,'models',lambda self:[dict(name='local:test',size=1234)])
    original=Segment(100,900,'ktury kolor?',words=[dict(text='ktury',start=100,end=400),dict(text='kolor?',start=500,end=900)])
    workspace.editor.track().segments=[original];workspace.editor.refresh()
    dialog=OllamaDialog(workspace)
    deadline=time.monotonic()+3
    while dialog.model.count()==0 and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    segments=workspace.editor.track().segments
    dialog.context=(workspace.editor,workspace.editor.project,segments,{0:(original,original.text,original.start,original.end)})
    dialog.context_target=0
    dialog.proposals=[dict(id=0,original='ktury kolor?',text='który kolor?',reason='Pisownia')]
    dialog.table.setRowCount(1)
    from PySide6.QtWidgets import QTableWidgetItem
    item=QTableWidgetItem();item.setCheckState(Qt.CheckState.Checked);dialog.table.setItem(0,0,item)
    dialog.apply()
    assert segments[0].text=='który kolor?' and (segments[0].start,segments[0].end)==(100,900)
    assert segments[0].original=='ktury kolor?' and not segments[0].words
    workspace.editor.undo();assert workspace.editor.track().segments[0].text=='ktury kolor?'
    dialog.apply();assert 'zmienił' in dialog.message.text()
    dialog.reject()


def test_ctrl_s_from_transcription_saves_the_common_session(workspace,app,tmp_path,monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    speech=workspace.speech()
    speech.project=SpeechProject(duration=2,segments=[SpeechSegment(0,1,'hello')]);speech.dirty=True;speech.render()
    target=tmp_path/'shortcut-session.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(target),''))
    workspace.show();workspace.activateWindow();workspace.tabs.setCurrentIndex(1);speech.table.setFocus();app.processEvents()
    QTest.keyClick(speech.table,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    assert target.exists() and load(target).transcript['segments'][0]['text']=='hello'
    assert not speech.dirty and not workspace.editor.dirty


def test_top_video_button_starts_asr_after_probe(workspace,app,monkeypatch):
    from core.media.tools import probe
    source=load('examples/Demo.subtitlelogo.json').video
    workspace.editor.set_video(source,probe(source))
    speech=workspace.speech();speech.confirm_save=lambda:True
    started=[];monkeypatch.setattr(speech,'start_asr',lambda:started.append(speech.project.source))
    workspace.transcribe_video()
    deadline=time.monotonic()+10
    while not started and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert started==[source]
    workspace.transcribe_video()
    assert started==[source,source]  # Already probed: one start, no redundant reload.


def test_transcription_file_picker_includes_video(workspace,monkeypatch):
    speech=workspace.speech();picked=[];filters=[]
    def choose(*args):
        filters.append(args[3]);return ('speech.mp4','')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',choose)
    monkeypatch.setattr(speech,'load_audio',lambda path:picked.append(path))
    speech.choose_audio()
    assert picked==['speech.mp4'] and '*.mp4' in filters[0] and '*.mkv' in filters[0]


def test_paused_seek_updates_overlay_time(workspace):
    workspace.editor.preview.ms=0
    workspace.editor.position(1789)
    assert workspace.editor.preview.ms==1789


def test_ollama_real_gui_worker_sends_all_captions_and_reopens_on_current_tab(workspace,app,monkeypatch,tmp_path):
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import threading
    from core.projects.model import Track
    import ui.ollama as ai_ui
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def answer(self,data):
            body=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):self.answer(dict(models=[dict(name='local:test',size=1234)]))
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path=='/api/show':self.answer(dict(capabilities=['completion','thinking'],model_info={'general.architecture':'test'}))
            else:
                calls.append(data)
                captions=json.loads(data['prompt'])['captions']
                self.answer(dict(response=json.dumps(dict(corrections=[dict(id=c['id'],text=c['text'].replace('ktury','który'),reason='Pisownia') for c in captions]))))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    settings=QSettings(str(tmp_path/'ai.ini'),QSettings.Format.IniFormat)
    settings.setValue('url',f'http://127.0.0.1:{server.server_port}')
    monkeypatch.setattr(ai_ui,'QSettings',lambda *args:settings)
    track=Track(name='Imported captions',segments=[Segment(0,900,'ktury pierwszy?'),Segment(1000,1900,'ktury drugi?')])
    workspace.editor.project.tracks.append(track)
    workspace.editor.refresh()  # Active default track is empty; imported track must be found.
    workspace.show_ai();dialog=workspace.ai_dialog
    try:
        deadline=time.monotonic()+5
        while dialog.model.count()==0 and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
        assert dialog.track_selector.currentData()==track.track_id
        assert not dialog.selection.isChecked() and 'ktury drugi?' in dialog.input_text.toPlainText()
        dialog.begin()
        deadline=time.monotonic()+15
        while dialog.process and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
        assert dialog.process is None and len(dialog.proposals)==2,dialog.message.text()
        assert len(json.loads(calls[0]['prompt'])['captions'])==2
        assert calls[0]['think'] is True
        dialog.select_all();dialog.apply()
        assert track.segments[1].text=='który drugi?' and track.segments[1].start==1000
        dialog.reject()
        speech=workspace.speech();speech.project=SpeechProject(duration=2,segments=[SpeechSegment(0,1,'ktury transkrypt?')])
        workspace.tabs.setCurrentIndex(1);workspace.show_ai()
        assert dialog.target.currentIndex()==1 and 'transkrypt' in dialog.input_text.toPlainText()
        dialog.reject();workspace.tabs.setCurrentIndex(0);workspace.show_ai()
        assert dialog.target.currentIndex()==0 and 'drugi' in dialog.input_text.toPlainText()
    finally:
        dialog.reject()
        deadline=time.monotonic()+3
        while dialog.process and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
        server.shutdown();server.server_close();thread.join()
