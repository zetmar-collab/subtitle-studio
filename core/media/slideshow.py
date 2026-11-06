"""Normalize a visual playlist, then combine it with independent audio."""
import json
import math
from pathlib import Path
import tempfile
from PySide6.QtGui import QGuiApplication
from core.media.tools import probe,probe_audio
from core.media.create_video import IMAGE_EXTENSIONS,load_photo,create_video
from core.media.join import run_ffmpeg


def slideshow(clips,audio,target,options,progress=lambda value:None,cancelled=lambda:False):
    if not 1<=len(clips)<=40:raise ValueError('Wybierz 1–40 materiałów / Choose 1–40 visuals')
    sources=[Path(clip['path']).resolve() for clip in clips]
    audio=Path(audio).resolve();target=Path(target).resolve()
    if target in sources+[audio] or target.suffix.lower()!='.mp4':raise ValueError('Wybierz nowy plik MP4 / Choose a new MP4')
    width=int(options.get('width',1920));height=int(options.get('height',1080));fps=float(options.get('fps',30))
    if not 2<=width<=7680 or not 2<=height<=7680 or width%2 or height%2 or not 1<=fps<=120:
        raise ValueError('Nieprawidłowe wymiary lub FPS / Invalid dimensions or FPS')
    fit=options.get('fit','fit')
    if fit not in ('fit','crop'):raise ValueError('Nieprawidłowe kadrowanie / Invalid framing')
    sound=probe_audio(audio)['duration']/1000
    if not math.isfinite(sound) or sound<=0:raise ValueError('Nieprawidłowy dźwięk / Invalid audio')
    durations=[float(clip.get('seconds',3)) for clip in clips]
    if options.get('auto_duration') and all(path.suffix.lower() in IMAGE_EXTENSIONS for path in sources):
        durations=[sound/len(clips)]*len(clips)
    if any(not math.isfinite(value) or not .1<=value<=86400 for value in durations):
        raise ValueError('Czas materiału musi wynosić 0,1–86400 s / Visual duration must be 0.1–86400 seconds')
    total=sum(durations);done=0
    with tempfile.TemporaryDirectory(prefix='.subtitle-show-',dir=target.parent) as directory:
        folder=Path(directory);prepared=[]
        for index,(path,seconds) in enumerate(zip(sources,durations)):
            if cancelled():raise InterruptedError('Anulowano / Cancelled')
            photo=path.suffix.lower() in IMAGE_EXTENSIONS
            if photo:
                normalized=folder/f'photo-{index}.png'
                if not load_photo(path).save(str(normalized)):raise ValueError('Nie można odczytać zdjęcia / Cannot read photo')
                args=['-loop','1','-framerate',str(fps),'-i',str(normalized)];stream='0:v:0'
            else:
                metadata=probe(path)
                stream='0:'+str(next(s['index'] for s in metadata['streams']
                                     if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')))
                args=['-stream_loop','-1','-i',str(path)]
            filters=[f'scale={width}:{height}:force_original_aspect_ratio={"decrease" if fit=="fit" else "increase"}:force_divisible_by=2',
                     f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2' if fit=='fit' else f'crop={width}:{height}:(iw-ow)/2:(ih-oh)/2',
                     'setsar=1',f'fps={fps}']
            if photo and options.get('motion'):
                increment=.08/max(1,seconds*fps)
                filters.append(f"zoompan=z='min(1.08,1+on*{increment})':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps}")
            if options.get('fade'):
                fade=min(.5,seconds/3)
                filters.extend([f'fade=t=in:st=0:d={fade}',f'fade=t=out:st={seconds-fade}:d={fade}'])
            clip=folder/f'clip-{index:03}.mkv'
            args+=['-map',stream,'-an','-vf',','.join(filters),'-t',str(seconds),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(clip)]
            run_ffmpeg(args,seconds,lambda fraction:progress(dict(percent=round(75*(done+seconds*fraction)/total))),cancelled)
            done+=seconds;prepared.append(clip)
            if photo:normalized.unlink(missing_ok=True)
        listing=folder/'clips.txt';listing.write_text('\n'.join("file '"+path.name+"'" for path in prepared),encoding='utf-8')
        montage=folder/'montage.mp4'
        run_ffmpeg(['-f','concat','-safe','0','-i',str(listing),'-c','copy','-an',str(montage)],total,
                   lambda fraction:progress(dict(percent=75+round(5*fraction))),cancelled)
        final_options=dict(options,kind='video',length=options.get('length','loop'))
        create_video(montage,audio,target,final_options,
                     lambda value:progress(dict(percent=80+round(value.get('percent',0)*.2))),cancelled)


def main(args):
    app=QGuiApplication.instance() or QGuiApplication([])
    config,cancel,status=map(Path,args)
    def report(value):status.write_text(json.dumps(value),encoding='utf-8')
    try:
        job=json.loads(config.read_text(encoding='utf-8'))
        slideshow(job['clips'],job['audio'],job['target'],job['options'],report,cancel.exists)
        report(dict(percent=100,done=True))
    except Exception as error:
        report(dict(error=str(error)));raise SystemExit(1)
