$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
python -m PyInstaller --noconfirm --onedir --windowed --name SubtitleStudio --icon assets/icon.ico --add-data 'assets;assets' --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick main.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
python scripts/fix_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'MSVC runtime normalization failed' }
Copy-Item -LiteralPath README.md,LICENSE,THIRD_PARTY.md -Destination dist/SubtitleStudio
Copy-Item -LiteralPath docs -Destination dist/SubtitleStudio -Recurse -Force
Copy-Item -LiteralPath examples -Destination dist/SubtitleStudio -Recurse -Force
python scripts/collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
python scripts/check_package.py
if ($LASTEXITCODE -ne 0) { throw 'Packaged executable verification failed' }
Copy-Item -LiteralPath docs -Destination dist/SubtitleStudio -Recurse -Force
Copy-Item -LiteralPath examples -Destination dist/SubtitleStudio -Recurse -Force
Compress-Archive -Path dist/SubtitleStudio -DestinationPath dist/SubtitleStudio-Windows-x64.zip -Force
python scripts/package_source.py
if ($LASTEXITCODE -ne 0) { throw 'Source archive creation failed' }
