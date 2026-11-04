"""Use the Qt wheel's compatible MSVC runtime throughout the portable folder."""
from pathlib import Path
import shutil
import PySide6

root = Path(__file__).resolve().parents[1]/'dist/SubtitleStudio/_internal'
source = Path(PySide6.__file__).parent
for name in ('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','msvcp140_codecvt_ids.dll','concrt140.dll'):
    if (source/name).is_file():
        shutil.copy2(source/name,root/name)

# Qt's Windows build imports the OS ICU API (unversioned symbols).
# PyInstaller may resolve an unrelated ICU from PATH with version-suffixed symbols.
# Windows supplies this dependency; shipping that unrelated DLL breaks Qt imports.
for name in ('icuuc.dll','icuuc.dll.disabled','icudt78.dll'):
    (root/name).unlink(missing_ok=True)
