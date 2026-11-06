"""Generate the integrated PyInstaller specification from installed dependencies."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = r'''
from pathlib import Path
import importlib.util
from PyInstaller.utils.hooks import collect_all, copy_metadata
root = Path(SPECPATH)
datas = [(str(root/'assets'), 'assets'),
         (str(root/'srtstudio/dictionary_catalog.json'), 'srtstudio')]
binaries, hidden = [], []
for package in ('faster_whisper','ctranslate2','onnxruntime','tokenizers','av','spylls'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hidden += h
for package in ('faster-whisper','huggingface-hub','spylls','pyenchant'):
    datas += copy_metadata(package)
enchant = Path(next(iter(importlib.util.find_spec('enchant').submodule_search_locations)))
for name in ('libhunspell-1.7-0.dll','libgcc_s_seh-1.dll','libstdc++-6.dll','libwinpthread-1.dll'):
    binaries.append((str(enchant/'data/mingw64/bin'/name), 'native/hunspell'))
a = Analysis([str(root/'main.py')], pathex=[str(root)], binaries=binaries, datas=datas,
             hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtQml',
                       'PySide6.QtQuick','tkinter','pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='SubtitleStudio',debug=False,
          bootloader_ignore_signals=False,strip=False,upx=False,console=False,
          icon=str(root/'assets/icon.ico'))
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='SubtitleStudio')
'''
(root/'SubtitleStudio.spec').write_text(spec, encoding='utf-8')
