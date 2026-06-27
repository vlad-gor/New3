# Python installer

This directory contains the saved Windows installer for Python 3.13.

## File

- `python-3.13.14-amd64.exe`: official 64-bit Windows installer for Python 3.13.14

## Source

- https://www.python.org/ftp/python/3.13.14/python-3.13.14-amd64.exe

## SHA-256

`c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0`

## Example usage

Interactive install:

```powershell
.\python-3.13.14-amd64.exe
```

Silent install for all users with PATH enabled:

```powershell
.\python-3.13.14-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
```
