import os
from pathlib import Path
import subprocess
import pytest
from PySide6.QtGui import QImage, QColor
from core.projects.model import Project, Segment, Logo
from core.compositor.render import compose, image
from core.media.tools import binary, probe, FLAGS
from core.export.worker import render


def pixels(img):
    return bytes(img.constBits())


@pytest.mark.parametrize('effect',['static','fade','left','right','up','typewriter','words','highlight','pop'])
def test_deterministic_seeking(app,effect):
    p = Project(); p.tracks[0].segments = [Segment(0,2000,'Pierwsze drugie',words=[dict(text='Pierwsze',start=0,end=1000),dict(text='drugie',start=1000,end=2000)])]
    p.tracks[0].style.effect = effect
    frame = QImage(640,360,QImage.Format.Format_RGB888); frame.fill(QColor('#263349'))
    first = pixels(compose(frame,p,500)); compose(frame,p,1800)
    assert first == pixels(compose(frame,p,500))
    assert first != pixels(compose(frame,p,2200))


def test_manual_word_changes_color(app):
    p = Project(); p.tracks[0].style.effect = 'highlight'
    p.tracks[0].segments = [Segment(0,2000,'raz dwa',words=[dict(start=0,end=1000),dict(start=1000,end=2000)])]
    frame = QImage(640,360,QImage.Format.Format_RGB888); frame.fill(QColor('black'))
    assert pixels(compose(frame,p,500)) != pixels(compose(frame,p,1500))


def test_highlight_without_word_timings(app):
    project = Project()
    track = project.tracks[0]
    track.style.effect = 'highlight'
    track.style.size = 90
    track.segments = [Segment(1000, 3000, '<i>raz</i>\ndwa')]
    frame = QImage(640, 360, QImage.Format.Format_RGB888)
    frame.fill(QColor('black'))
    first = compose(frame, project, 1500)
    second = compose(frame, project, 2500)
    highlight = QColor(track.style.active_color).rgb()
    highlighted_rows = lambda img: {y for y in range(240, 360) for x in range(250, 390)
                                    if img.pixel(x, y) == highlight}
    assert max(highlighted_rows(first)) < min(highlighted_rows(second))
    assert track.segments[0].words == []


@pytest.mark.parametrize('effect', ['fade', 'left', 'right', 'up', 'typewriter', 'words', 'pop'])
def test_animation_changes_then_reaches_static_frame(app, effect):
    project = Project()
    track = project.tracks[0]
    track.segments = [Segment(0, 2000, 'Pierwsze drugie trzecie')]
    track.style.animation_ms = 800
    frame = QImage(640, 360, QImage.Format.Format_RGB888)
    frame.fill(QColor('black'))
    static = pixels(compose(frame, project, 900))
    track.style.effect = effect
    assert pixels(compose(frame, project, 150)) != static
    assert pixels(compose(frame, project, 900)) == static


@pytest.fixture
def video(tmp_path):
    path = tmp_path/'Źródło ze spacją.mp4'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=0x263349:s=640x360:r=12',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-c:a','aac',str(path)],check=True,creationflags=FLAGS)
    return path


@pytest.mark.parametrize('effect',['static','typewriter','left','right','highlight'])
def test_real_export_audio_overlay_and_frame_match(app,video,tmp_path,effect):
    p = Project(video=str(video)); p.tracks[0].style.effect = effect
    p.tracks[0].segments = [Segment(250,1750,'Zażółć gęślą',words=[dict(start=250,end=1000),dict(start=1000,end=1750)])]
    logo = QImage(80,40,QImage.Format.Format_ARGB32); logo.fill(QColor('#80ff0000'))
    logo_path = tmp_path/'logo.png'; logo.save(str(logo_path))
    p.logos.append(Logo(path=str(logo_path),width=20,opacity=50))
    target = tmp_path/f'{effect}.mp4'
    progress = []
    render(p,target,dict(fps=12,crf=10),progress.append)
    info = probe(target)
    assert any(s['codec_type'] == 'audio' for s in info['streams'])
    assert info['duration'] >= 1900 and progress[-1]['percent'] == 100
    def frame(path):
        raw = subprocess.run([binary('ffmpeg'),'-v','error','-ss','0.75','-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True,creationflags=FLAGS).stdout
        return QImage(raw,640,360,640*3,QImage.Format.Format_RGB888).copy()
    source = frame(video)
    expected = pixels(compose(source,p,750)); actual = pixels(frame(target))
    # Lossy H.264 and YUV chroma subsampling allow small pixel differences.
    difference = sum(abs(a-b) for a,b in zip(expected,actual))/len(actual)
    assert difference < 3
    assert pixels(source) != actual


def test_cancel_removes_partial_and_preserves_target(app,video,tmp_path):
    target = tmp_path/'old.mp4'; target.write_bytes(b'keep-existing')
    calls = [0]
    def cancel():
        calls[0] += 1
        return calls[0] > 3
    with pytest.raises(InterruptedError):
        render(Project(video=str(video)),target,dict(fps=12),cancelled=cancel)
    assert target.read_bytes() == b'keep-existing'
    assert not list(tmp_path.glob('.subtitle-*'))


def test_portrait_fit_and_corrupt_input(app,video,tmp_path):
    target = tmp_path/'portrait.mp4'
    render(Project(video=str(video)),target,dict(width=180,height=320,fps=12))
    assert (probe(target)['width'],probe(target)['height']) == (180,320)
    corrupt = tmp_path/'bad.mp4'; corrupt.write_bytes(b'not a movie')
    with pytest.raises(ValueError):
        probe(corrupt)


@pytest.mark.parametrize('codec,suffix',[('libx265','mp4'),('libvpx-vp9','webm'),('libx264','mkv')])
def test_other_profiles(app,video,tmp_path,codec,suffix):
    target = tmp_path/f'profile.{suffix}'
    render(Project(video=str(video)),target,dict(width=320,height=180,fps=12,codec=codec))
    info = probe(target)
    assert any(s['codec_type'] == 'audio' for s in info['streams'])


def test_vfr_two_audio_tracks_and_1080p(app,tmp_path):
    path = tmp_path/'Zmienny FPS.mp4'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','testsrc2=s=1920x1080:r=24',
        '-f','lavfi','-i','sine=frequency=440','-f','lavfi','-i','sine=frequency=880',
        '-t','1.5','-vf',r'select=not(mod(n\,3))+not(mod(n\,5))','-fps_mode','vfr',
        '-map','0:v','-map','1:a','-map','2:a','-c:v','libx264','-preset','ultrafast','-c:a','aac',str(path)],check=True,creationflags=FLAGS)
    p = Project(video=str(path)); p.tracks[0].segments = [Segment(0,700,'Literówka poprawiona')]
    from core.subtitles.service import shift
    shift(p.tracks[0].segments,500)
    target = tmp_path/'Wynik 1080p.mp4'
    render(p,target,dict(fps=24))
    info = probe(target)
    assert (info['width'],info['height']) == (1920,1080)
    assert sum(s['codec_type'] == 'audio' for s in info['streams']) == 2
