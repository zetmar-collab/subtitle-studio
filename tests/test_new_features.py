import copy
import json
import subprocess
import time
import wave
from pathlib import Path
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtGui import QColor,QImage,QMouseEvent
from PySide6.QtTest import QTest
from core.projects.model import Project,Segment
from core.media.tools import binary,probe


def wait(app,predicate,seconds=30):
    deadline=time.monotonic()+seconds
    while not predicate() and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert predicate()


@pytest.fixture
def media(tmp_path,app):
    pictures=[]
    for color in ('red','green'):
        path=tmp_path/(color+'.png');image=QImage(96,64,QImage.Format.Format_RGB888);image.fill(QColor(color));image.save(str(path));pictures.append(path)
    audio=tmp_path/'sound.wav'
    with wave.open(str(audio),'wb') as output:
        output.setparams((1,2,16000,0,'NONE',''));output.writeframes(b'\0'*64000)
    video=tmp_path/'clip.mp4'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=blue:s=96x64:r=10:d=0.5',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True,capture_output=True,timeout=20)
    return pictures,audio,video


def test_overlap_sweep_and_non_destructive_repair():
    import random
    from core.subtitles.service import overlap_flags
    from core.subtitles.repair import propose
    rng=random.Random(42)
    segments=[Segment(start:=rng.randrange(10000),start+rng.randrange(1,100),'text') for _ in range(500)]
    expected=[any(other is not s and other.start<s.end and other.end>s.start for other in segments) for s in segments]
    assert overlap_flags(segments)==expected
    original=[Segment(-50,0,'one'),Segment(0,1200,'two'),Segment(400,3000,'three')]
    before=copy.deepcopy(original);fixed=propose(original,2000)
    assert original==before and [s.text for s in fixed]==[s.text for s in original]
    assert all(0<=s.start<s.end<=2000 for s in fixed)
    assert all(a.end<=b.start for a,b in zip(fixed,fixed[1:]))
    assert not any(overlap_flags(fixed))


def test_word_drag_preview_cancel_apply_undo(app,monkeypatch,tmp_path):
    from ui.window import Window
    from ui.word_timing import WordTimingDialog
    monkeypatch.setattr(Window,'recover',lambda self:None)
    owner=Window();owner.autopath=tmp_path/'recovery.json'
    original=Segment(0,2000,'one two',words=[dict(text='one',start=0,end=800),dict(text='two',start=1000,end=2000)])
    owner.track().segments=[original];owner.timeline.wave=[.5]*100;owner.info['duration']=2000
    before=copy.deepcopy(original)
    dialog=WordTimingDialog(owner,0);dialog.show();app.processEvents()
    canvas=dialog.canvas
    start=QPoint(round(canvas.x_at(800)),85);end=QPoint(round(canvas.x_at(600)),85)
    QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=start)
    event=QMouseEvent(QMouseEvent.Type.MouseMove,QPointF(end),QPointF(canvas.mapToGlobal(end)),
                     Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    app.sendEvent(canvas,event);QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=end)
    assert abs(dialog.segment.words[0]['end']-600)<=3
    assert owner.track().segments[0]==before
    dialog.apply();assert owner.track().style.effect=='highlight'
    assert abs(owner.track().segments[0].words[0]['end']-600)<=3
    owner.undo();assert owner.track().segments[0]==before
    dialog.reject();owner.dirty=False;owner.close()


