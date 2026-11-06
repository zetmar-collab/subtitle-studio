from pathlib import Path
import subprocess
import threading
import time
import array
import pytest
from core.media.tools import binary, probe, FLAGS
from core.media.join import join_videos


@pytest.fixture
def clips(tmp_path):
    first = tmp_path/'Pierwszy z dźwiękiem.mp4'
    second = tmp_path/'Drugi pionowy bez audio.mp4'
    base = [binary('ffmpeg'),'-v','error','-y','-f','lavfi']
    subprocess.run(base+['-i','color=c=red:s=320x180:r=12','-f','lavfi','-i','sine=frequency=440',
                        '-t','0.5','-c:v','libx264','-c:a','aac',str(first)],check=True,creationflags=FLAGS)
    subprocess.run(base+['-i','color=c=blue:s=180x320:r=12','-t','0.5','-c:v','libx264',str(second)],check=True,creationflags=FLAGS)
    return [first,second]


def test_join_normalizes_order_size_and_missing_audio(clips,tmp_path):
    output = tmp_path/'Łączenie.mp4'
    join_videos(clips,output,dict(width=320,height=180,fps=12))
    result = probe(output)
    assert result['width'] == 320 and result['height'] == 180
    assert abs(result['duration']-1000) < 200
    assert sum(s['codec_type'] == 'audio' for s in result['streams']) == 1
    def pixel(seconds):
        data = subprocess.run([binary('ffmpeg'),'-v','error','-ss',str(seconds),'-i',str(output),
                               '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True,creationflags=FLAGS).stdout
        offset = (90*320+160)*3
        return data[offset:offset+3]
    red,green,blue = pixel(.2)
    assert red > blue+150
    red,green,blue = pixel(.8)
    assert blue > red+150
    def audio_energy(seconds):
        data = subprocess.run([binary('ffmpeg'),'-v','error','-ss',str(seconds),'-i',str(output),
                               '-t','0.1','-vn','-ac','1','-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=FLAGS).stdout
        samples = array.array('f',data)
        return sum(sample*sample for sample in samples)/len(samples)
    assert audio_energy(.15) > .001
    assert audio_energy(.75) < .00001
    assert not list(tmp_path.glob('.subtitle-join-*'))


def test_join_cancel_preserves_existing_target(clips,tmp_path):
    target = tmp_path/'existing.mp4'
    target.write_bytes(b'preserve')
    cancel = threading.Event()
    with pytest.raises(InterruptedError):
        join_videos(clips,target,dict(width=320,height=180,fps=12),lambda _: cancel.set(),cancel.is_set)
    assert target.read_bytes() == b'preserve'
    assert not list(tmp_path.glob('.subtitle-join-*'))


def test_join_dialog_real_worker(app,clips,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from ui.window import Window
    from ui.join import JoinDialog
    monkeypatch.setattr(Window,'recover',lambda self: None)
    target = tmp_path/'dialog.mp4'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args: (str(target),'MP4'))
    window = Window()
    dialog = JoinDialog(window)
    dialog.files.addItems([str(p) for p in clips])
    dialog.size_combo.setCurrentIndex(3)
    dialog.fps.setValue(12)
    dialog.start.click()
    deadline = time.monotonic()+30
    while dialog.process and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)
    assert dialog.process is None
    assert dialog.open_button.isEnabled(), dialog.message.text()
    assert target.exists()
    dialog.close()
    window.dirty = False
    window.close()
