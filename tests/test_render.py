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


@pytest.mark.parametrize('effect',['typewriter','words'])
def test_reveal_keeps_text_positions_and_background_fixed(app,effect):
    project=Project();track=project.tracks[0]
    track.segments=[Segment(0,3000,'Pierwsze drugie trzecie czwarte piąte')]
    track.style.effect=effect;track.style.animation_ms=2000;track.style.width=38
    track.style.size=80;track.style.y=50;track.style.background='#142134';track.style.stroke=0
    frame=QImage(640,360,QImage.Format.Format_RGB888);frame.fill(QColor('black'))
    early=compose(frame,project,550);late=compose(frame,project,2500)
    white=QColor(track.style.color).rgb();black=QColor('black').rgb()
    # Revealed glyphs keep exactly the same pixels; the full box never jumps.
    early_ink={(x,y) for y in range(360) for x in range(640) if early.pixel(x,y)==white}
    assert early_ink and all(late.pixel(x,y)==white for x,y in early_ink)
    bounds=lambda img:{(x,y) for y in range(360) for x in range(640) if img.pixel(x,y)!=black}
    assert bounds(early)==bounds(late)


def test_words_use_asr_starts_and_highlight_does_not_flash_in_pause(app):
    project=Project();track=project.tracks[0]
    track.segments=[Segment(0,3000,'raz dwa',words=[dict(text='raz',start=100,end=600),dict(text='dwa',start=2000,end=2800)])]
    track.style.effect='words';track.style.size=90
    frame=QImage(640,360,QImage.Format.Format_RGB888);frame.fill(QColor('black'))
    assert pixels(compose(frame,project,200))==pixels(compose(frame,project,1500))
    assert pixels(compose(frame,project,2100))!=pixels(compose(frame,project,1500))
    track.style.effect='highlight'
    assert pixels(compose(frame,project,200))==pixels(compose(frame,project,1500))
    assert pixels(compose(frame,project,2100))!=pixels(compose(frame,project,1500))


def test_stale_word_text_uses_equal_intervals_and_graphemes_stay_whole(app):
    from core.compositor.render import aligned_words,graphemes,text_lines
    from PySide6.QtGui import QFont,QFontMetricsF
    assert graphemes('A\U0001f469\u200d\U0001f4bb\U0001f1f5\U0001f1f1e\u0301')==['A','\U0001f469\u200d\U0001f4bb','\U0001f1f5\U0001f1f1','e\u0301']
    segment=Segment(0,2000,'nowe słowa',words=[dict(text='stare',start=0,end=100),dict(text='słowa',start=200,end=300)])
    assert not aligned_words(segment,segment.text)
    font=QFont('Arial');font.setPixelSize(36);fm=QFontMetricsF(font)
    lines=text_lines('Bardzodługiesłowobezspacji',fm,120)
    assert len(lines)>1 and all(fm.horizontalAdvance(line)<=120 for line,_ in lines)


@pytest.fixture
def video(tmp_path):
    path = tmp_path/'Źródło ze spacją.mp4'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=0x263349:s=640x360:r=12',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-c:a','aac',str(path)],check=True,creationflags=FLAGS)
    return path


@pytest.mark.parametrize('effect',['static','fade','left','right','up','typewriter','words','highlight','pop'])
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


def test_export_range_keeps_original_subtitle_time_and_audio(app,video,tmp_path):
    project = Project(video=str(video))
    project.tracks[0].segments = [Segment(1000,1600,'Zakres filmu')]
    output = tmp_path/'range.mp4'
    render(project,output,dict(start=1,seconds=.5,fps=12,crf=10))
    info = probe(output)
    assert abs(info['duration']-500) < 150
    assert sum(s['codec_type'] == 'audio' for s in info['streams']) == 1
    raw = subprocess.run([binary('ffmpeg'),'-v','error','-ss','0.1','-i',str(output),'-frames:v','1',
                          '-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True,creationflags=FLAGS).stdout
    actual = QImage(raw,640,360,640*3,QImage.Format.Format_RGB888).copy()
    frame = QImage(640,360,QImage.Format.Format_RGB888)
    frame.fill(QColor('#263349'))
    expected = compose(frame,project,1100)
    assert sum(abs(a-b) for a,b in zip(pixels(expected),pixels(actual)))/len(raw) < 3


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
