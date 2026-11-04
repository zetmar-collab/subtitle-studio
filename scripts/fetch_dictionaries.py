"""Fetch optional local Hunspell resources and their upstream notices, pinned to a commit."""
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parents[1]/'assets/dictionaries'
root.mkdir(parents=True,exist_ok=True)
commit = json.load(urllib.request.urlopen('https://api.github.com/repos/LibreOffice/dictionaries/commits/master'))['sha']
sources = {
    'pl': ('pl_PL','pl_PL'), 'en': ('en','en_US'), 'de': ('de','de_DE_frami'),
    'es': ('es','es_ES'), 'it': ('it_IT','it_IT'), 'uk': ('uk_UA','uk_UA'),
    'fr': ('fr_FR','fr'),
}
manifest = {}
for lang,(directory,base) in sources.items():
    entries = json.load(urllib.request.urlopen(f'https://api.github.com/repos/LibreOffice/dictionaries/contents/{directory}?ref={commit}'))
    if lang == 'fr':
        # French upstream keeps current dictionary resources in a nested directory.
        if not any(e['name'].endswith('.dic') for e in entries):
            directories = [e for e in entries if e['type'] == 'dir' and e['name'] == 'dictionaries']
            if directories:
                directory += '/'+directories[0]['name']
                entries = json.load(urllib.request.urlopen(f'https://api.github.com/repos/LibreOffice/dictionaries/contents/{directory}?ref={commit}'))
        names = [e['name'][:-4] for e in entries if e['name'].endswith('.dic') and not e['name'].startswith('hyph')]
        base = names[0] if names else base
    for ext in ('dic','aff'):
        url = f'https://raw.githubusercontent.com/LibreOffice/dictionaries/{commit}/{directory}/{base}.{ext}'
        (root/f'{lang}.{ext}').write_bytes(urllib.request.urlopen(url,timeout=60).read())
    notices = root/'licenses'/lang; notices.mkdir(parents=True,exist_ok=True)
    for entry in entries:
        if entry['type'] == 'file' and any(word in entry['name'].lower() for word in ('readme','license','copying')):
            (notices/entry['name']).write_bytes(urllib.request.urlopen(entry['download_url'],timeout=60).read())
    manifest[lang] = dict(commit=commit,directory=directory,base=base)
    print(lang,'OK',flush=True)
(root/'sources.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
