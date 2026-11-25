"""Media work in a child process; never called inside the GUI event loop."""
import json
import os
from pathlib import Path
import tempfile
import time


def write_status(path, value, required=True, attempts=20):
    """Atomically replace the status file.

    On Windows os.replace fails while the GUI briefly has the old file open for
    reading. Progress updates are best-effort; final states are retried longer
    and then written in place so the GUI always learns the outcome."""
    temp = path.with_suffix('.tmp')
    text = json.dumps(value, ensure_ascii=False)
    for attempt in range(attempts if required else 3):
        try:
            temp.write_text(text, encoding='utf-8')
            os.replace(temp, path)
            return True
        except PermissionError:
            time.sleep(0.02 * (attempt + 1))
    if required:
        path.write_text(text, encoding='utf-8')
        return True
    return False


def main(args):
    kind, config, cancel, status = args
    data = json.loads(Path(config).read_text(encoding='utf-8'))
    def report(value):
        write_status(Path(status), value, required='percent' not in value or len(value) > 1)
    try:
        if kind == 'color':
            from core.media.join import run_ffmpeg
            from core.media.tools import probe
            target = Path(data['target'])
            opts = data['options']
            with tempfile.TemporaryDirectory(prefix='.subtitle-color-', dir=target.parent) as folder:
                output = Path(folder)/'video.mp4'
                run_ffmpeg(['-f','lavfi','-i',f"color=c=0x{data['color'][1:]}:s={opts['width']}x{opts['height']}:r={opts['fps']}",
                    '-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-map','0:v:0','-map','1:a:0',
                    '-t',str(data['seconds']),'-c:v','libx264','-preset','fast','-crf','20',
                    '-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(output)],
                    data['seconds'],lambda p: report({'percent':round(p*99)}),lambda:Path(cancel).exists())
                info = probe(output)
                if info['width'] != opts['width'] or info['height'] != opts['height']:
                    raise ValueError('Generated dimensions differ from requested dimensions')
                if Path(cancel).exists():
                    raise InterruptedError('Cancelled')
                os.replace(output, target)
        elif kind == 'transcribe':
            from srtstudio.engine import transcribe
            segments = []
            class Events:
                def put(self, event):
                    if Path(cancel).exists():
                        raise InterruptedError('Cancelled')
                    if event[0] == 'segment':
                        segments.append(dict(event[1],spell_language=data.get('language') or ''))
                    elif event[0] == 'language':
                        data['language'] = event[1]
                    elif event[0] == 'progress':
                        report({'percent':round(event[1]*99)})
            data['work'] = str(Path(config).parent)
            transcribe(data, Events())
            Path(data['target']).write_text(json.dumps(segments, ensure_ascii=False),encoding='utf-8')
        else:
            raise ValueError('Unsupported automation worker')
        report({'done':True,'percent':100})
    except Exception as error:
        report({'error':str(error)})
        raise SystemExit(1)
