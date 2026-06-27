# Offline installers

This directory contains saved Windows installers used by this repository.

## Python 3.13

File:

- `python-3.13.14-amd64.exe`: official 64-bit Windows installer for Python 3.13.14

Source:

- https://www.python.org/ftp/python/3.13.14/python-3.13.14-amd64.exe

SHA-256:

`c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0`

Example usage:

```powershell
.\python-3.13.14-amd64.exe
```

```powershell
.\python-3.13.14-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
```

## VS Code

Files:

- `vscode/parts/VSCodeUserSetup-x64-1.126.0.exe.part*`: split archive parts for the official Windows x64 user installer
- `vscode/VSCodeUserSetup-x64-1.126.0.exe.sha256`: checksum for the rebuilt installer
- `vscode/rebuild-vscode-installer.ps1`: helper script to rebuild the installer from the saved parts

See `installers/vscode/README.md` for the source URL, checksum, and example usage.

## Git for Windows

Files:

- `git/Git-2.54.0-64-bit.exe`: official 64-bit Git for Windows installer
- `git/Git-2.54.0-64-bit.exe.sha256`: saved checksum file

See `installers/git/README.md` for the source URL, checksum, and example usage.
