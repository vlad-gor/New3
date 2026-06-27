$ErrorActionPreference = "Stop"

$extensionFiles = @(
    "ms-python.python-2026.5.2026061001.vsix",
    "ms-python.vscode-pylance-2026.2.106.vsix",
    "ms-python.debugpy-2026.7.11751011.vsix",
    "ms-python.vscode-python-envs-1.37.2026062601.vsix",
    "ms-toolsai.jupyter-2026.6.2026061001.vsix",
    "ms-toolsai.jupyter-keymap-1.1.2.vsix",
    "ms-toolsai.jupyter-renderers-1.3.2025062701.vsix",
    "ms-toolsai.vscode-jupyter-slideshow-0.1.6.vsix",
    "ms-toolsai.vscode-jupyter-cell-tags-0.1.9.vsix"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$codeCommand = Get-Command code -ErrorAction Stop

foreach ($file in $extensionFiles) {
    $path = Join-Path $scriptDir $file
    if (-not (Test-Path $path)) {
        throw "Missing VSIX file: $path"
    }

    Write-Host "Installing $file"
    & $codeCommand.Source --install-extension $path
}

Write-Host "Offline VS Code extension installation completed."
