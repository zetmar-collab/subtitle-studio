import array
from pathlib import Path
import subprocess
import threading
import time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QColor
from core.media.create_video import create_video
from core.media.tools import binary, probe, FLAGS


@pytest.fixture
def sources(app,tmp_path):
    image = tmp_path/'Zdjęcie z kolorami.png'
    frame = QImage(200,100,QImage.Format.Format_RGB888)
    frame.fill(QColor('lime'))
    painter = QPainter(frame)
    painter.fillRect(0,0,50,100,QColor('red'))
    painter.fillRect(150,0,50,100,QColor('blue'))
    painter.end()
    assert frame.save(str(image))
    audio = tmp_path/'Dźwięk 880 Hz.wav'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','sine=frequency=880:sample_rate=48000',
                    '-t','1.2',str(audio)],check=True,creationflags=FLAGS)
    video = tmp_path/'Film z oryginalnym audio.mp4'
    graph = 'color=c=red:s=160x90:r=12:d=0.25[r];color=c=blue:s=160x90:r=12:d=0.25[b];[r][b]concat=n=2:v=1:a=0'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i',graph,
                    '-f','lavfi','-i','sine=frequency=220:sample_rate=48000','-t','0.5',
                    '-c:v','libx264','-c:a','aac',str(video)],check=True,creationflags=FLAGS)
    return image,audio,video


def pixel(path,seconds,x,y,width):
    data = subprocess.run([binary('ffmpeg'),'-v','error','-ss',str(seconds),'-i',str(path),
                           '-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],
                          capture_output=True,check=True,creationflags=FLAGS).stdout
    offset = (y*width+x)*3
    return data[offset:offset+3]


@pytest.mark.parametrize('width,height',[(160,90),(90,160),(100,100),(80,100),(120,90),(136,96)])
def test_image_audio_in_different_aspects(app,sources,tmp_path,width,height):
    image,audio,_ = sources
    target = tmp_path/'new.mp4'
    progress = []
    create_video(image,audio,target,dict(width=width,height=height,fps=12),progress.append)
    result = probe(target)
    assert (result['width'],result['height']) == (width,height)
    assert abs(result['duration']-1200) < 150
    assert sum(s['codec_type']=='audio' for s in result['streams']) == 1
    assert progress[-1]['percent'] == 100
    red,green,blue = pixel(target,.9,width//2,height//2,width)
    assert green > 200 and red < 30 and blue < 30


def test_fit_bars_and_center_crop(app,sources,tmp_path):
    image,audio,_ = sources
    colors = {}
    for mode in ('fit','crop'):
        target = tmp_path/f'{mode}.mp4'
        create_video(image,audio,target,dict(width=90,height=160,fps=12,fit=mode))
        colors[mode] = pixel(target,.3,5,5,90)
    assert max(colors['fit']) < 20
    assert colors['crop'][1] > 200


@pytest.mark.parametrize('mode,expected_duration', [('loop',1200),('freeze',1200),('shortest',500)])
def test_video_length_modes_and_external_sound(app,sources,tmp_path,mode,expected_duration):
    _,audio,video = sources
    target = tmp_path/'result.mp4'
    create_video(video,audio,target,dict(width=160,height=90,fps=12,length=mode))
    result = probe(target)
    assert abs(result['duration']-expected_duration) < 150
    if mode != 'shortest':
        red,green,blue = pixel(target,.62,80,45,160)
        assert (red > blue+150) if mode == 'loop' else (blue > red+150)
    raw = subprocess.run([binary('ffmpeg'),'-v','error','-ss','0.1','-i',str(target),'-t','0.2',
                          '-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],
                         capture_output=True,check=True,creationflags=FLAGS).stdout
    samples = array.array('f',raw)
    frequency = sum(a <= 0 < b for a,b in zip(samples,samples[1:]))/(len(samples)/48000)
    assert abs(frequency-880) < 30


def test_cancel_and_source_protection(app,sources,tmp_path):
    image,audio,_ = sources
    original = image.read_bytes()
    with pytest.raises(ValueError):
        create_video(image,audio,image,{})
    assert image.read_bytes() == original
    target = tmp_path/'old.mp4'
    target.write_bytes(b'preserve')
    cancel = threading.Event()
    with pytest.raises(InterruptedError):
        create_video(image,audio,target,dict(width=160,height=90,fps=12),lambda _: cancel.set(),cancel.is_set)
    assert target.read_bytes() == b'preserve'
    assert not list(tmp_path.glob('.subtitle-create-*'))


def test_invalid_audio(app,sources,tmp_path):
    image,_,_ = sources
    with pytest.raises(ValueError,match='audio'):
        create_video(image,image,tmp_path/'invalid.mp4',dict(width=160,height=90,fps=12))


def test_creator_dialog_real_process_and_preview(app,sources,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from ui.window import Window
    from ui.create_video import CreateVideoDialog
    monkeypatch.setattr(Window,'recover',lambda self: None)
    target = tmp_path/'GUI result.mp4'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args: (str(target),'MP4'))
    window = Window()
    dialog = CreateVideoDialog(window)
    dialog.set_visual(str(sources[0]))
    dialog.audio_path.setText(str(sources[1]))
    dialog.profile.setCurrentIndex(len(dialog.profiles)-1)
    dialog.width_box.setValue(90)
    dialog.height_box.setValue(160)
    dialog.fps.setValue(12)
    dialog.start.click()
    deadline = time.monotonic()+30
    while (dialog.process or dialog.frame.isNull()) and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)
    assert dialog.process is None
    assert dialog.open_button.isEnabled(), dialog.message.text()
    assert not dialog.preview_label.pixmap().isNull()
    assert dialog.width_box.isEnabled()
    assert not dialog.length_mode.isEnabled()
    assert probe(target)['height'] == 160
    dialog.close()
    window.dirty = False
    window.close()
