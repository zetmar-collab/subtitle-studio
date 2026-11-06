import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading
from PySide6.QtGui import QImage, QGuiApplication
from core.projects.model import load
from core.media.tools import probe, binary, FLAGS
from core.compositor.render import compose


def render(project, target, options, progress=lambda p: None, cancelled=lambda: False):
    info = probe(project.video)
    start = float(options.get('start',0))
    requested = float(options.get('seconds',info['duration']/1000))
    if not math.isfinite(start) or not math.isfinite(requested) or start < 0 or start >= info['duration']/1000:
        raise ValueError('Nieprawidłowy zakres eksportu.')
    duration = min(info['duration']/1000-start, requested)
    if duration <= 0:
        raise ValueError('Nieznany czas trwania filmu.')
    w, h = options.get('width', info['width']), options.get('height', info['height'])
    w, h = int(w)//2*2, int(h)//2*2
    fps = float(options.get('fps', info['fps']))
    if not (2 <= w <= 7680 and 2 <= h <= 7680 and 1 <= fps <= 120):
        raise ValueError('Nieprawidłowa rozdzielczość lub FPS.')
    if any(not s.timed or s.start < 0 or s.end <= s.start for t in project.tracks if t.visible for s in t.segments):
        raise ValueError('Nadaj poprawne czasy wszystkim widocznym napisom.')
    target = Path(target).resolve()
    if target == Path(project.video).resolve():
        raise ValueError('Nie można nadpisać filmu źródłowego.')
    if any(target == Path(l.path).resolve() for l in project.logos):
        raise ValueError('Nie można nadpisać grafiki źródłowej.')
    if any(t.source and target == Path(t.source).resolve() for t in project.tracks):
        raise ValueError('Nie można nadpisać napisów źródłowych.')
    codec = options.get('codec', 'libx264')
    if codec not in ('libx264', 'libx265', 'libvpx-vp9'):
        raise ValueError('Nieobsługiwany koder.')
    mode=options.get('fit','fit')
    if mode not in ('fit','crop'):
        raise ValueError('Nieprawidłowy tryb kadrowania / Invalid framing mode')
    fd, tempname = tempfile.mkstemp(prefix='.subtitle-', suffix=target.suffix, dir=target.parent)
    os.close(fd)
    temp = Path(tempname)
    decoder = encoder = None
    stopped=threading.Event();timed_out=threading.Event()
    activity=[time.monotonic()]
    idle=float(options.get('idle_timeout',120))
    if not math.isfinite(idle) or not 1<=idle<=600:
        temp.unlink(missing_ok=True)
        raise ValueError('Nieprawidłowy limit czasu / Invalid idle timeout')
    def watch():
        while not stopped.wait(.1):
            expired=time.monotonic()-activity[0]>idle
            if cancelled() or expired:
                if expired:timed_out.set()
                for process in (decoder,encoder):
                    if process and process.poll() is None:
                        try:process.kill()
                        except OSError:pass
                return
    watcher=threading.Thread(target=watch,daemon=True);watcher.start()
    started = time.monotonic()
    try:
        with tempfile.TemporaryFile() as decode_log, tempfile.TemporaryFile() as encode_log:
            vf = (f'scale={w}:{h}:force_original_aspect_ratio={"decrease" if mode=="fit" else "increase"}:force_divisible_by=2,'
                  + (f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2' if mode=='fit' else f'crop={w}:{h}:(iw-ow)/2:(ih-oh)/2')
                  + f',setsar=1,fps={fps}')
            decoder = subprocess.Popen([binary('ffmpeg'), '-v', 'error', '-nostdin', '-ss', str(start), '-i', project.video,
                                        '-t', str(duration), '-vf', vf, '-an', '-sn', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
                                       stdout=subprocess.PIPE, stderr=decode_log, creationflags=FLAGS)
            cmd = [binary('ffmpeg'), '-v', 'error', '-nostdin', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                   '-s', f'{w}x{h}', '-r', str(fps), '-i', 'pipe:0', '-ss', str(start), '-i', project.video,
                   '-map', '0:v:0', '-map', '1:a?', '-c:v', codec, '-crf', str(options.get('crf', 20)),
                   '-pix_fmt', 'yuv420p', '-c:a', 'libopus' if codec == 'libvpx-vp9' else 'aac', '-b:a', '192k',
                   '-t', str(duration), '-map_metadata', '-1']
            if codec in ('libx264', 'libx265'):
                cmd += ['-preset', 'fast']
            if target.suffix.lower() == '.mp4':
                cmd += ['-movflags', '+faststart']
            cmd += [str(temp)]
            encoder = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=encode_log, creationflags=FLAGS)
            count = 0
            size = w*h*3
            while True:
                if cancelled():
                    raise InterruptedError('Anulowano / Cancelled')
                data = decoder.stdout.read(size)
                if cancelled():raise InterruptedError('Anulowano / Cancelled')
                if timed_out.is_set():raise TimeoutError('FFmpeg nie odpowiada / FFmpeg idle timeout')
                if not data:
                    break
                if len(data) != size:
                    raise ValueError('Niepełna klatka wideo.')
                frame = QImage(data, w, h, w*3, QImage.Format.Format_RGB888).copy()
                frame = compose(frame, project, start*1000+count/fps*1000)
                # QImage may pad rows to 4 bytes; remove padding before rawvideo encoding.
                raw = bytes(frame.constBits())
                if frame.bytesPerLine() != w*3:
                    stride = frame.bytesPerLine()
                    raw = b''.join(raw[y*stride:y*stride+w*3] for y in range(h))
                encoder.stdin.write(raw)
                activity[0]=time.monotonic()
                count += 1
                if count % max(1, round(fps/4)) == 0:
                    fraction = min(.99, count/max(1, math.ceil(duration*fps)))
                    progress(dict(percent=round(fraction*100), eta=round((time.monotonic()-started)*(1-fraction)/max(.001, fraction))))
            encoder.stdin.close()
            decoder.stdout.close()
            if decoder.wait(timeout=30) or encoder.wait(timeout=120):
                raise ValueError('FFmpeg: błąd dekodowania lub kodowania. Sprawdź dostępność kodera i miejsce na dysku.')
            result = probe(temp)
            audio_in = sum(s['codec_type'] == 'audio' for s in info['streams'])
            audio_out = sum(s['codec_type'] == 'audio' for s in result['streams'])
            if (result['width'], result['height']) != (w, h) or audio_in != audio_out or abs(result['duration']/1000-duration) > max(.5, 2/fps):
                raise ValueError('Weryfikacja eksportu: niezgodna rozdzielczość, czas lub liczba ścieżek audio.')
            if cancelled():
                raise InterruptedError('Anulowano / Cancelled')
            os.replace(temp, target)
            progress(dict(percent=100, eta=0))
    finally:
        stopped.set()
        for process in (decoder, encoder):
            if process and process.poll() is None:
                process.kill()
                process.wait()
        temp.unlink(missing_ok=True)
        watcher.join(timeout=2)


def main(args):
    app = QGuiApplication.instance() or QGuiApplication([])
    from core.fonts import initialize_fonts
    initialize_fonts()
    project_path, target, config, cancel_path, status_path = args
    status = Path(status_path)
    def report(d):
        status.write_text(json.dumps(d), encoding='utf-8')
    try:
        render(load(project_path), target, json.loads(Path(config).read_text()), report, lambda: Path(cancel_path).exists())
        report({'percent': 100, 'done': True})
    except Exception as e:
        report({'error': str(e)})
        sys.exit(1)
