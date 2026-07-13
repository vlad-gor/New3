$ErrorActionPreference = "Stop"

$extensionFiles = @(
    "eamodio.gitlens-2026.6.270545.vsix",
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

$candidateCommands = @()
if ($env:VSCODE_COMMAND) {
    $candidateCommands += $env:VSCODE_COMMAND
}

$commandFromPath = Get-Command code -ErrorAction SilentlyContinue
if ($commandFromPath) {
    $candidateCommands += $commandFromPath.Source
}

$candidateCommands += @(
    (Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\bin\code.cmd"),
    (Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\Code.exe"),
    (Join-Path ${env:ProgramFiles} "Microsoft VS Code\bin\code.cmd"),
    (Join-Path ${env:ProgramFiles} "Microsoft VS Code\Code.exe")
)

$codeCommandPath = $candidateCommands |
    Where-Object { $_ -and (Test-Path $_) } |
    Select-Object -First 1

if (-not $codeCommandPath) {
    throw "Could not locate VS Code command. Set VSCODE_COMMAND or install VS Code first."
}

foreach ($file in $extensionFiles) {
    $path = Join-Path $scriptDir $file
    if (-not (Test-Path $path)) {
        throw "Missing VSIX file: $path"
    }

    Write-Host "Installing $file"
    & $codeCommandPath --install-extension $path
}

Write-Host "Offline VS Code extension installation completed."
