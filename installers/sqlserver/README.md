# SQL Server Express installer

This directory contains the saved offline Windows x64 installer for SQL Server 2022 Express Core.

To fit GitHub's file-size limit, the installer is stored as split parts.

## Files

- `parts/SQLEXPR_x64_ENU.exe.part00`
- `parts/SQLEXPR_x64_ENU.exe.part01`
- `parts/SQLEXPR_x64_ENU.exe.part02`
- `parts/SHA256SUMS.txt`: checksums for the split parts
- `SQLEXPR_x64_ENU.exe.sha256`: checksum for the rebuilt installer
- `rebuild-sqlserver-express-installer.ps1`: PowerShell script that rebuilds the installer from the parts

## Source

- https://download.microsoft.com/download/3/8/d/38de7036-2433-4207-8eae-06e247e17b25/SQLEXPR_x64_ENU.exe

## SHA-256

`2e61c8bbde6021f9026c54ad9db4bbb1227e68761d4c00a6a50a2c70fe7afe05`

## Rebuild installer

Run this in PowerShell from the `installers/sqlserver` directory:

```powershell
.\rebuild-sqlserver-express-installer.ps1
```

This creates:

```text
SQLEXPR_x64_ENU.exe
```

and verifies its SHA-256 hash.

You can also verify the split files before rebuilding:

```powershell
cd .\parts
sha256sum -c .\SHA256SUMS.txt
cd ..
```

## Example usage

Extract the media:

```powershell
.\SQLEXPR_x64_ENU.exe /Q /X:C:\SQLExpress2022
```

Then install SQL Server Express from the extracted setup media.
