# VS Code installer

This directory contains the saved Windows x64 installer for Visual Studio Code.
To fit GitHub's file-size limit, the installer is stored as split parts.

## Files

- `parts/VSCodeUserSetup-x64-1.126.0.exe.part00`
- `parts/VSCodeUserSetup-x64-1.126.0.exe.part01`
- `parts/VSCodeUserSetup-x64-1.126.0.exe.part02`
- `parts/SHA256SUMS.txt`: checksums for the split parts
- `VSCodeUserSetup-x64-1.126.0.exe.sha256`: checksum for the rebuilt installer
- `rebuild-vscode-installer.ps1`: PowerShell script that rebuilds the installer from the parts

## Source

- https://update.code.visualstudio.com/latest/win32-x64-user/stable

## SHA-256

`1e883039671841218ef4be1fc308f79d0512ed7bc3213578f4931a2581a7de37`

## Rebuild installer

Run this in PowerShell from the `installers/vscode` directory:

```powershell
.\rebuild-vscode-installer.ps1
```

This creates:

```text
VSCodeUserSetup-x64-1.126.0.exe
```

and verifies its SHA-256 hash.

You can also verify the split files before rebuilding:

```powershell
cd .\parts
sha256sum -c .\SHA256SUMS.txt
cd ..
```

## Example usage

Interactive install:

```powershell
.\VSCodeUserSetup-x64-1.126.0.exe
```

Silent install:

```powershell
.\VSCodeUserSetup-x64-1.126.0.exe /VERYSILENT /NORESTART /MERGETASKS=!runcode
```
