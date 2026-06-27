param(
    [string]$PythonInstallDir = (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313"),
    [string]$VenvPath = (Join-Path $PSScriptRoot ".venv"),
    [switch]$RegisterJupyterKernel,
    [switch]$SkipGit,
    [switch]$SkipVSCode,
    [switch]$SkipPythonPackages,
    [switch]$SkipVSCodeExtensions
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-PathExists {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path $Path)) {
        throw "$Description not found: $Path"
    }
}

function Assert-FileHashValue {
    param(
        [string]$Path,
        [string]$ExpectedHash
    )

    $actualHash = (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $ExpectedHash.ToLowerInvariant()) {
        throw "Checksum mismatch for $Path. Expected $ExpectedHash, got $actualHash"
    }
}

function Assert-ChecksumFile {
    param(
        [string]$BaseDirectory,
        [string]$ChecksumFile
    )

    $lines = Get-Content -Path $ChecksumFile | Where-Object { $_.Trim() }
    foreach ($line in $lines) {
        $parts = $line -split "\s+", 2
        if ($parts.Count -ne 2) {
            throw "Invalid checksum line in ${ChecksumFile}: $line"
        }

        $expectedHash = $parts[0].Trim().ToLowerInvariant()
        $relativePath = $parts[1].Trim()
        $targetPath = Join-Path $BaseDirectory $relativePath
        Assert-PathExists -Path $targetPath -Description "Checksum target"
        Assert-FileHashValue -Path $targetPath -ExpectedHash $expectedHash
    }
}

function Invoke-Installer {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Description
    )

    Write-Step $Description
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "$Description failed with exit code $($process.ExitCode)"
    }
}

function Add-ToProcessPath {
    param([string[]]$Paths)

    foreach ($path in $Paths) {
        if (-not $path) {
            continue
        }

        if (-not (Test-Path $path)) {
            continue
        }

        $currentEntries = $env:PATH -split ';'
        if ($currentEntries -notcontains $path) {
            $env:PATH = "$path;$env:PATH"
        }
    }
}

function Ensure-UserPathEntries {
    param([string[]]$Paths)

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @()
    if ($userPath) {
        $entries = $userPath -split ';'
    }

    $updated = $false
    foreach ($path in $Paths) {
        if (-not $path) {
            continue
        }

        if (-not (Test-Path $path)) {
            continue
        }

        if ($entries -notcontains $path) {
            $entries += $path
            $updated = $true
        }
    }

    if ($updated) {
        $newUserPath = ($entries | Where-Object { $_ }) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    }
}

function Refresh-ProcessPathFromRegistry {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $combined = @($machinePath, $userPath) | Where-Object { $_ }
    if ($combined.Count -gt 0) {
        $env:PATH = ($combined -join ';')
    }
}

