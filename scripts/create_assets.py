from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
folder = root/'assets/presets'
folder.mkdir(parents=True, exist_ok=True)
presets = [
    ('Klasyczne / Classic', {}),
    ('Filmowe / Cinema', dict(bold=False, size=42, stroke=1, y=91)),
    ('Ciemne tło / Dark box', dict(background='#b8000000', stroke=0)),
    ('Social media', dict(size=76, y=50, width=78)),
    ('Aktywne słowo / Active word', dict(effect='highlight', active_color='#ffdc55', size=64)),
    ('Maszyna / Typewriter', dict(effect='typewriter', font='Consolas')),
    ('Wjazd z lewej / Slide left', dict(effect='left', animation_ms=500)),
    ('Wjazd z prawej / Slide right', dict(effect='right', animation_ms=500)),
]
(folder/'defaults.json').write_text(json.dumps([dict(name=n, style=s) for n,s in presets],ensure_ascii=False,indent=2),encoding='utf-8')
# The catalog is also readable by translators without opening Python source.
import ast
tree = ast.parse((root/'ui/window.py').read_text(encoding='utf-8'))
catalog = {}
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        index = 1 if node.func.attr == 'text' else 0
        if node.func.attr in ('tr_text','text','button','action') and len(node.args) > index+1:
            a,b = node.args[index:index+2]
            if isinstance(a,ast.Constant) and isinstance(b,ast.Constant) and isinstance(a.value,str) and isinstance(b.value,str):
                catalog[a.value] = b.value
    if isinstance(node, ast.Tuple) and len(node.elts) == 4:
        a,b = node.elts[:2]
        if isinstance(a,ast.Constant) and isinstance(b,ast.Constant) and isinstance(a.value,str) and isinstance(b.value,str):
            catalog[a.value] = b.value
    if isinstance(node,ast.Tuple) and len(node.elts) == 4:
        a,b = node.elts[-2:]
        if isinstance(a,ast.Constant) and isinstance(b,ast.Constant) and isinstance(a.value,str) and isinstance(b.value,str):
            catalog[a.value] = b.value
    if isinstance(node, ast.Call) and isinstance(node.func,ast.Name) and node.func.id == 'row':
        a,b = node.args[:2]
        if isinstance(a,ast.Constant) and isinstance(b,ast.Constant):
            catalog[a.value] = b.value
folder = root/'assets/i18n'; folder.mkdir(parents=True,exist_ok=True)
for lang,data in [('en',catalog),('pl',{k:k for k in catalog})]:
    (folder/f'{lang}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
from PySide6.QtCore import QLibraryInfo
import shutil
shutil.copy2(Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))/'qtbase_pl.qm',folder/'qtbase_pl.qm')
