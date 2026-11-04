import pytest
from core.subtitles.service import read, write, shift, stretch, warnings
from core.projects.model import Segment, Project, Logo, save, load


@pytest.mark.parametrize('ext', ['srt','vtt','ass'])
def test_unicode_roundtrip(tmp_path, ext):
    path = tmp_path/f'Zażółć.{ext}'
    source = [Segment(1250,3500,'Zażółć gęślą jaźń\nУкраїна')]
    write(source, path)
    result = read(path)
    assert result[0].text == source[0].text
    assert (result[0].start,result[0].end) == (1250,3500)


def test_txt_is_untimed(tmp_path):
    path = tmp_path/'text.txt'; path.write_text('Pierwszy\nDrugi',encoding='utf-8')
    segments = read(path)
    assert len(segments) == 2 and not any(s.timed for s in segments)
    with pytest.raises(ValueError):
        write(segments,tmp_path/'output.srt')


def test_encoding_and_shift(tmp_path):
    path = tmp_path/'old.srt'
    path.write_bytes('1\n00:00:01,000 --> 00:00:02,000\nZażółć'.encode('cp1250'))
    segments = read(path,'cp1250')
    assert segments[0].text == 'Zażółć'
    segments[0].words = [dict(text='Zażółć',start=1000,end=2000)]
    shift(segments,500)
    assert segments[0].start == 1500 and segments[0].words[0]['end'] == 2500
    with pytest.raises(ValueError):
        shift(segments,-2000)
    assert segments[0].start == 1500


def test_stretch_and_quality():
    segments = [Segment(1000,2000,'Cześć'), Segment(1800,3000,'Test')]
    assert 'Overlap' in warnings(segments,2500)[0]
    stretch(segments,1000,3000,2000,6000)
    assert segments[0].start == 2000 and segments[-1].end == 6000


def test_relative_project_and_no_mutation(tmp_path):
    video = tmp_path/'film.mp4'; video.write_bytes(b'original')
    logo = tmp_path/'logo.png'; logo.write_bytes(b'original')
    project = Project(video=str(video),logos=[Logo(path=str(logo))])
    project.tracks[0].segments = [Segment(10,1000,'Łódź',words=[dict(text='Łódź',start=10,end=1000)])]
    path = tmp_path/'project.subtitlelogo.json'; save(project,path)
    assert '"video": "film.mp4"' in path.read_text(encoding='utf-8')
    result = load(path)
    assert result.data() == project.data()
    assert video.read_bytes() == b'original'


def test_reject_unknown_version():
    with pytest.raises(ValueError):
        Project.from_data(dict(version=99))


@pytest.mark.parametrize('ext,text',[
    ('sbv','0:00:01.000,0:00:02.500\nZażółć'),
    ('sub','{25}{50}Zażółć'),
    ('mpl2','[10][25]Zażółć'),
    ('ttml','<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body><div><p begin="00:00:01.000" end="00:00:02.500">Zażółć</p></div></body></tt>'),
    ('smi','<SAMI><BODY><SYNC Start=1000><P Class=PLCC>Zażółć<SYNC Start=2500><P Class=PLCC>&nbsp;</BODY></SAMI>')])
def test_additional_formats(tmp_path,ext,text):
    path = tmp_path/f'test.{ext}'; path.write_text(text,encoding='utf-8')
    result = read(path,fps=25)
    assert result[0].start == 1000
    assert 'Zażółć' in result[0].text
