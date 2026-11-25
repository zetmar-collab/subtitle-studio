import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from core.compositor.render import compose
from core.projects.model import Banner, Project, load, save


def test_banner_roundtrip_and_legacy(tmp_path):
    project = Project()
    assert project.data()['version']==2 and 'banners' not in project.data()
    project.banners.append(Banner(text='Zażółć gęślą',width=60,height=12,x=40,y=30))
    save(project,tmp_path/'project.json')
    restored = load(tmp_path/'project.json')
    assert restored.banners==project.banners and restored.data()['version']==3
    with pytest.raises(ValueError):
        Project.from_data(dict(project.data(),banners=[project.data()['banners'][0]]*2))


@pytest.mark.parametrize('change',[{'width':0},{'height':float('nan')},{'x':True},
    {'start':20,'end':10},{'background':'invalid'},{'visible':'yes'},{'font_size':500}])
def test_banner_validation(change):
    with pytest.raises(ValueError):
        Banner(**change).validate()


def test_banner_render_geometry_timing(app):
    frame = QImage(400,200,QImage.Format.Format_RGB888); frame.fill(QColor('black'))
    banner = Banner(text='',background='#ff0000',radius=0,x=50,y=25,width=50,height=20,start=100,end=300)
    project = Project(banners=[banner])
    assert compose(frame,project,99).pixelColor(110,40)==QColor('black')
    result = compose(frame,project,100)
    assert result.pixelColor(110,40)==QColor('red')
    assert result.pixelColor(90,40)==QColor('black')
    assert result.pixelColor(110,75)==QColor('black')
    assert compose(frame,project,300).pixelColor(110,40)==QColor('black')
    assert frame.pixelColor(110,40)==QColor('black')


@pytest.fixture
def workspace(app,monkeypatch,tmp_path):
    from ui.window import Window
    from ui.workspace import Workspace
    monkeypatch.setattr(Window,'recover',lambda self:None)
    w = Workspace(); w.editor.autotimer.stop(); w.editor.autopath=tmp_path/'recovery.json'
    w.automation.start(tmp_path)
    yield w
    w.editor.player.stop(); w.editor.dirty=False
    if w.transcription: w.transcription.dirty=False
    w.close(); app.processEvents()


def test_automation_scope_and_undo(workspace,tmp_path):
    a = workspace.automation
    for path in ('../outside.txt',str(tmp_path.parent/'outside.txt')):
        with pytest.raises(ValueError): a.path(path,True)
    (tmp_path/'keep.json').write_text('keep')
    with pytest.raises(ValueError): a.path('keep.json',True)
    with pytest.raises(ValueError): a.path('keep.json',True,'yes')
    banner = a.call('banner',{'properties':{'text':'Nagłówek','width':40}})
    assert workspace.editor.project.banners[0].width==40
    a.call('banner',{'properties':{'height':30},'banner_id':banner['banner_id']})
    workspace.editor.undo()
    assert workspace.editor.project.banners[0].height==16
    with pytest.raises(ValueError): a.call('new_project',{})
    with pytest.raises(ValueError): a.call('style',{'changes':{},'track_index':-1})
    a.call('new_project',{'discard_changes':True})
    assert not workspace.editor.project.banners


def test_source_protection_and_failed_load_preserve_project(workspace,tmp_path):
    a = workspace.automation
    source = tmp_path/'source.mp4'; source.write_bytes(b'not a video')
    workspace.editor.project.video = str(source)
    with pytest.raises(ValueError): a.path(source,True,True)
    original = workspace.editor.project
    save(Project(video=str(source)),tmp_path/'broken.json')
    with pytest.raises(ValueError): a.tool_open_project('broken.json',True)
    assert workspace.editor.project is original


def test_job_cancellation(app,workspace):
    a = workspace.automation
    job = a.call('create_blank_video',{'output':'cancelled.mp4','seconds':100,'width':640,'height':360})
    with pytest.raises(ValueError): a.call('banner',{'properties':{'text':'busy'}})
    a.call('cancel',{'job_id':job['id']})
    deadline = time.monotonic()+20
    while a.tool_job(job['id'])['state']=='running' and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    assert a.tool_job(job['id'])['state']=='cancelled'
    assert not (a.root/'cancelled.mp4').exists()


def test_transcription_worker_retains_detected_language(monkeypatch,tmp_path):
    from core.automation_worker import main
    import srtstudio.engine
    def transcribe(data,queue):
        queue.put(('language','en',.99))
        queue.put(('segment',{'start':0,'end':1,'text':'Hello'}))
    monkeypatch.setattr(srtstudio.engine,'transcribe',transcribe)
    config,status,target = (tmp_path/name for name in ('config.json','status.json','transcript.json'))
    config.write_text(json.dumps({'target':str(target)}))
    main(['transcribe',str(config),str(tmp_path/'cancel'),str(status)])
    assert json.loads(status.read_text())['done']
    assert json.loads(target.read_text())[0]['spell_language']=='en'


def test_banner_dialog_is_transactional(workspace):
    from ui.banner import BannerDialog
    dialog = BannerDialog(workspace.editor)
    dialog.fields['text'].setPlainText('Nowy baner')
    dialog.fields['width'].setValue(42)
    assert dialog.value.width==42
    assert not workspace.editor.project.banners
    dialog.fields['end'].setValue(1); dialog.fields['start'].setValue(2)
    assert not dialog.save_button.isEnabled()
    dialog.reject()
    assert not workspace.editor.project.banners


