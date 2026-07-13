# Node.js installer

This directory contains the saved Windows x64 installer for Node.js.

## File

- `node-v24.18.0-x64.msi`: official Windows x64 MSI installer for Node.js 24.18.0 LTS
- `node-v24.18.0-x64.msi.sha256`: saved checksum file

## Source

- https://nodejs.org/dist/latest-v24.x/node-v24.18.0-x64.msi

## SHA-256

`e30cd4ca15529583afe0efc978f1ae3ab3a93c2400c222d0752d17900552ebb3`

## Example usage

Interactive install:

```powershell
msiexec /i .\node-v24.18.0-x64.msi
```

Silent install:

```powershell
msiexec /i .\node-v24.18.0-x64.msi /qn /norestart
```
