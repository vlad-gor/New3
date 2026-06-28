@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher "py" was not found.
    echo Install Python 3 on Windows and try again.
    exit /b 1
)

echo Installing or updating PyInstaller...
py -3 -m pip install --upgrade pip pyinstaller
if errorlevel 1 exit /b 1

echo Building NetDiagPeer.exe...
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name NetDiagPeer gui_main.py
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo Output: dist\NetDiagPeer.exe
