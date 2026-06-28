@echo off
setlocal
cd /d "%~dp0"

py -3.8 -V >nul 2>nul
if errorlevel 1 (
    echo Python 3.8 was not found via the "py" launcher.
    echo Install Python 3.8 to build a Windows 7 compatible executable.
    exit /b 1
)

echo Installing or updating PyInstaller for Python 3.8...
py -3.8 -m pip install --upgrade pip pyinstaller
if errorlevel 1 exit /b 1

echo Building Windows 7 compatible NetDiagPeer.exe...
py -3.8 -m PyInstaller --noconfirm --clean --onefile --windowed --name NetDiagPeer gui_main.py
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo Output: dist\NetDiagPeer.exe
