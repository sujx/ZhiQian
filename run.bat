@echo off
chcp 65001 >nul
setlocal
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

set "PY=C:\Users\sujx\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

if not exist "%PY%" (
    echo [ERROR] Python env not found: %PY%
    echo Please create venv first.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo.
    echo === wiznote-exporter ===
    echo Usage:
    echo   run.bat --list
    echo   run.bat --source local --input ^<wiznote data dir^> --output ^<output dir^>
    echo Example:
    echo   run.bat --source local --input "C:\Users\sujx\Documents\My Knowledge\" --output "D:\notes"
    echo.
    "%PY%" -m exporter --help
) else (
    "%PY%" -m exporter %*
)

echo.
pause
