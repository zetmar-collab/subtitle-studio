@echo off
where py.exe >nul 2>&1
if errorlevel 1 (
    python "%~dp0bootstrap.py"
) else (
    py -3.12 "%~dp0bootstrap.py"
)
if errorlevel 1 (
    echo Subtitle Studio could not start. Check the error above and make sure Python 3.12 x64 is installed.
    pause
    exit /b 1
)
