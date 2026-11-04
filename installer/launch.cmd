@echo off
where py.exe >nul 2>&1
if errorlevel 1 (
    python "%~dp0bootstrap.py"
) else (
    py -3.12 "%~dp0bootstrap.py"
)
if errorlevel 1 (
    echo Subtitle Studio requires 64-bit Python 3.12. See https://www.python.org/downloads/
    pause
    exit /b 1
)
