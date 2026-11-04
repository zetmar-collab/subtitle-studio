from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

target = Path(__file__).resolve().parents[1]/'dist/SubtitleStudio/licenses'
target.mkdir(parents=True,exist_ok=True)
for name in ('PySide6_Essentials','PySide6_Addons','shiboken6','pysubs2','charset-normalizer','spylls'):
    dist = distribution(name)
    for file in dist.files or []:
        if '.dist-info/' in str(file).replace('\\','/') and any(word in Path(str(file)).name.lower() for word in ('license','copying','copyright')):
            path = Path(dist.locate_file(file))
            relative = str(file).replace('\\','/').split('.dist-info/',1)[1].removeprefix('licenses/')
            destination = target/name/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,destination)
python_license = Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():
    shutil.copy2(python_license,target/'Python-LICENSE.txt')
shutil.copytree(Path(__file__).resolve().parents[1]/'assets/licenses',target/'Qt-open-source',dirs_exist_ok=True)
# Qt Multimedia ships FFmpeg shared libraries as part of the Qt wheel.
# The exact Qt release source location and rebuilding instructions are documented in THIRD_PARTY.md.
