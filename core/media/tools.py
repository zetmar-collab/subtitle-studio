from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def binary(name):
    folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
    filename = name + ('.exe' if os.name == 'nt' else '')
    candidates = [folder/filename]
    if getattr(sys, 'frozen', False):
        candidates.append(Path(getattr(sys, '_MEIPASS', folder/'_internal'))/'bin'/filename)
    found = next((str(path) for path in candidates if path.is_file()), None) or shutil.which(name)
    if not found:
        raise ValueError(f'Brak {name}. Dodaj ffmpeg.exe i ffprobe.exe obok aplikacji lub do PATH.')
    return found


def read_metadata(path):
    r = subprocess.run([binary('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
                       capture_output=True, timeout=30, creationflags=FLAGS)
    if r.returncode:
        raise ValueError('Nie można odczytać multimediów. Plik jest uszkodzony lub format nie jest obsługiwany.')
    return json.loads(r.stdout)


def probe(path):
    d = read_metadata(path)
    streams = d.get('streams', [])
    v = next((s for s in streams if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')), None)
    if not v:
        raise ValueError('Plik nie zawiera obsługiwanej ścieżki wideo.')
    num, den = map(int, v.get('avg_frame_rate', '25/1').split('/'))
    rotation = next((s.get('rotation', 0) for s in v.get('side_data_list', []) if 'rotation' in s), 0)
    w, h = v['width'], v['height']
    if abs(rotation) % 180 == 90:
        w, h = h, w
    sar = v.get('sample_aspect_ratio', '1:1').split(':')
    if len(sar) == 2 and all(x.isdigit() for x in sar) and int(sar[1]) > 0:
        w = round(w * int(sar[0]) / int(sar[1]))
    return dict(width=w, height=h, fps=num/den if den and num else 25,
                duration=round(float(d.get('format', {}).get('duration', v.get('duration', 0)))*1000),
                codec=v['codec_name'], streams=streams)


def probe_audio(path):
    d = read_metadata(path)
    stream = next((s for s in d.get('streams',[]) if s['codec_type'] == 'audio'), None)
    if stream is None:
        raise ValueError('Wybrany plik nie zawiera ścieżki audio.')
    duration = stream.get('duration')
    if duration in (None,'N/A'):
        duration = d.get('format',{}).get('duration',0)
    return dict(duration=round(float(duration)*1000),index=stream['index'])
