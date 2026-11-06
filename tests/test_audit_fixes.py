import copy
from pathlib import Path
import pytest
from core.projects.model import Project, Segment, Logo, Style, save, load


@pytest.mark.parametrize('source_kind', ['video','logo','track'])
def test_save_protects_every_source(tmp_path, source_kind):
    source = tmp_path/'original.json'
    source.write_bytes(b'keep original')
    project = Project()
    if source_kind == 'video':
        project.video = str(source)
    elif source_kind == 'logo':
        project.logos = [Logo(path=str(source))]
    else:
        project.tracks[0].source = str(source)
    with pytest.raises(ValueError):
        save(project,source)
    assert source.read_bytes() == b'keep original'


@pytest.mark.parametrize('words', [[{}], [dict(start=0,end=0)], [dict(start=0,end=1001)],
                                   [dict(start=True,end=900)], [dict(start=0,end=900,text=[])]] )
def test_reject_invalid_word_data(words):
    data = Project().data()
    data['tracks'][0]['segments'] = [dict(start=0,end=1000,text='hello',words=words)]
    with pytest.raises(ValueError):
        Project.from_data(data)


@pytest.mark.parametrize('field,value', [('width',0),('stroke',-1),('animation_ms',0),
                                        ('color','no-such-color'),('x',float('nan')),('effect','bad')])
def test_style_validation_shared(field,value):
    style = Style()
    setattr(style,field,value)
    with pytest.raises(ValueError):
        style.validate()


def test_recovery_sessions_do_not_touch_live_siblings(tmp_path, app):
    from core.projects.recovery import RecoverySession
    first = RecoverySession(tmp_path,'test','legacy.json')
    second = RecoverySession(tmp_path,'test','legacy.json')
    first.path.write_text('first')
    second.path.write_text('second')
    assert first.candidates() == [] and second.candidates() == []
    second.close()
    assert first.path.read_text() == 'first'
    first.lock.unlock()  # simulate a crashed process leaving its data
    third = RecoverySession(tmp_path,'test','legacy.json')
    assert third.candidates() == [first.path]
    third.close()
    first.close()


def test_empty_project_clears_media_and_probe_race(app, monkeypatch, tmp_path):
    from PySide6.QtCore import QUrl
    from ui.window import Window
    monkeypatch.setattr(Window,'recover',lambda self:None)
    window = Window();window.autopath=tmp_path/'recovery.json'
    monkeypatch.setattr(window,'error',lambda error: pytest.fail(str(error)))
    window.info['duration'] = 9000
    window.player.setSource(QUrl.fromLocalFile(str(Path('examples/Film demonstracyjny.mp4').resolve())))
    saved=tmp_path/'empty.json';save(Project(),saved)
    window.open_project(str(saved))
    assert window.player.source().isEmpty() and window.info['duration'] == 0
    queued=[]
    class Pool:
        def start(self,job):queued.append(job)
    window.pool=Pool();loaded=[]
    monkeypatch.setattr(window,'set_video',lambda path,info:loaded.append(path))
    window.open_video('old.mp4');window.open_video('new.mp4')
    queued[1].signals.success({});queued[0].signals.success({})
    assert loaded == ['new.mp4']
    window.dirty=False;window.close()


def test_word_split_preserves_real_alignment_and_rejects_single_word(app,monkeypatch,tmp_path):
    from ui.window import Window
    monkeypatch.setattr(Window,'recover',lambda self:None)
    window=Window();window.autopath=tmp_path/'recovery.json'
    errors=[];monkeypatch.setattr(window,'error',errors.append)
    original=Segment(0,2000,'one two three',words=[dict(text='one',start=0,end=400),
        dict(text='two',start=800,end=1200),dict(text='three',start=1500,end=2000)])
    expected = copy.deepcopy(original)
    window.track().segments=[original];window.refresh();window.table.selectRow(0)
    monkeypatch.setattr(window.player,'position',lambda:1400)
    window.split_segment()
    assert [(s.start,s.end,s.text) for s in window.track().segments] == [(0,1500,'one two'),(1500,2000,'three')]
    assert window.track().segments[1].words[0]['start'] == 1500
    window.undo();assert window.track().segments == [expected]
    window.track().segments=[Segment(0,2000,'word')];window.refresh()
    window.table.clearSelection();window.table.selectRow(0)
    assert window.selected() == [0]
    window.split_segment();assert errors and len(window.track().segments) == 1
    window.dirty=False;window.close()


def test_audio_tools_share_local_exe_lookup(monkeypatch,tmp_path):
    import sys
    from core.media.tools import binary
    from srtstudio.audio import binary as speech_binary
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'executable',str(tmp_path/'SubtitleStudio.exe'))
    for name in ('ffmpeg','ffprobe'):
        target=tmp_path/(name+'.exe');target.write_bytes(b'not executed')
        assert binary(name) == speech_binary(name) == str(target)


def test_asr_invalid_duration_reports_error_without_importing_model():
    from types import SimpleNamespace
    from srtstudio.engine import worker
    events=[]
    worker('asr',dict(duration=0),SimpleNamespace(put=events.append))
    assert events[0][0] == 'error' and not any(e[0]=='done' for e in events)
