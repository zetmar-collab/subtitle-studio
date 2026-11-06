"""Build the online installer from current Git-visible source files."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--compiler', default=str(root/'build/tools/inno/ISCC.exe'))
args = parser.parse_args()
compiler = Path(args.compiler)
if not compiler.is_file():
    found = shutil.which('ISCC.exe')
    if not found:
        raise SystemExit('Specify the Inno Setup compiler using --compiler.')
    compiler = Path(found)
files = subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],
                       cwd=root,capture_output=True,check=True).stdout.decode('utf-8').split('\0')
build = root/'build'
build.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='online-source-',dir=build) as folder:
    source = Path(folder).resolve()
    for name in files:
        if name and (root/name).is_file():
            destination = source/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(root/name,destination)
    subprocess.run([str(compiler.resolve()),'/Q',f'/DSourceRoot={source}',
                    str(root/'installer/SubtitleStudioOnline.iss')],cwd=root,check=True)
