$ErrorActionPreference = "Stop"

param(
    [string]$LayoutPath = (Join-Path $PSScriptRoot "layout")
)

$bootstrapper = Join-Path $PSScriptRoot "vs_SSMS.exe"
if (-not (Test-Path $bootstrapper)) {
    throw "SSMS bootstrapper not found: $bootstrapper"
}

New-Item -ItemType Directory -Force -Path $LayoutPath | Out-Null

$arguments = @(
    "--layout",
    $LayoutPath,
    "--all"
)

$process = Start-Process -FilePath $bootstrapper -ArgumentList $arguments -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "SSMS offline layout creation failed with exit code $($process.ExitCode)"
}

Write-Host "Created SSMS offline layout at: $LayoutPath"
