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

## Node.js

Files:

- `node/node-v24.18.0-x64.msi`: official Windows x64 MSI installer for Node.js 24.18.0 LTS
- `node/node-v24.18.0-x64.msi.sha256`: saved checksum file

See `installers/node/README.md` for the source URL, checksum, and example usage.

## Git for Windows

Files:

- `git/Git-2.54.0-64-bit.exe`: official 64-bit Git for Windows installer
- `git/Git-2.54.0-64-bit.exe.sha256`: saved checksum file

See `installers/git/README.md` for the source URL, checksum, and example usage.

## SQL Server Express

Files:

- `sqlserver/parts/SQLEXPR_x64_ENU.exe.part*`: split archive parts for the SQL Server 2022 Express Core installer
- `sqlserver/SQLEXPR_x64_ENU.exe.sha256`: checksum for the rebuilt installer
- `sqlserver/rebuild-sqlserver-express-installer.ps1`: helper script to rebuild the installer from the saved parts

See `installers/sqlserver/README.md` for the source URL, checksum, and example usage.

## SQL Server Management Studio (SSMS)

Files:

- `ssms/vs_SSMS.exe`: official SSMS bootstrapper
- `ssms/vs_SSMS.exe.sha256`: saved checksum file
- `ssms/create-offline-layout.ps1`: helper script for creating a local offline layout

See `installers/ssms/README.md` for the source URL, checksum, layout guidance, and example usage.
