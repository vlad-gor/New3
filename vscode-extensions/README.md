# VS Code offline extensions

This directory contains VSIX packages for offline installation of VS Code
extensions used for Python development, Jupyter notebooks, and Git work.

## Included extensions

Primary extensions:

- `eamodio.gitlens-2026.6.270545.vsix`
- `ms-python.python-2026.5.2026061001.vsix`
- `ms-toolsai.jupyter-2026.6.2026061001.vsix`

Included dependency and extension-pack VSIX files:

- `ms-python.vscode-pylance-2026.2.106.vsix`
- `ms-python.debugpy-2026.7.11751011.vsix`
- `ms-python.vscode-python-envs-1.37.2026062601.vsix`
- `ms-toolsai.jupyter-keymap-1.1.2.vsix`
- `ms-toolsai.jupyter-renderers-1.3.2025062701.vsix`
- `ms-toolsai.vscode-jupyter-slideshow-0.1.6.vsix`
- `ms-toolsai.vscode-jupyter-cell-tags-0.1.9.vsix`

Checksums and source URLs are saved in:

- `SHA256SUMS.txt`
- `manifest.json`

## Install with PowerShell

Run the helper script from this directory:

```powershell
.\install-offline-vscode-extensions.ps1
```

## Install manually

Install the VSIX files in this order:

```powershell
code --install-extension .\eamodio.gitlens-2026.6.270545.vsix
code --install-extension .\ms-python.python-2026.5.2026061001.vsix
code --install-extension .\ms-python.vscode-pylance-2026.2.106.vsix
code --install-extension .\ms-python.debugpy-2026.7.11751011.vsix
code --install-extension .\ms-python.vscode-python-envs-1.37.2026062601.vsix
code --install-extension .\ms-toolsai.jupyter-2026.6.2026061001.vsix
code --install-extension .\ms-toolsai.jupyter-keymap-1.1.2.vsix
code --install-extension .\ms-toolsai.jupyter-renderers-1.3.2025062701.vsix
code --install-extension .\ms-toolsai.vscode-jupyter-slideshow-0.1.6.vsix
code --install-extension .\ms-toolsai.vscode-jupyter-cell-tags-0.1.9.vsix
```