@pytest.fixture
def mcp_runtime(workspace,tmp_path):
    """Use a frozen GUI and stdio companion when verifying a built package."""
    package = os.environ.get('SUBTITLE_STUDIO_TEST_PACKAGE')
    if not package:
        yield workspace.automation.endpoint, sys.executable, [str(Path(__file__).resolve().parents[1]/'main.py'),'--mcp']
        return
    from uuid import uuid4
    from core.mcp_server import request
    endpoint = 'subtitle-studio-'+uuid4().hex
    package = Path(package).resolve()
    child = subprocess.Popen([str(package/'SubtitleStudio.exe'),'--automation',str(tmp_path),endpoint],
                             stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic()+30
        while True:
            try:
                request(endpoint,'state',{}); break
            except ValueError:
                if child.poll() is not None or time.monotonic()>deadline: raise
                time.sleep(.1)
        yield endpoint,str(package/'SubtitleStudio-MCP.exe'),[]
    finally:
        child.terminate(); child.wait(timeout=10)


def test_real_stdio_mcp_creates_and_exports_video(app,workspace,tmp_path,mcp_runtime):
    """Official client -> stdio server -> live Qt IPC -> real FFmpeg workers."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from core.media.tools import binary, probe
    endpoint,command,args = mcp_runtime
    outcome = {}

    async def workflow():
        params = StdioServerParameters(command=command,args=[*args,'--connect',endpoint])
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert 'studio_set_banner' in {t.name for t in listing.tools}
                async def call(name,**args):
                    result = await session.call_tool(name,args)
                    assert not result.is_error, result
                    return json.loads(next(c.text for c in result.content if c.type=='text'))
                async def wait(job):
                    deadline = time.monotonic()+45
                    while job['state']=='running' and time.monotonic()<deadline:
                        await asyncio.sleep(.15)
                        job = await call('studio_get_job',job_id=job['id'])
                    assert job['state']=='done',job
                state = await call('studio_get_state')
                assert Path(state['root'])==tmp_path
                await wait(await call('studio_create_blank_video',output='base.mp4',seconds=1,width=320,height=180,fps=12))
                await call('studio_set_banner',properties={'text':'Film AI','background':'#ff0000','radius':0,
                           'width':60,'height':30,'x':50,'y':25,'font_size':70})
                await call('studio_set_captions',captions=[{'start':0,'end':900,'text':'Gotowe napisy'}])
                preview = await session.call_tool('studio_preview',dict(output='preview.png',width=320,height=180,time_ms=100))
                assert not preview.is_error, preview
                assert any(c.type=='image' and c.mime_type=='image/png' for c in preview.content)
                assert json.loads(next(c.text for c in preview.content if c.type=='text'))['width']==320
                templates = await call('studio_list_banner_templates')
                assert 'Tytuł / Title' in templates['templates']
                await call('studio_save_project',path='film.json')
                await wait(await call('studio_export_video',output='final.mp4',width=320,height=180,fps=12))
                await call('studio_export_captions',output='napisy.srt')
                outcome['success']=True

    def run():
        try: asyncio.run(workflow())
        except BaseException as error: outcome['error']=error
    thread = threading.Thread(target=run,daemon=True); thread.start()
    deadline = time.monotonic()+110
    while thread.is_alive() and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    assert not thread.is_alive(),'MCP workflow timed out'
    if 'error' in outcome: raise outcome['error']
    assert outcome['success']
    assert len(load(tmp_path/'film.json').banners)==1
    assert 'Gotowe napisy' in (tmp_path/'napisy.srt').read_text(encoding='utf-8')
    assert probe(tmp_path/'final.mp4')['width']==320
    result = subprocess.run([binary('ffmpeg'),'-v','error','-i',str(tmp_path/'final.mp4'),'-frames:v','1',
                             '-f','image2pipe','-c:v','png','pipe:1'],capture_output=True,timeout=15)
    image = QImage.fromData(result.stdout)
    color = image.pixelColor(70,30)
    assert color.red()>200 and color.green()<40 and color.blue()<40


def test_legacy_mcp_handshake(app,mcp_runtime):
    """Clients using the 2025 stateful handshake can list and call the same tools."""
    endpoint,command,args = mcp_runtime
    child = subprocess.Popen([command,*args,'--connect',endpoint],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
    outcome = {}
    def send(value):
        child.stdin.write(json.dumps(value)+'\n'); child.stdin.flush()
    def receive():
        value = child.stdout.readline()
        assert value,'MCP server closed stdout'
        return json.loads(value)
    def run():
        try:
            send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25',
                  'capabilities':{},'clientInfo':{'name':'legacy-smoke','version':'1'}}})
            from core.version import VERSION
            initialized = receive()['result']
            assert initialized['protocolVersion']=='2025-11-25'
            assert initialized['serverInfo']['version']==VERSION
            send({'jsonrpc':'2.0','method':'notifications/initialized'})
            send({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
            assert len(receive()['result']['tools'])==24
            send({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'studio_get_state','arguments':{}}})
            result = receive()['result']
            assert not result.get('isError',False),result
            assert 'root' in json.loads(result['content'][0]['text'])
        except BaseException as error: outcome['error']=error
    thread = threading.Thread(target=run,daemon=True); thread.start()
    try:
        deadline = time.monotonic()+20
        while thread.is_alive() and time.monotonic()<deadline:
            app.processEvents(); time.sleep(.01)
        assert not thread.is_alive(),'Legacy MCP timed out'
        if 'error' in outcome: raise outcome['error']
    finally:
        child.kill(); child.wait(timeout=10)
