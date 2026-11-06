"""Create an MP4 from one visual source and an independent audio track."""
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QImageReader
from core.media.tools import binary, probe, probe_audio, FLAGS
from core.media.join import run_ffmpeg

IMAGE_EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.bmp'}


def load_photo(path, max_edge=None):
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width()*size.height() > 80_000_000:
        raise ValueError('Nieprawidłowe zdjęcie lub rozmiar powyżej 80 megapikseli.')
    if bytes(reader.format()).lower() not in (b'png',b'jpg',b'jpeg',b'webp',b'bmp'):
        raise ValueError('Wybierz zdjęcie PNG, JPG, WebP lub BMP.')
    if max_edge and max(size.width(),size.height()) > max_edge:
        reader.setScaledSize(size.scaled(max_edge,max_edge,Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ValueError('Nie można odczytać zdjęcia.')
    return image


def thumbnail(path):
    if Path(path).suffix.lower() in IMAGE_EXTENSIONS:
        return load_photo(path,640)
    result = subprocess.run([binary('ffmpeg'),'-v','error','-nostdin','-i',str(path),
                             '-frames:v','1','-vf','scale=640:640:force_original_aspect_ratio=decrease',
                             '-f','image2pipe','-c:v','png','pipe:1'],capture_output=True,timeout=30,creationflags=FLAGS)
    image = QImage.fromData(result.stdout)
    if result.returncode or image.isNull():
        raise ValueError('Nie można utworzyć podglądu filmu.')
    return image


def create_video(visual, audio, target, options, progress=lambda value: None, cancelled=lambda: False):
    visual, audio, target = (Path(path).resolve() for path in (visual,audio,target))
    if target in (visual,audio) or target.suffix.lower() != '.mp4':
        raise ValueError('Wybierz nowy plik MP4, inny niż źródła obrazu i dźwięku.')
    kind = options.get('kind','image' if visual.suffix.lower() in IMAGE_EXTENSIONS else 'video')
    mode = options.get('fit','fit')
    length = options.get('length','loop')
    if kind not in ('image','video') or mode not in ('fit','crop') or length not in ('loop','freeze','shortest'):
        raise ValueError('Nieprawidłowy tryb tworzenia filmu.')
    width, height = int(options.get('width',1920)), int(options.get('height',1080))
    fps = float(options.get('fps',30))
    crf = int(options.get('crf',20))
    if not (2 <= width <= 7680 and 2 <= height <= 7680 and width % 2 == 0 and height % 2 == 0
            and 1 <= fps <= 120 and 0 <= crf <= 51):
        raise ValueError('Ustaw parzyste wymiary do 7680 px, FPS 1–120 i CRF 0–51.')
    if cancelled():
        raise InterruptedError('Anulowano / Cancelled')
    sound = probe_audio(audio)
    seconds = sound['duration']/1000
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Nie można odczytać długości wybranego dźwięku.')
    video_index = 0
    if kind == 'video':
        video = probe(visual)
        video_index = next(s['index'] for s in video['streams']
                           if s['codec_type'] == 'video' and not s.get('disposition',{}).get('attached_pic'))
        if length == 'shortest':
            seconds = min(seconds,video['duration']/1000)
    if seconds <= 0:
        raise ValueError('Film źródłowy ma nieprawidłowy czas trwania.')

    with tempfile.TemporaryDirectory(prefix='.subtitle-create-',dir=target.parent) as directory:
        folder = Path(directory)
        if kind == 'image':
            photo = load_photo(visual)
            normalized = folder/'photo.png'
            if not photo.save(str(normalized)):
                raise ValueError('Nie można przygotować zdjęcia do renderowania.')
            arguments = ['-loop','1','-framerate',str(fps),'-i',str(normalized)]
        else:
            arguments = ['-stream_loop','-1'] if length == 'loop' else []
            arguments += ['-i',str(visual)]
        arguments += ['-i',str(audio)]
        filters = ['setpts=PTS-STARTPTS']
        if kind == 'video' and length == 'freeze':
            filters.append(f'tpad=stop_mode=clone:stop_duration={seconds}')
        aspect = 'decrease' if mode == 'fit' else 'increase'
        filters.append(f'scale={width}:{height}:force_original_aspect_ratio={aspect}:force_divisible_by=2')
        if mode == 'fit':
            filters.append(f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black')
        else:
            filters.append(f'crop={width}:{height}:(iw-ow)/2:(ih-oh)/2')
        filters += ['setsar=1',f'fps={fps}']
        output = folder/'result.mp4'
        arguments += ['-map',f'0:{video_index}','-map',f'1:{sound["index"]}',
                      '-vf',','.join(filters),'-af','asetpts=PTS-STARTPTS,aresample=48000',
                      '-t',str(seconds),'-c:v','libx264','-preset','fast','-crf',str(crf),
                      '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ac','2','-ar','48000',
                      '-map_metadata','-1','-movflags','+faststart',str(output)]
        run_ffmpeg(arguments,seconds,lambda value: progress(dict(percent=min(99,round(value*99)))),cancelled)
        result = probe(output)
        if ((result['width'],result['height']) != (width,height)
                or abs(result['duration']/1000-seconds) > max(.25,2/fps+.1)
                or sum(s['codec_type'] == 'audio' for s in result['streams']) != 1):
            raise ValueError('Weryfikacja wygenerowanego filmu nie powiodła się.')
        if cancelled():
            raise InterruptedError('Anulowano / Cancelled')
        os.replace(output,target)
        progress(dict(percent=100))


def main(args):
    app = QGuiApplication.instance() or QGuiApplication([])
    config, cancel, status = map(Path,args)
    def report(value):
        status.write_text(json.dumps(value),encoding='utf-8')
    try:
        job = json.loads(config.read_text(encoding='utf-8'))
        create_video(job['visual'],job['audio'],job['target'],job['options'],report,cancel.exists)
        report(dict(percent=100,done=True))
    except Exception as error:
        report(dict(error=str(error)))
        raise SystemExit(1)
