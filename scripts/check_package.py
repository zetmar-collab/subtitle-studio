from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.media.tools import binary,probe
from core.projects.model import load

root = Path(__file__).resolve().parents[1]
package = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root/'dist/SubtitleStudio'
exe = package/'SubtitleStudio.exe'
demo = package/'examples/Demo.subtitlelogo.json'
env = os.environ.copy()
env['QT_QPA_PLATFORM'] = 'offscreen'
# Exclude the development Python directories from the child's PATH.
env['PATH'] = os.pathsep.join([str(Path(binary('ffmpeg')).parent),str(Path(os.environ['WINDIR'])/'System32'),os.environ['WINDIR']])
shot = root/'docs/packaged.png'
subprocess.run([str(exe),'--smoke-test',str(demo),str(shot)],env=env,check=True,timeout=30)
gui = json.loads(Path(str(shot)+'.json').read_text())
assert gui['frame'] and gui['wave_samples'] > 0 and gui['media_error'] == ''
assert gui['icon'] and gui['visual_colors']
assert (package/'docs/POMOC.md').is_file(), 'The offline user guide is missing.'
with tempfile.TemporaryDirectory(prefix='subtitle-integration-') as integration_folder:
    report_path = Path(integration_folder)/'report.json'
    subprocess.run([str(exe),'--integration-smoke',str(report_path),str(load(demo).video),'--queue-test'],
                   env=env,check=True,timeout=60)
    integration = json.loads(report_path.read_text(encoding='utf-8'))
    assert integration['ok'] and integration['frozen']
    assert integration['audio_probe'] and integration['native_spelling_worker']
    assert integration['word_timing_transfer'] and integration['reverse_transfer']
    assert integration['queue_worker']
import pefile
import struct
pe = pefile.PE(str(exe))
resources = next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id == 3)
embedded_icons = [pe.get_data(lang.data.struct.OffsetToData,lang.data.struct.Size)
                  for item in resources.directory.entries for lang in item.directory.entries]
ico = (root/'assets/icon.ico').read_bytes()
count = struct.unpack_from('<H',ico,4)[0]
largest = next(struct.unpack_from('<BBBBHHII',ico,6+i*16) for i in range(count)
               if ico[6+i*16] == 0 and ico[7+i*16] == 0)
