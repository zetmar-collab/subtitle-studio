"""Create a reproducible source bundle without build caches or local runtime data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
directories = ('core','ui','srtstudio','assets','scripts','tests','docs','examples','installer','.github')
files = ['main.py','requirements.txt','requirements-lock.txt','requirements-dev.txt','README.md','LICENSE','THIRD_PARTY.md','CHANGELOG.md','.gitignore']
paths = [root/name for name in files]
for name in directories:
    paths.extend(p for p in (root/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
target = root/'dist/SubtitleStudio-source.zip'
with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=6) as archive:
    for path in sorted(paths):
        archive.write(path,Path('SubtitleStudio-source')/path.relative_to(root))
print(target)
