param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& $Python scripts/package_spec.py
if ($LASTEXITCODE -ne 0) { throw 'Specification generation failed' }
& $Python -m PyInstaller --noconfirm SubtitleStudio.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
& $Python scripts/fix_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'MSVC runtime normalization failed' }
Copy-Item -LiteralPath README.md,LICENSE,THIRD_PARTY.md -Destination dist/SubtitleStudio
Copy-Item -LiteralPath docs -Destination dist/SubtitleStudio -Recurse -Force
Copy-Item -LiteralPath examples -Destination dist/SubtitleStudio -Recurse -Force
& $Python scripts/collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
& $Python scripts/check_package.py
if ($LASTEXITCODE -ne 0) { throw 'Packaged executable verification failed' }
Copy-Item -LiteralPath docs -Destination dist/SubtitleStudio -Recurse -Force
Copy-Item -LiteralPath examples -Destination dist/SubtitleStudio -Recurse -Force
Compress-Archive -Path dist/SubtitleStudio -DestinationPath dist/SubtitleStudio-Windows-x64.zip -Force
& $Python scripts/package_source.py
if ($LASTEXITCODE -ne 0) { throw 'Source archive creation failed' }
