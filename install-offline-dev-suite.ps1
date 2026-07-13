param(
    [string]$PythonInstallDir = (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313"),
    [switch]$SkipJupyterKernelRegistration,
    [switch]$SkipNode,
    [switch]$SkipGit,
    [switch]$SkipPostgreSQL,
    [switch]$SkipSqlServer,
    [switch]$SkipSSMS,
    [switch]$SkipVSCode,
    [switch]$SkipPythonPackages,
    [switch]$SkipVSCodeExtensions,
    [string]$PostgreSqlInstallDir = "C:\Program Files\PostgreSQL\15",
    [string]$PostgreSqlSuperPassword = "ChangeMe_Postgres15!",
    [string]$PostgreSqlPort = "5432",
    [string]$SqlServerInstanceName = "SQLEXPRESS",
    [string]$SsmsInstallPath = "C:\Program Files\Microsoft SQL Server Management Studio 22\Release"
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

function Invoke-MsiInstaller {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Description
    )

    Write-Step $Description
    $msiArguments = @(
        "/i",
        $FilePath
    ) + $Arguments
    $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $msiArguments -Wait -PassThru
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

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-AdministratorFor {
    param([string[]]$Components)

    if (-not (Test-IsAdministrator)) {
        $joined = $Components -join ", "
        throw "Administrator privileges are required to install: $joined. Re-run the installer as Administrator or skip those components."
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

function Update-VSCodeSettings {
    param(
        [string]$PythonExe,
        [string]$InterpreterPath
    )

    $settingsDir = Join-Path $env:APPDATA "Code\User"
    $settingsPath = Join-Path $settingsDir "settings.json"
    New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null

    $updatedWithPython = $false
    if (Test-Path $PythonExe) {
        $tempScript = Join-Path $env:TEMP "offline_dev_suite_update_vscode_settings.py"
        $scriptContent = @'
import json
import os
import shutil
import sys

settings_path = sys.argv[1]
interpreter_path = sys.argv[2]
data = {}

if os.path.exists(settings_path):
    raw = open(settings_path, "r", encoding="utf-8").read()
    if raw.strip():
        loaded = None
        try:
            import json5
            loaded = json5.loads(raw)
        except Exception:
            try:
                loaded = json.loads(raw)
            except Exception:
                backup_path = settings_path + ".backup"
                if not os.path.exists(backup_path):
                    shutil.copyfile(settings_path, backup_path)
                loaded = {}
        if isinstance(loaded, dict):
            data = loaded

data["python.defaultInterpreterPath"] = interpreter_path
data["jupyter.jupyterServerType"] = "local"

with open(settings_path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
'@
        Set-Content -Path $tempScript -Value $scriptContent -Encoding utf8
        try {
            & $PythonExe $tempScript $settingsPath $InterpreterPath
            if ($LASTEXITCODE -eq 0) {
                $updatedWithPython = $true
            }
        }
        finally {
            Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
        }
    }

    if (-not $updatedWithPython) {
        $settingsObject = [pscustomobject]@{}
        if (Test-Path $settingsPath) {
            $raw = Get-Content -Path $settingsPath -Raw
            if ($raw.Trim()) {
                try {
                    $settingsObject = $raw | ConvertFrom-Json
                }
                catch {
                    $backupPath = "$settingsPath.backup"
                    if (-not (Test-Path $backupPath)) {
                        Copy-Item -Path $settingsPath -Destination $backupPath
                    }
                    $settingsObject = [pscustomobject]@{}
                }
            }
        }

        $settingsObject | Add-Member -NotePropertyName "python.defaultInterpreterPath" -NotePropertyValue $InterpreterPath -Force
        $settingsObject | Add-Member -NotePropertyName "jupyter.jupyterServerType" -NotePropertyValue "local" -Force
        $settingsObject | ConvertTo-Json -Depth 20 | Set-Content -Path $settingsPath -Encoding utf8
    }

    Write-Host "vscode-settings=$settingsPath"
}

$pythonInstaller = Join-Path $PSScriptRoot "installers\python-3.13.14-amd64.exe"
$nodeInstaller = Join-Path $PSScriptRoot "installers\node\node-v24.18.0-x64.msi"
$nodeChecksumFile = Join-Path $PSScriptRoot "installers\node\node-v24.18.0-x64.msi.sha256"
$postgresqlRebuildScript = Join-Path $PSScriptRoot "installers\postgresql\rebuild-postgresql-installer.ps1"
$postgresqlInstaller = Join-Path $PSScriptRoot "installers\postgresql\postgresql-15.18-1-windows-x64.exe"
$postgresqlChecksumFile = Join-Path $PSScriptRoot "installers\postgresql\postgresql-15.18-1-windows-x64.exe.sha256"
$postgresqlPartsChecksumFile = Join-Path $PSScriptRoot "installers\postgresql\parts\SHA256SUMS.txt"
$gitInstaller = Join-Path $PSScriptRoot "installers\git\Git-2.54.0-64-bit.exe"
$gitChecksumFile = Join-Path $PSScriptRoot "installers\git\Git-2.54.0-64-bit.exe.sha256"
$sqlServerRebuildScript = Join-Path $PSScriptRoot "installers\sqlserver\rebuild-sqlserver-express-installer.ps1"
$sqlServerInstaller = Join-Path $PSScriptRoot "installers\sqlserver\SQLEXPR_x64_ENU.exe"
$sqlServerChecksumFile = Join-Path $PSScriptRoot "installers\sqlserver\SQLEXPR_x64_ENU.exe.sha256"
$sqlServerPartsChecksumFile = Join-Path $PSScriptRoot "installers\sqlserver\parts\SHA256SUMS.txt"
$ssmsBootstrapper = Join-Path $PSScriptRoot "installers\ssms\vs_SSMS.exe"
$ssmsChecksumFile = Join-Path $PSScriptRoot "installers\ssms\vs_SSMS.exe.sha256"
$ssmsLayoutBootstrapper = Join-Path $PSScriptRoot "installers\ssms\layout\vs_SSMS.exe"
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
Assert-PathExists -Path $nodeInstaller -Description "Node.js installer"
Assert-PathExists -Path $nodeChecksumFile -Description "Node.js checksum file"
Assert-PathExists -Path $postgresqlRebuildScript -Description "PostgreSQL rebuild script"
Assert-PathExists -Path $postgresqlChecksumFile -Description "PostgreSQL checksum file"
Assert-PathExists -Path $postgresqlPartsChecksumFile -Description "PostgreSQL parts checksum file"
Assert-PathExists -Path $gitInstaller -Description "Git installer"
Assert-PathExists -Path $gitChecksumFile -Description "Git checksum file"
Assert-PathExists -Path $sqlServerRebuildScript -Description "SQL Server rebuild script"
Assert-PathExists -Path $sqlServerChecksumFile -Description "SQL Server checksum file"
Assert-PathExists -Path $sqlServerPartsChecksumFile -Description "SQL Server parts checksum file"
Assert-PathExists -Path $ssmsBootstrapper -Description "SSMS bootstrapper"
Assert-PathExists -Path $ssmsChecksumFile -Description "SSMS checksum file"
Assert-PathExists -Path $vscodeRebuildScript -Description "VS Code rebuild script"
Assert-PathExists -Path $vscodePartsChecksumFile -Description "VS Code parts checksum file"
Assert-PathExists -Path $pythonWheelhouse -Description "Python wheelhouse"
Assert-PathExists -Path $pythonRequirements -Description "Python requirements file"
Assert-PathExists -Path $vscodeExtensionsChecksumFile -Description "VS Code extensions checksum file"
Assert-PathExists -Path $vscodeExtensionsInstaller -Description "VS Code extensions installer script"

Assert-FileHashValue -Path $pythonInstaller -ExpectedHash "c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0"
Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\node") -ChecksumFile $nodeChecksumFile
Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\postgresql\parts") -ChecksumFile $postgresqlPartsChecksumFile
Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\git") -ChecksumFile $gitChecksumFile
Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\sqlserver\parts") -ChecksumFile $sqlServerPartsChecksumFile
Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\ssms") -ChecksumFile $ssmsChecksumFile
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

if (-not $SkipNode) {
    Assert-AdministratorFor -Components @("Node.js")
    Invoke-MsiInstaller -FilePath $nodeInstaller -Description "Installing Node.js" -Arguments @(
        "/qn",
        "/norestart"
    )
}

if (-not $SkipPostgreSQL) {
    Assert-AdministratorFor -Components @("PostgreSQL 15")
    Write-Step "Rebuilding PostgreSQL 15 installer"
    & $postgresqlRebuildScript
    Assert-PathExists -Path $postgresqlInstaller -Description "Rebuilt PostgreSQL installer"
    Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\postgresql") -ChecksumFile $postgresqlChecksumFile

    $postgresqlDataDir = Join-Path $PostgreSqlInstallDir "data"
    Invoke-Installer -FilePath $postgresqlInstaller -Description "Installing PostgreSQL 15" -Arguments @(
        "--mode",
        "unattended",
        "--unattendedmodeui",
        "none",
        "--install_runtimes",
        "1",
        "--prefix",
        $PostgreSqlInstallDir,
        "--datadir",
        $postgresqlDataDir,
        "--serverport",
        $PostgreSqlPort,
        "--superpassword",
        $PostgreSqlSuperPassword,
        "--servicepassword",
        $PostgreSqlSuperPassword,
        "--enable-components",
        "server,commandlinetools",
        "--create_shortcuts",
        "0"
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
    "InstallLauncherAllUsers=0",
    "SimpleInstall=1"
)

$pythonExe = Join-Path $PythonInstallDir "python.exe"
Assert-PathExists -Path $pythonExe -Description "Installed python executable"

Write-Step "Rebuilding VS Code installer"
& $vscodeRebuildScript
Assert-PathExists -Path $vscodeInstaller -Description "Rebuilt VS Code installer"

if (-not $SkipSqlServer) {
    Assert-AdministratorFor -Components @("SQL Server Express")
    Write-Step "Rebuilding SQL Server Express installer"
    & $sqlServerRebuildScript
    Assert-PathExists -Path $sqlServerInstaller -Description "Rebuilt SQL Server Express installer"
    Assert-ChecksumFile -BaseDirectory (Join-Path $PSScriptRoot "installers\sqlserver") -ChecksumFile $sqlServerChecksumFile

    $sqlExtractDir = Join-Path $env:TEMP "offline-sqlserver-express"
    if (Test-Path $sqlExtractDir) {
        Remove-Item -Path $sqlExtractDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $sqlExtractDir | Out-Null

    Invoke-Installer -FilePath $sqlServerInstaller -Description "Extracting SQL Server Express media" -Arguments @(
        "/Q",
        "/X:$sqlExtractDir"
    )

    $sqlSetupExe = Join-Path $sqlExtractDir "setup.exe"
    Assert-PathExists -Path $sqlSetupExe -Description "SQL Server setup executable"

    Invoke-Installer -FilePath $sqlSetupExe -Description "Installing SQL Server Express" -Arguments @(
        "/Q",
        "/IACCEPTSQLSERVERLICENSETERMS",
        "/ACTION=Install",
        "/FEATURES=SQLENGINE",
        "/INSTANCENAME=$SqlServerInstanceName",
        "/ADDCURRENTUSERASSQLADMIN",
        "/SQLSYSADMINACCOUNTS=BUILTIN\Administrators",
        "/SQLSVCSTARTUPTYPE=Automatic",
        "/TCPENABLED=1",
        "/NPENABLED=1",
        "/UpdateEnabled=0"
    )
}

if (-not $SkipVSCode) {
    Invoke-Installer -FilePath $vscodeInstaller -Description "Installing Visual Studio Code" -Arguments @(
        "/VERYSILENT",
        "/SP-",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/MERGETASKS=!runcode,addcontextmenufiles,addcontextmenufolders,associatewithfiles,addtopath"
    )
}

if (-not $SkipSSMS) {
    Assert-AdministratorFor -Components @("SQL Server Management Studio")
    $ssmsInstallerToUse = $ssmsBootstrapper
    $ssmsArguments = @(
        "--quiet",
        "--wait",
        "--norestart",
        "--installPath",
        $SsmsInstallPath
    )

    if (Test-Path $ssmsLayoutBootstrapper) {
        $ssmsInstallerToUse = $ssmsLayoutBootstrapper
        $ssmsArguments = @(
            "--noWeb",
            "--quiet",
            "--wait",
            "--norestart",
            "--installPath",
            $SsmsInstallPath
        )
    }

    Invoke-Installer -FilePath $ssmsInstallerToUse -Description "Installing SQL Server Management Studio" -Arguments $ssmsArguments
}

$gitPathCandidates = @(
    (Join-Path $env:ProgramFiles "Git\cmd"),
    (Join-Path $env:LOCALAPPDATA "Programs\Git\cmd")
)
$nodePathCandidates = @(
    (Join-Path ${env:ProgramFiles} "nodejs"),
    (Join-Path $env:LOCALAPPDATA "Programs\nodejs")
)
$postgresqlPathCandidates = @(
    (Join-Path $PostgreSqlInstallDir "bin")
)
$vsCodeBinCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\bin"),
    (Join-Path ${env:ProgramFiles} "Microsoft VS Code\bin")
)
$pythonPathCandidates = @(
    $PythonInstallDir,
    (Join-Path $PythonInstallDir "Scripts")
)

Ensure-UserPathEntries -Paths ($gitPathCandidates + $nodePathCandidates + $postgresqlPathCandidates + $vsCodeBinCandidates + $pythonPathCandidates)
Refresh-ProcessPathFromRegistry
Add-ToProcessPath -Paths ($gitPathCandidates + $nodePathCandidates + $postgresqlPathCandidates + $vsCodeBinCandidates + $pythonPathCandidates)

if (-not $SkipPythonPackages) {
    Write-Step "Installing offline Python package bundle globally"
    & $pythonExe -m pip install --no-index --find-links $pythonWheelhouse -r $pythonRequirements

    if (-not $SkipJupyterKernelRegistration) {
        Write-Step "Registering Jupyter kernel"
        & $pythonExe -m ipykernel install --user --name "offline-dev-py313" --display-name "Offline Dev Python 3.13"
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

Write-Step "Updating VS Code user settings"
Update-VSCodeSettings -PythonExe $pythonExe -InterpreterPath $pythonExe

Write-Step "Installed tool versions"
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($gitCommand) {
    & $gitCommand.Source --version
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) {
    & $nodeCommand.Source --version
}

$npmCommand = Get-Command npm -ErrorAction SilentlyContinue
if ($npmCommand) {
    & $npmCommand.Source --version
}

$psqlCommand = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlCommand) {
    & $psqlCommand.Source --version
}

& $pythonExe --version
& $pythonExe -m pip --version
& $pythonExe -c "import PyInstaller; from importlib import metadata; print('pyinstaller=' + PyInstaller.__version__); print('auto-py-to-exe=' + metadata.version('auto-py-to-exe'))"

if (-not $SkipPythonPackages -and -not $SkipJupyterKernelRegistration) {
    Write-Host "jupyter-kernel=Offline Dev Python 3.13"
}

$codeCommand = Resolve-VSCodeCommand
if ($codeCommand) {
    $codeVersion = & $codeCommand --version
    if ($codeVersion) {
        $codeVersion | Select-Object -First 1 | ForEach-Object { Write-Host "VS Code $_" }
    }
}

Write-Step "Offline development suite installation completed"
if (-not $SkipNode) {
    Write-Host "Node.js installer: $nodeInstaller"
}
if (-not $SkipPostgreSQL) {
    Write-Host "PostgreSQL 15 install dir: $PostgreSqlInstallDir"
    Write-Host "PostgreSQL port: $PostgreSqlPort"
    Write-Host "PostgreSQL password: $PostgreSqlSuperPassword"
}
Write-Host "Python installed to: $PythonInstallDir"
Write-Host "Global site-packages: $(Join-Path $PythonInstallDir 'Lib\site-packages')"
if (-not $SkipSqlServer) {
    Write-Host "SQL Server Express instance: $SqlServerInstanceName"
}
if (-not $SkipSSMS) {
    Write-Host "SSMS install path: $SsmsInstallPath"
}
Write-Host "Repo-local Python packages came from: $pythonWheelhouse"
Write-Host "VS Code extensions installed from: $vscodeExtensionsDir"
Write-Host "If this was run from an old terminal window, open a new terminal to pick up updated PATH and shell integrations."
