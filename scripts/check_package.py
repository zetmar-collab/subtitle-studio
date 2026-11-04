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
                  overlay_mean_pixel_error=round(difference,4),
                  note='Current Windows installation; child PATH excludes development Python; not a clean VM.')
    (root/'docs/package-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
