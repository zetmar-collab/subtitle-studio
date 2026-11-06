from importlib.metadata import distribution
from packaging.requirements import Requirement
from pathlib import Path
import shutil
import sys

target = Path(__file__).resolve().parents[1]/'dist/SubtitleStudio/licenses'
target.mkdir(parents=True,exist_ok=True)
pending = [Requirement(line).name for line in (Path(__file__).resolve().parents[1]/'requirements.txt').read_text().splitlines() if line.strip()]
seen = set()
while pending:
    name = pending.pop()
    key = name.lower().replace('_','-')
    if key in seen:
        continue
    seen.add(key)
    dist = distribution(name)
    for dependency in dist.requires or []:
        requirement = Requirement(dependency)
        if requirement.marker is None or requirement.marker.evaluate({'extra':''}):
            pending.append(requirement.name)
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
