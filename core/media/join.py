"""Normalize and concatenate local videos using a cancellable FFmpeg worker."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from core.media.tools import binary, probe, FLAGS


def run_ffmpeg(arguments, seconds, progress, cancelled):
    if cancelled():
        raise InterruptedError('Anulowano / Cancelled')
    command = [binary('ffmpeg'), '-hide_banner', '-v', 'error', '-nostdin', '-y',
               '-progress', 'pipe:1', '-stats_period', '0.2'] + arguments
    stopped = threading.Event()
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding='utf-8', creationflags=FLAGS)
        def watch_cancel():
            while not stopped.wait(.1):
                if cancelled():
                    if process.poll() is None:
                        process.kill()
                    return
        watcher = threading.Thread(target=watch_cancel,daemon=True)
        watcher.start()
        try:
            for line in process.stdout:
                key, _, value = line.strip().partition('=')
                if key == 'out_time_us':
                    try:
                        progress(min(1,max(0,int(value)/1_000_000/max(.001,seconds))))
                    except ValueError:
                        pass
            code = process.wait(timeout=30)
            if cancelled():
                raise InterruptedError('Anulowano / Cancelled')
            if code:
                errors.seek(0)
                detail = errors.read()[-1600:].decode('utf-8',errors='replace')
                raise ValueError('FFmpeg: '+detail)
        finally:
            stopped.set()
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            watcher.join(timeout=2)


def join_videos(paths, target, options, progress=lambda value: None, cancelled=lambda: False):
    if not 2 <= len(paths) <= 40:
        raise ValueError('Wybierz od 2 do 40 filmów.')
    sources = [Path(path).resolve() for path in paths]
    target = Path(target).resolve()
    if target in sources or target.suffix.lower() != '.mp4':
        raise ValueError('Wybierz nowy plik MP4, inny niż filmy źródłowe.')
    infos = []
    for source in sources:
        if cancelled():
            raise InterruptedError('Anulowano / Cancelled')
        infos.append(probe(source))
    width = int(options.get('width',infos[0]['width']))//2*2
    height = int(options.get('height',infos[0]['height']))//2*2
    fps = float(options.get('fps',infos[0]['fps']))
    if not (2 <= width <= 7680 and 2 <= height <= 7680 and 1 <= fps <= 120):
        raise ValueError('Nieprawidłowy rozmiar lub FPS łączenia.')
    durations = [info['duration']/1000 for info in infos]
    if any(seconds <= 0 for seconds in durations):
        raise ValueError('Nieznany czas trwania jednego z filmów.')
    total = sum(durations)
    completed = 0
    with tempfile.TemporaryDirectory(prefix='.subtitle-join-',dir=target.parent) as folder:
        folder = Path(folder)
        files = []
        for i, (source,info,seconds) in enumerate(zip(sources,infos,durations)):
            clip = folder/f'clip-{i:04}.mkv'
            arguments = ['-i',str(source)]
            audio = any(s['codec_type'] == 'audio' for s in info['streams'])
            if not audio:
                arguments += ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
            vf = f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}'
            arguments += ['-map','0:v:0','-map','0:a:0' if audio else '1:a:0',
                          '-vf',vf,'-af','aresample=48000,apad','-ac','2','-t',str(seconds),
                          '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
                          '-c:a','aac','-b:a','192k','-map_metadata','-1',str(clip)]
            def clip_progress(fraction):
                progress(dict(percent=round(90*(completed+seconds*fraction)/total),clip=i+1,total=len(sources)))
            run_ffmpeg(arguments,seconds,clip_progress,cancelled)
            completed += seconds
            files.append(clip)
        listing = folder/'clips.txt'
        listing.write_text('\n'.join("file '"+clip.name+"'" for clip in files),encoding='utf-8')
        output = folder/'result.mp4'
        run_ffmpeg(['-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-map','0:a:0',
                    '-c','copy','-movflags','+faststart',str(output)], total,
                   lambda value: progress(dict(percent=90+round(value*9))),cancelled)
        result = probe(output)
        tolerance = len(sources)*(1/fps+.05)+.3
        if ((result['width'],result['height']) != (width,height)
                or abs(result['duration']/1000-total) > tolerance
                or sum(s['codec_type'] == 'audio' for s in result['streams']) != 1):
            raise ValueError('Weryfikacja połączonego filmu nie powiodła się.')
        if cancelled():
            raise InterruptedError('Anulowano / Cancelled')
        os.replace(output,target)
        progress(dict(percent=100))


def main(args):
    config, cancel, status = map(Path,args)
    def report(value):
        status.write_text(json.dumps(value),encoding='utf-8')
    try:
        job = json.loads(config.read_text(encoding='utf-8'))
        join_videos(job['paths'],job['target'],job['options'],report,cancel.exists)
        report(dict(percent=100,done=True))
    except Exception as error:
        report(dict(error=str(error)))
        raise SystemExit(1)
