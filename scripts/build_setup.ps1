param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath 'dist/SubtitleStudio/SubtitleStudio.exe')) {
    throw 'Build the portable application first with scripts/build.ps1.'
}
if (-not $Compiler) {
    $localCompiler = Join-Path (Get-Location) 'build/tools/inno/ISCC.exe'
    $installedCompiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $localCompiler) { $Compiler = $localCompiler }
    elseif ($installedCompiler) { $Compiler = $installedCompiler.Source }
    else { throw 'Inno Setup compiler not found. Use -Compiler with the full path to ISCC.exe.' }
}
& $Compiler '/Q' 'installer/SubtitleStudio.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
