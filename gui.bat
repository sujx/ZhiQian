@echo off
chcp 65001 >nul
setlocal
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

set "PY=.gui-venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [ERROR] GUI venv not found: %PY%
    echo Please run: "C:\Program Files\Python312\python.exe" -m venv .gui-venv
    echo then: .gui-venv\Scripts\pip install customtkinter html2text beautifulsoup4
    pause
    exit /b 1
)

"%PY%" -m exporter.gui %*

echo.
pause
