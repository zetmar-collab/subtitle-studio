"""Install dependencies from PyPI into a per-user environment and launch the app."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or struct.calcsize('P') != 8:
        raise SystemExit('Subtitle Studio requires 64-bit Python 3.12.')

    source = Path(__file__).resolve().parent / 'app'
    runtime = Path(os.environ['LOCALAPPDATA']) / 'SubtitleStudio' / 'online-runtime-0.2.1'
    python = runtime / 'Scripts' / 'python.exe'
    ready = runtime / 'requirements-installed.txt'
    requirements = source / 'requirements.txt'
    expected = requirements.read_bytes()
    if not python.is_file() or not ready.is_file() or ready.read_bytes() != expected:
        print('Preparing Subtitle Studio. The first launch downloads dependencies from PyPI.', flush=True)
        venv.create(runtime, with_pip=True)
        subprocess.run(
            [str(python), '-m', 'pip', '--isolated', 'install', '--index-url', 'https://pypi.org/simple',
             '-r', str(requirements)],
            check=True,
        )
        ready.write_bytes(expected)
    if not args.prepare_only:
        subprocess.Popen([str(python.with_name('pythonw.exe')), str(source / 'main.py')], cwd=source)


if __name__ == '__main__':
    main()
