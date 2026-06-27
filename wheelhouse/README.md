# Offline wheelhouse

This directory contains Python wheels downloaded into the repository for
offline installation.

## Available bundle

- `py313-linux-x86_64/`: CPython 3.13 wheels for Linux x86_64

## Install example

```bash
python3.13 -m pip install --no-index \
  --find-links=wheelhouse/py313-linux-x86_64 \
  -r wheelhouse/py313-linux-x86_64/requirements.txt
```

The wheels in `py313-linux-x86_64/` are platform-specific. If you need
Windows or macOS bundles, create a separate directory for each target.