function Resolve-VSCodeCommand {
    $candidatePaths = @()

    if ($env:VSCODE_COMMAND) {
        $candidatePaths += $env:VSCODE_COMMAND
    }

    $commandFromPath = Get-Command code -ErrorAction SilentlyContinue
    if ($commandFromPath) {
        $candidatePaths += $commandFromPath.Source
    }

    $candidatePaths += @(
        (Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\bin\code.cmd"),
        (Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\Code.exe"),
        (Join-Path ${env:ProgramFiles} "Microsoft VS Code\bin\code.cmd"),
        (Join-Path ${env:ProgramFiles} "Microsoft VS Code\Code.exe")
    )

    return $candidatePaths |
        Where-Object { $_ -and (Test-Path $_) } |
        Select-Object -First 1
}

$pythonInstaller = Join-Path $PSScriptRoot "installers\python-3.13.14-amd64.exe"
$gitInstaller = Join-Path $PSScriptRoot "installers\git\Git-2.54.0-64-bit.exe"
$gitChecksumFile = Join-Path $PSScriptRoot "installers\git\Git-2.54.0-64-bit.exe.sha256"
$vscodeRebuildScript = Join-Path $PSScriptRoot "installers\vscode\rebuild-vscode-installer.ps1"
$vscodeInstaller = Join-Path $PSScriptRoot "installers\vscode\VSCodeUserSetup-x64-1.126.0.exe"
$vscodePartsChecksumFile = Join-Path $PSScriptRoot "installers\vscode\parts\SHA256SUMS.txt"
$pythonWheelhouse = Join-Path $PSScriptRoot "wheelhouse\py313-windows-x86_64"
$pythonRequirements = Join-Path $pythonWheelhouse "requirements.txt"
$vscodeExtensionsDir = Join-Path $PSScriptRoot "vscode-extensions"
$vscodeExtensionsChecksumFile = Join-Path $vscodeExtensionsDir "SHA256SUMS.txt"
$vscodeExtensionsInstaller = Join-Path $vscodeExtensionsDir "install-offline-vscode-extensions.ps1"

Write-Step "Verifying offline assets"
Assert-PathExists -Path $pythonInstaller -Description "Python installer"
Assert-PathExists -Path $gitInstaller -Description "Git installer"
Assert-PathExists -Path $gitChecksumFile -Description "Git checksum file"
Assert-PathExists -Path $vscodeRebuildScript -Description "VS Code rebuild script"
Assert-PathExists -Path $vscodePartsChecksumFile -Description "VS Code parts checksum file"
Assert-PathExists -Path $pythonWheelhouse -Description "Python wheelhouse"
Assert-PathExists -Path $pythonRequirements -Description "Python requirements file"
Assert-PathExists -Path $vscodeExtensionsChecksumFile -Description "VS Code extensions checksum file"
Assert-PathExists -Path $vscodeExtensionsInstaller -Description "VS Code extensions installer script"

Assert-FileHashValue -Path $pythonInstaller -ExpectedHash "c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0"
Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\git") -ChecksumFile $gitChecksumFile
Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\vscode\parts") -ChecksumFile $vscodePartsChecksumFile
Assert-ChecksumFile -BaseDirectory $vscodeExtensionsDir -ChecksumFile $vscodeExtensionsChecksumFile

if (-not $SkipGit) {
    Invoke-Installer -FilePath $gitInstaller -Description "Installing Git for Windows" -Arguments @(
        "/VERYSILENT",
        "/NORESTART",
        "/NOCANCEL",
        "/SP-",
        "/CLOSEAPPLICATIONS",
        "/RESTARTAPPLICATIONS"
    )
}

Invoke-Installer -FilePath $pythonInstaller -Description "Installing Python 3.13" -Arguments @(
    "/quiet",
    "InstallAllUsers=0",
    "TargetDir=""$PythonInstallDir""",
    "Include_pip=1",
    "Include_test=0",
    "AssociateFiles=0",
    "Shortcuts=0",
    "PrependPath=1",
    "Include_launcher=1",
    "InstallLauncherAllUsers=0"
)

$pythonExe = Join-Path $PythonInstallDir "python.exe"
Assert-PathExists -Path $pythonExe -Description "Installed python executable"

Write-Step "Rebuilding VS Code installer"
& $vscodeRebuildScript
Assert-PathExists -Path $vscodeInstaller -Description "Rebuilt VS Code installer"

if (-not $SkipVSCode) {
    Invoke-Installer -FilePath $vscodeInstaller -Description "Installing Visual Studio Code" -Arguments @(
        "/VERYSILENT",
        "/SP-",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/MERGETASKS=!runcode,addcontextmenufiles,addcontextmenufolders,associatewithfiles,addtopath"
    )
}

$gitPathCandidates = @(
    (Join-Path $env:ProgramFiles "Git\cmd"),
    (Join-Path $env:LOCALAPPDATA "Programs\Git\cmd")
)
$vsCodeBinCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\bin"),
    (Join-Path ${env:ProgramFiles} "Microsoft VS Code\bin")
)
$pythonPathCandidates = @(
    $PythonInstallDir,
    (Join-Path $PythonInstallDir "Scripts")
)

Ensure-UserPathEntries -Paths ($gitPathCandidates + $vsCodeBinCandidates + $pythonPathCandidates)
Refresh-ProcessPathFromRegistry
Add-ToProcessPath -Paths ($gitPathCandidates + $vsCodeBinCandidates + $pythonPathCandidates)

$venvPython = $null
if (-not $SkipPythonPackages) {
    Write-Step "Creating Python virtual environment"
    & $pythonExe -m venv $VenvPath

    $venvPython = Join-Path $VenvPath "Scripts\python.exe"
    Assert-PathExists -Path $venvPython -Description "Virtual environment python executable"

    Write-Step "Installing offline Python package bundle"
    & $venvPython -m pip install --no-index --find-links $pythonWheelhouse -r $pythonRequirements

    if ($RegisterJupyterKernel) {
        Write-Step "Registering Jupyter kernel"
        & $venvPython -m ipykernel install --user --name "offline-dev-py313" --display-name "Offline Dev Python 3.13"
    }
}

if (-not $SkipVSCodeExtensions) {
    $codeCommand = Resolve-VSCodeCommand
    if (-not $codeCommand) {
        throw "Could not locate the VS Code command after installation."
    }

    $env:VSCODE_COMMAND = $codeCommand

    Write-Step "Installing offline VS Code extensions"
    & $vscodeExtensionsInstaller
}

Write-Step "Installed tool versions"
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($gitCommand) {
    & $gitCommand.Source --version
}

& $pythonExe --version

if ($venvPython) {
    & $venvPython --version
}

$codeCommand = Resolve-VSCodeCommand
if ($codeCommand) {
    $codeVersion = & $codeCommand --version
    if ($codeVersion) {
        $codeVersion | Select-Object -First 1 | ForEach-Object { Write-Host "VS Code $_" }
    }
}

Write-Step "Offline development suite installation completed"
Write-Host "Python installed to: $PythonInstallDir"
Write-Host "Virtual environment: $VenvPath"
Write-Host "Repo-local Python packages came from: $pythonWheelhouse"
Write-Host "VS Code extensions installed from: $vscodeExtensionsDir"
Write-Host "If this was run from an old terminal window, open a new terminal to pick up updated PATH and shell integrations."
