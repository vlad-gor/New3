# SQL Server Management Studio installer

This directory contains the saved SQL Server Management Studio 22 bootstrapper.

## Files

- `vs_SSMS.exe`: official SSMS 22.7.2 bootstrapper
- `vs_SSMS.exe.sha256`: saved checksum file
- `create-offline-layout.ps1`: helper script for creating a local offline SSMS layout on a connected machine

## Source

- https://aka.ms/ssms/22/release/vs_SSMS.exe

Direct resolved download used for this repository:

- https://download.visualstudio.microsoft.com/download/pr/4c1645e2-fb0d-4889-a6b9-3fb6fd3a782f/1f383a4bc871f3100d0fac5b4a0ef1dfed088806410b5b0d004164b1fe2a434c/vs_SSMS.exe

## SHA-256

`1f383a4bc871f3100d0fac5b4a0ef1dfed088806410b5b0d004164b1fe2a434c`

## Important note

`vs_SSMS.exe` is a bootstrapper, not a full standalone installer.  
For a disconnected installation, you should first create a local layout on a machine with internet access and then copy that layout to the offline machine.

## Example usage

Silent online install:

```powershell
.\vs_SSMS.exe --quiet --norestart --wait
```

Create a complete offline layout:

```powershell
.\create-offline-layout.ps1
```
