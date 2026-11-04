"""Install into an isolated workspace folder, verify the app, then uninstall."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import winreg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.version import VERSION

root = Path(__file__).resolve().parents[1]
setup = root/f'dist/SubtitleStudio-Setup-{VERSION}-x64.exe'
test_root = root/'build/installer-smoke'
key_path = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{2B60A64D-053F-40CF-B11A-1B1B2B39A358}_is1'


def registered():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path):
            return True
    except FileNotFoundError:
        return False


if registered():
    raise SystemExit('An installed copy already exists. Refusing to change its registration during testing.')
test_root.mkdir(parents=True,exist_ok=True)
folder = Path(tempfile.mkdtemp(prefix='run-',dir=test_root))
destination = folder/'installed-app'
report = dict(setup_sha256=hashlib.sha256(setup.read_bytes()).hexdigest())
try:
    subprocess.run([str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/NOICONS','/TASKS=',
                    f'/DIR={destination}',f'/LOG={folder / "install.log"}'],check=True,timeout=120)
    assert registered()
    source = root/'dist/SubtitleStudio/SubtitleStudio.exe'
    installed = destination/'SubtitleStudio.exe'
    assert installed.read_bytes() == source.read_bytes()
    assert not (destination/'_internal/icuuc.dll').exists()
    report['installation'] = 'passed'
    report['installed_exe_sha256'] = hashlib.sha256(installed.read_bytes()).hexdigest()
    subprocess.run([sys.executable,str(root/'scripts/check_package.py'),str(destination)],check=True,timeout=90)
    report['installed_application_preview_and_export'] = 'passed'
finally:
    uninstaller = destination/'unins000.exe'
    if uninstaller.exists():
        user_project = destination/'User-project.subtitlelogo.json'
        user_project.write_text('{"test":"preserve user project"}',encoding='utf-8')
        subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={folder / "uninstall.log"}'],check=True,timeout=120)
        deadline = time.monotonic()+15
        while (destination/'SubtitleStudio.exe').exists() and time.monotonic()<deadline:
            time.sleep(.2)
        assert not (destination/'SubtitleStudio.exe').exists()
        assert not registered()
        assert user_project.read_text(encoding='utf-8') == '{"test":"preserve user project"}'
        report['uninstall_and_user_project_preservation'] = 'passed'
    else:
        report['uninstall_and_user_project_preservation'] = 'not tested'
    (root/'docs/setup-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
