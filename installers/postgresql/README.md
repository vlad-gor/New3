# PostgreSQL 15 installer

This directory contains the saved Windows x64 installer for PostgreSQL 15.

To fit GitHub's file-size limit, the installer is stored as split parts.

## Files

- `parts/postgresql-15.18-1-windows-x64.exe.part00`
- `parts/postgresql-15.18-1-windows-x64.exe.part01`
- `parts/postgresql-15.18-1-windows-x64.exe.part02`
- `parts/postgresql-15.18-1-windows-x64.exe.part03`
- `parts/SHA256SUMS.txt`: checksums for the split parts
- `postgresql-15.18-1-windows-x64.exe.sha256`: checksum for the rebuilt installer
- `rebuild-postgresql-installer.ps1`: PowerShell script that rebuilds the installer from the parts

## Source

- https://get.enterprisedb.com/postgresql/postgresql-15.18-1-windows-x64.exe

## SHA-256

`8d1ac971810b819d861ac6bc47ceaa87a23251c9194f66255ec4ac208d15d688`

## Important note

EnterpriseDB does not prominently publish a stable checksum catalog for these installers on the public downloads page.
This repository stores the downloaded installer split into parts and saves the verified checksum used during repository preparation.

## Rebuild installer

Run this in PowerShell from the `installers/postgresql` directory:

```powershell
.\rebuild-postgresql-installer.ps1
```

This creates:

```text
postgresql-15.18-1-windows-x64.exe
```

and verifies its SHA-256 hash.

You can also verify the split files before rebuilding:

```powershell
cd .\parts
sha256sum -c .\SHA256SUMS.txt
cd ..
```

## Example usage

Silent install:

```powershell
.\postgresql-15.18-1-windows-x64.exe --mode unattended --unattendedmodeui none
```
