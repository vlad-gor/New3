# Offline wheelhouse

This directory contains Python wheels downloaded into the repository for
offline installation.

## Available bundles

- `py313-linux-x86_64/`: CPython 3.13 wheels for Linux x86_64
- `py313-windows-x86_64/`: CPython 3.13 wheels for Windows x86_64

## Install examples

Linux:
```bash
python3.13 -m pip install --no-index \
  --find-links=wheelhouse/py313-linux-x86_64 \
  -r wheelhouse/py313-linux-x86_64/requirements.txt
```

Windows:
```powershell
py -3.13 -m pip install --no-index `
  --find-links=wheelhouse/py313-windows-x86_64 `
  -r wheelhouse/py313-windows-x86_64/requirements.txt
```

These bundles are platform-specific. Keep a separate directory for each
target OS and architecture.
