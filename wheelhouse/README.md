# Offline wheelhouse

This directory contains Python wheels downloaded into the repository for
offline installation.

## Available bundle

- `py313-windows-x86_64/`: CPython 3.13 wheels for Windows x86_64

## Install example

Windows:
```powershell
py -3.13 -m pip install --no-index `
  --find-links=wheelhouse/py313-windows-x86_64 `
  -r wheelhouse/py313-windows-x86_64/requirements.txt
```

The pinned bundle includes:

- `numpy`
- `pandas`
- `notebook`
- `ipykernel`
- `matplotlib`
- `matplotlib-venn`
- `docxtpl`
- `lxml`
- `openpyxl`
- `pillow`
- `python-docx`
- `pyxlsb`
- `xlsxwriter`
- the runtime dependencies required to launch Jupyter Notebook offline

Example launch after installation:

```powershell
py -3.13 -m notebook
```

This bundle is platform-specific and targets Windows x86_64.