icon_size, icon_offset = largest[-2:]
assert ico[icon_offset:icon_offset+icon_size] in embedded_icons, 'The EXE does not contain the custom 256px icon.'
pe.close()
with tempfile.TemporaryDirectory(prefix='subtitle-package-') as folder:
    folder = Path(folder)
    options = folder/'options.json'; options.write_text(json.dumps(dict(width=640,height=360,fps=12,seconds=2)))
    output = root/'examples/Przykładowy eksport.mp4'
    status = folder/'status.json'; cancel = folder/'cancel'
    subprocess.run([str(exe),'--render',str(demo),str(output),str(options),str(cancel),str(status)],env=env,check=True,timeout=60)
    assert json.loads(status.read_text())['done']
    info = probe(output)
    assert info['width'] == 640 and info['height'] == 360
    assert sum(s['codec_type'] == 'audio' for s in info['streams']) == 1
    join_config = folder/'join.json'
    join_output = folder/'joined.mp4'
    join_config.write_text(json.dumps(dict(paths=[load(demo).video]*2,target=str(join_output),
                                          options=dict(width=320,height=180,fps=12))),encoding='utf-8')
    subprocess.run([str(exe),'--join',str(join_config),str(cancel),str(status)],env=env,check=True,timeout=90)
    assert json.loads(status.read_text())['done']
    joined = probe(join_output)
    assert joined['width'] == 320 and joined['height'] == 180
    assert sum(s['codec_type'] == 'audio' for s in joined['streams']) == 1
    assert abs(joined['duration']-2*probe(load(demo).video)['duration']) < 500
    sound = folder/'sound.wav'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','sine=frequency=880',
                    '-t','1',str(sound)],check=True,env=env,timeout=20)
    create_config = folder/'create.json'
    created_output = folder/'created.mp4'
    create_config.write_text(json.dumps(dict(visual=str(package/'examples/Logo przezroczyste.png'),
                                             audio=str(sound),target=str(created_output),
                                             options=dict(width=90,height=160,fps=12))),encoding='utf-8')
    subprocess.run([str(exe),'--create-video',str(create_config),str(cancel),str(status)],env=env,check=True,timeout=60)
    assert json.loads(status.read_text())['done']
    created = probe(created_output)
    assert (created['width'],created['height']) == (90,160)
    assert abs(created['duration']-1000) < 150
    assert sum(s['codec_type'] == 'audio' for s in created['streams']) == 1
    show_config=folder/'slideshow.json';show_output=folder/'slideshow.mp4'
    show_config.write_text(json.dumps(dict(clips=[dict(path=str(package/'examples/Logo przezroczyste.png'),seconds=1)],
        audio=str(sound),target=str(show_output),options=dict(width=90,height=160,fps=12,auto_duration=True,fade=True,motion=True))),encoding='utf-8')
    subprocess.run([str(exe),'--slideshow',str(show_config),str(cancel),str(status)],env=env,check=True,timeout=60)
    assert json.loads(status.read_text())['done'] and abs(probe(show_output)['duration']-1000)<150
    # A synthetic local server verifies the packaged Ollama worker without depending on installed models.
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import threading
    class OllamaHandler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,data):
            body=json.dumps(data).encode('utf-8');self.send_response(200)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):self.send(dict(models=[dict(name='local:test',size=1234)]))
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path=='/api/show':self.send(dict(capabilities=['completion'],model_info={'general.architecture':'test'}))
            else:self.send(dict(response=json.dumps(dict(corrections=[dict(id=0,text='który',reason='Pisownia')]))))
    server=ThreadingHTTPServer(('127.0.0.1',0),OllamaHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        ollama_config=folder/'ollama.json'
        ollama_config.write_text(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}',model='local:test',
            captions=[dict(id=0,text='ktury')],timeout=30)),encoding='utf-8')
        subprocess.run([str(exe),'--ollama-correct',str(ollama_config),str(cancel),str(status)],env=env,check=True,timeout=30)
        assert json.loads(status.read_text(encoding='utf-8'))['corrections'][0]['text']=='który'
    finally:server.shutdown();server.server_close();thread.join()
    # Verify the actual packaged renderer, not just the presence of a video stream.
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtGui import QGuiApplication,QImage
    from core.fonts import initialize_fonts
    from core.compositor.render import compose
    app = QGuiApplication.instance() or QGuiApplication([])
    initialize_fonts()
    project = load(demo)
    def sample(path):
        command = [binary('ffmpeg'),'-v','error','-i',str(path),'-vf','scale=640:360,fps=12',
                   '-ss','0.75','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
        data = subprocess.run(command,capture_output=True,check=True,timeout=20).stdout
        return QImage(data,640,360,640*3,QImage.Format.Format_RGB888).copy()
    source = sample(project.video)
    expected_image = compose(source,project,750)
    actual_image = sample(output)
    expected = bytes(expected_image.constBits())
    actual = bytes(actual_image.constBits())
    difference = sum(abs(a-b) for a,b in zip(expected,actual))/len(actual)
    assert len(actual) == 640*360*3 and difference < 5, difference
    assert bytes(source.constBits()) != actual
    report = dict(gui=gui,export=dict(width=info['width'],height=info['height'],duration_ms=info['duration'],audio_tracks=1),
                  embedded_program_icon=True,
                  join_worker=True,
                  create_video_worker=True,
                  slideshow_worker=True,
                  ollama_worker=True,
                  integrated_transcription=integration,
                  overlay_mean_pixel_error=round(difference,4),
                  note='Current Windows installation; child PATH excludes development Python; not a clean VM.')
    (root/'docs/package-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