@pytest.mark.parametrize('effects',[False,True])
def test_slideshow_actual_photo_order_audio_and_duration(media,tmp_path,app,effects):
    from core.media.slideshow import slideshow
    pictures,audio,_=media;target=tmp_path/'show.mp4'
    slideshow([dict(path=str(path),seconds=1) for path in pictures],audio,target,
              dict(width=96,height=64,fps=10,auto_duration=True,motion=effects,fade=effects))
    info=probe(target);assert abs(info['duration']-2000)<150
    assert sum(s['codec_type']=='audio' for s in info['streams'])==1
    for at,expected in ((.5,'red'),(1.5,'green')):
        raw=subprocess.run([binary('ffmpeg'),'-v','error','-ss',str(at),'-i',str(target),'-frames:v','1',
            '-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True,timeout=20).stdout
        color=QImage(raw,96,64,96*3,QImage.Format.Format_RGB888).pixelColor(48,32)
        assert color.red()>200 if expected=='red' else color.green()>90


def test_slideshow_mixed_clip_loop_and_cancel_preserves_target(media,tmp_path,app):
    from core.media.slideshow import slideshow
    pictures,audio,video=media;target=tmp_path/'mixed.mp4'
    clips=[dict(path=str(pictures[0]),seconds=.5),dict(path=str(video),seconds=.5)]
    slideshow(clips,audio,target,dict(width=96,height=64,fps=10,length='loop'))
    assert abs(probe(target)['duration']-2000)<150
    before=target.read_bytes();progress=[]
    with pytest.raises(InterruptedError):
        slideshow(clips,audio,target,dict(width=96,height=64,fps=10),progress.append,lambda:bool(progress))
    assert target.read_bytes()==before
    assert not list(tmp_path.glob('.subtitle-show-*'))


def test_slideshow_zoom_really_changes_photo_framing(media,tmp_path,app):
    from core.media.slideshow import slideshow
    _,audio,_=media;image=QImage(96,64,QImage.Format.Format_RGB888);image.fill(QColor('red'))
    from PySide6.QtGui import QPainter
    painter=QPainter(image);painter.fillRect(0,0,8,64,QColor('green'));painter.end()
    photo=tmp_path/'motion.png';image.save(str(photo));target=tmp_path/'motion.mp4'
    slideshow([dict(path=str(photo),seconds=2)],audio,target,dict(width=96,height=64,fps=10,motion=True,auto_duration=True))
    colors=[]
    for at in (.1,1.8):
        raw=subprocess.run([binary('ffmpeg'),'-v','error','-ss',str(at),'-i',str(target),'-frames:v','1',
            '-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True,timeout=20).stdout
        colors.append(QImage(raw,96,64,96*3,QImage.Format.Format_RGB888).pixelColor(6,32))
    assert colors[0].green()>70 and colors[1].red()>180


def test_queue_real_workers_snapshot_resume_and_exclusive_lock(media,tmp_path,app):
    from PySide6.QtCore import QObject
    from core.export.queue import ExportQueue
    _,_,video=media;owner=QObject();queue=ExportQueue(owner,tmp_path/'first.exports.json')
    project=Project(video=str(video));project.tracks[0].segments=[Segment(0,500,'test')]
    targets=[tmp_path/'wide.mp4',tmp_path/'portrait.mp4']
    options=[dict(width=96,height=64,fps=10,codec='libx264'),dict(width=64,height=96,fps=10,codec='libx264',fit='crop')]
    queue.add(project,targets,options);project.tracks[0].segments[0].text='later edit'
    assert queue.jobs[0]['project']['tracks'][0]['segments'][0]['text']=='test'
    second=ExportQueue(owner,tmp_path/'other.exports.json')
    with pytest.raises(ValueError):second.load(queue.path)
    queue.start();wait(app,lambda:not queue.active and not queue.running)
    assert [job['state'] for job in queue.jobs]==['done','done']
    assert (probe(targets[1])['width'],probe(targets[1])['height'])==(64,96)
    first_path=queue.path;queue.release();second.load(first_path)
    assert all(job['state']=='done' for job in second.jobs)
    data=json.loads(first_path.read_text(encoding='utf-8'));data['jobs'][0]['state']='running'
    first_path.write_text(json.dumps(data),encoding='utf-8');second.load(first_path)
    assert second.jobs[0]['state']=='queued'
    second.release()


def test_worker_failed_start_rolls_back(app,monkeypatch,tmp_path):
    from srtstudio.jobs import Job
    import srtstudio.jobs as jobs
    closed=[]
    class Process:
        def start(self):raise OSError('start failed')
        def close(self):closed.append('process')
    queue=SimpleNamespace(close=lambda:closed.append('queue'))
    context=SimpleNamespace(Queue=lambda:queue,Process=lambda **kwargs:Process())
    monkeypatch.setattr(jobs.mp,'get_context',lambda *args:context)
    job=Job();events=[];finished=[];job.event.connect(events.append);job.finished.connect(finished.append)
    job.start('probe',{},tmp_path)
    assert not job.active and not job.work.exists()
    assert events[0][0]=='error' and finished==[False] and closed==['process','queue']


def test_cancel_blocked_renderer_read_kills_children(app,tmp_path,monkeypatch):
    import threading
    import io
    import core.export.worker as worker
    cancelled=threading.Event();killed=[]
    class Process:
        def __init__(self,*args,**kwargs):self.stdout=self;self.stdin=io.BytesIO();self.done=threading.Event()
        def read(self,size):self.done.wait(5);return b''
        def poll(self):return 0 if self.done.is_set() else None
        def kill(self):killed.append(self);self.done.set()
        def wait(self,**kwargs):return 0
        def close(self):pass
    monkeypatch.setattr(worker,'probe',lambda path:dict(width=96,height=64,duration=500,fps=10,streams=[]))
    monkeypatch.setattr(worker.subprocess,'Popen',Process)
    timer=threading.Timer(.2,cancelled.set);timer.start()
    with pytest.raises(InterruptedError):
        worker.render(Project(video='dummy'),tmp_path/'out.mp4',dict(width=96,height=64,fps=10),cancelled=cancelled.is_set)
    timer.join();assert len(killed)==2 and not (tmp_path/'out.mp4').exists()


@pytest.mark.parametrize('transient_lock',[False,True])
def test_renderer_cleanup_waits_for_exited_children_before_removal(app,tmp_path,monkeypatch,transient_lock):
    import io
    from core.export import worker
    children=[];waited=[];attempts=[]
    class ExitedProcess:
        def __init__(self,*args,**kwargs):
            self.stdin=io.BytesIO();self.stdout=io.BytesIO();children.append(self)
        def poll(self):return 0
        def wait(self,**kwargs):waited.append(self);return 0
    real_unlink=Path.unlink
    def unlink(path,*args,**kwargs):
        if path.name.startswith('.subtitle-'):
            assert waited==children
            assert all(child.stdin.closed and child.stdout.closed for child in children)
            attempts.append(path)
            if transient_lock and len(attempts)==1:raise PermissionError('Temporary Windows lock')
        return real_unlink(path,*args,**kwargs)
    monkeypatch.setattr(worker,'probe',lambda path:dict(width=96,height=64,duration=500,fps=10,streams=[]))
    monkeypatch.setattr(worker.subprocess,'Popen',ExitedProcess)
    monkeypatch.setattr(Path,'unlink',unlink)
    target=tmp_path/'existing.mp4';target.write_bytes(b'preserve user file')
    with pytest.raises(InterruptedError):
        worker.render(Project(video='dummy'),target,dict(width=96,height=64,fps=10),cancelled=lambda:True)
    assert len(attempts)==(2 if transient_lock else 1)
    assert target.read_bytes()==b'preserve user file' and not list(tmp_path.glob('.subtitle-*'))


def test_history_budget_and_image_cache_limits(app,tmp_path,monkeypatch):
    from core.projects.history import trim,byte_size
    from collections import OrderedDict
    import core.compositor.render as render
    owner=SimpleNamespace(history=[dict(text=str(i)*2000) for i in range(20)],future=[])
    trim(owner,budget=12000)
    assert sum(byte_size(state) for state in owner.history)<=12000
    monkeypatch.setattr(render,'_images',OrderedDict());monkeypatch.setattr(render,'_image_bytes',0)
    monkeypatch.setattr(render,'IMAGE_CACHE_BYTES',4096)
    for index in range(4):
        image=QImage(100,100,QImage.Format.Format_ARGB32);image.fill(QColor('red'))
        path=tmp_path/f'{index}.png';image.save(str(path));render.image(str(path))
    assert sum(value.sizeInBytes() for value in render._images.values())<=4096
