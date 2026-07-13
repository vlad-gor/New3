Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installerScript = Join-Path $scriptRoot "install-offline-dev-suite.ps1"

function Add-LogLine {
    param(
        [System.Windows.Forms.TextBox]$TextBox,
        [string]$Text
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return
    }

    $appendAction = [System.Action]{
        $TextBox.AppendText($Text + [Environment]::NewLine)
        $TextBox.SelectionStart = $TextBox.TextLength
        $TextBox.ScrollToCaret()
    }

    if ($TextBox.InvokeRequired) {
        $TextBox.BeginInvoke($appendAction) | Out-Null
    }
    else {
        $appendAction.Invoke()
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Offline Development Suite Installer"
$form.Size = New-Object System.Drawing.Size(980, 760)
$form.StartPosition = "CenterScreen"
$form.AutoScaleMode = "Font"

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "Offline Development Suite Installer"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$titleLabel.AutoSize = $true
$titleLabel.Location = New-Object System.Drawing.Point(20, 15)
$form.Controls.Add($titleLabel)

$descLabel = New-Object System.Windows.Forms.Label
$descLabel.Text = "Select the components to install and click Install. Run this GUI as Administrator if you want Node.js, PostgreSQL, SQL Server, or SSMS."
$descLabel.AutoSize = $true
$descLabel.MaximumSize = New-Object System.Drawing.Size(920, 0)
$descLabel.Location = New-Object System.Drawing.Point(20, 50)
$form.Controls.Add($descLabel)

$componentsGroup = New-Object System.Windows.Forms.GroupBox
$componentsGroup.Text = "Components"
$componentsGroup.Location = New-Object System.Drawing.Point(20, 90)
$componentsGroup.Size = New-Object System.Drawing.Size(440, 250)
$form.Controls.Add($componentsGroup)

$settingsGroup = New-Object System.Windows.Forms.GroupBox
$settingsGroup.Text = "Settings"
$settingsGroup.Location = New-Object System.Drawing.Point(480, 90)
$settingsGroup.Size = New-Object System.Drawing.Size(470, 250)
$form.Controls.Add($settingsGroup)

$logGroup = New-Object System.Windows.Forms.GroupBox
$logGroup.Text = "Installer log"
$logGroup.Location = New-Object System.Drawing.Point(20, 350)
$logGroup.Size = New-Object System.Drawing.Size(930, 310)
$form.Controls.Add($logGroup)

$componentY = 30

function New-CheckBox {
    param(
        [string]$Text,
        [int]$X,
        [int]$Y,
        [bool]$Checked = $true,
        [bool]$Enabled = $true
    )
    $checkbox = New-Object System.Windows.Forms.CheckBox
    $checkbox.Text = $Text
    $checkbox.AutoSize = $true
    $checkbox.Location = New-Object System.Drawing.Point($X, $Y)
    $checkbox.Checked = $Checked
    $checkbox.Enabled = $Enabled
    return $checkbox
}

$cbGit = New-CheckBox -Text "Git for Windows" -X 20 -Y $componentY
$componentY += 28
$cbNode = New-CheckBox -Text "Node.js" -X 20 -Y $componentY
$componentY += 28
$cbPython = New-CheckBox -Text "Python 3.13 (required base component)" -X 20 -Y $componentY -Checked $true -Enabled $false
$componentY += 28
$cbPythonPackages = New-CheckBox -Text "Python package bundle" -X 40 -Y $componentY
$componentY += 28
$cbJupyterKernel = New-CheckBox -Text "Register Jupyter kernel" -X 40 -Y $componentY
$componentY += 28
$cbPostgreSQL = New-CheckBox -Text "PostgreSQL 15" -X 20 -Y $componentY
$componentY += 28
$cbPgAdmin = New-CheckBox -Text "pgAdmin (with PostgreSQL)" -X 40 -Y $componentY
$componentY += 28
$cbSqlServer = New-CheckBox -Text "SQL Server 2022 Express" -X 20 -Y $componentY
$componentY += 28
$cbSSMS = New-CheckBox -Text "SQL Server Management Studio (SSMS)" -X 20 -Y $componentY
$componentY += 28
$cbVSCode = New-CheckBox -Text "Visual Studio Code" -X 20 -Y $componentY
$componentY += 28
$cbVSCodeExtensions = New-CheckBox -Text "VS Code extensions" -X 40 -Y $componentY

foreach ($checkbox in @(
    $cbGit, $cbNode, $cbPython, $cbPythonPackages, $cbJupyterKernel,
    $cbPostgreSQL, $cbPgAdmin, $cbSqlServer, $cbSSMS, $cbVSCode, $cbVSCodeExtensions
)) {
    $componentsGroup.Controls.Add($checkbox)
}

$cbPostgreSQL.Add_CheckedChanged({
    $cbPgAdmin.Enabled = $cbPostgreSQL.Checked
    if (-not $cbPostgreSQL.Checked) {
        $cbPgAdmin.Checked = $false
    }
    elseif (-not $cbPgAdmin.Checked) {
        $cbPgAdmin.Checked = $true
    }
})

$cbVSCode.Add_CheckedChanged({
    $cbVSCodeExtensions.Enabled = $cbVSCode.Checked
    if (-not $cbVSCode.Checked) {
        $cbVSCodeExtensions.Checked = $false
    }
    elseif (-not $cbVSCodeExtensions.Checked) {
        $cbVSCodeExtensions.Checked = $true
    }
})

$cbPythonPackages.Add_CheckedChanged({
    $cbJupyterKernel.Enabled = $cbPythonPackages.Checked
    if (-not $cbPythonPackages.Checked) {
        $cbJupyterKernel.Checked = $false
    }
    elseif (-not $cbJupyterKernel.Checked) {
        $cbJupyterKernel.Checked = $true
    }
})

function New-SettingLabel {
    param([string]$Text, [int]$X, [int]$Y)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.AutoSize = $true
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    return $label
}

function New-SettingTextBox {
    param([string]$Text, [int]$X, [int]$Y, [int]$Width = 300)
    $textbox = New-Object System.Windows.Forms.TextBox
    $textbox.Text = $Text
    $textbox.Location = New-Object System.Drawing.Point($X, $Y)
    $textbox.Size = New-Object System.Drawing.Size($Width, 24)
    return $textbox
}

$settingsY = 30
$settingsGroup.Controls.Add((New-SettingLabel -Text "Python install dir" -X 20 -Y $settingsY))
$tbPythonDir = New-SettingTextBox -Text '$env:LOCALAPPDATA\Programs\Python\Python313' -X 160 -Y ($settingsY - 3) -Width 280
$tbPythonDir.Text = [System.IO.Path]::Combine($env:LOCALAPPDATA, 'Programs\Python\Python313')
$settingsGroup.Controls.Add($tbPythonDir)

$settingsY += 35
$settingsGroup.Controls.Add((New-SettingLabel -Text "PostgreSQL install dir" -X 20 -Y $settingsY))
$tbPostgresDir = New-SettingTextBox -Text 'C:\Program Files\PostgreSQL\15' -X 160 -Y ($settingsY - 3) -Width 280
$settingsGroup.Controls.Add($tbPostgresDir)

$settingsY += 35
$settingsGroup.Controls.Add((New-SettingLabel -Text "PostgreSQL password" -X 20 -Y $settingsY))
$tbPostgresPassword = New-SettingTextBox -Text 'ChangeMe_Postgres15!' -X 160 -Y ($settingsY - 3) -Width 280
$tbPostgresPassword.UseSystemPasswordChar = $true
$settingsGroup.Controls.Add($tbPostgresPassword)

$settingsY += 35
$settingsGroup.Controls.Add((New-SettingLabel -Text "PostgreSQL port" -X 20 -Y $settingsY))
$tbPostgresPort = New-SettingTextBox -Text '5432' -X 160 -Y ($settingsY - 3) -Width 120
$settingsGroup.Controls.Add($tbPostgresPort)

$settingsY += 35
$settingsGroup.Controls.Add((New-SettingLabel -Text "SQL Express instance" -X 20 -Y $settingsY))
$tbSqlInstance = New-SettingTextBox -Text 'SQLEXPRESS' -X 160 -Y ($settingsY - 3) -Width 180
$settingsGroup.Controls.Add($tbSqlInstance)

$settingsY += 35
$settingsGroup.Controls.Add((New-SettingLabel -Text "SSMS install path" -X 20 -Y $settingsY))
$tbSsmsPath = New-SettingTextBox -Text 'C:\Program Files\Microsoft SQL Server Management Studio 22\Release' -X 160 -Y ($settingsY - 3) -Width 280
$settingsGroup.Controls.Add($tbSsmsPath)

$settingsY += 35
$settingsGroup.Controls.Add((New-SettingLabel -Text "Log file (optional)" -X 20 -Y $settingsY))
$tbLogFile = New-SettingTextBox -Text (Join-Path $scriptRoot 'offline-dev-suite-install.log') -X 160 -Y ($settingsY - 3) -Width 280
$settingsGroup.Controls.Add($tbLogFile)

$logTextBox = New-Object System.Windows.Forms.TextBox
$logTextBox.Multiline = $true
$logTextBox.ScrollBars = 'Vertical'
$logTextBox.ReadOnly = $true
$logTextBox.WordWrap = $false
$logTextBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$logTextBox.Location = New-Object System.Drawing.Point(15, 25)
$logTextBox.Size = New-Object System.Drawing.Size(900, 255)
$logGroup.Controls.Add($logTextBox)

$installButton = New-Object System.Windows.Forms.Button
$installButton.Text = "Install selected components"
$installButton.Location = New-Object System.Drawing.Point(20, 675)
$installButton.Size = New-Object System.Drawing.Size(240, 35)
$form.Controls.Add($installButton)

$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = "Close"
$closeButton.Location = New-Object System.Drawing.Point(840, 675)
$closeButton.Size = New-Object System.Drawing.Size(110, 35)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Ready."
$statusLabel.AutoSize = $true
$statusLabel.Location = New-Object System.Drawing.Point(280, 684)
$form.Controls.Add($statusLabel)

$runningProcess = $null

$installButton.Add_Click({
    if (-not (Test-Path $installerScript)) {
        [System.Windows.Forms.MessageBox]::Show("Installer script not found: $installerScript", "Error", "OK", "Error") | Out-Null
        return
    }

    if ($runningProcess -and -not $runningProcess.HasExited) {
        [System.Windows.Forms.MessageBox]::Show("Installation is already running.", "Information", "OK", "Information") | Out-Null
        return
    }

    $argList = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $installerScript
    )

    if (-not $cbGit.Checked) { $argList += "-SkipGit" }
    if (-not $cbNode.Checked) { $argList += "-SkipNode" }
    if (-not $cbPostgreSQL.Checked) { $argList += "-SkipPostgreSQL" }
    elseif (-not $cbPgAdmin.Checked) { $argList += "-SkipPgAdmin" }
    if (-not $cbSqlServer.Checked) { $argList += "-SkipSqlServer" }
    if (-not $cbSSMS.Checked) { $argList += "-SkipSSMS" }
    if (-not $cbVSCode.Checked) { $argList += "-SkipVSCode" }
    if (-not $cbPythonPackages.Checked) { $argList += "-SkipPythonPackages" }
    if (-not $cbVSCodeExtensions.Checked) { $argList += "-SkipVSCodeExtensions" }
    if (-not $cbJupyterKernel.Checked) { $argList += "-SkipJupyterKernelRegistration" }

    $argList += @("-PythonInstallDir", $tbPythonDir.Text)
    $argList += @("-PostgreSqlInstallDir", $tbPostgresDir.Text)
    $argList += @("-PostgreSqlSuperPassword", $tbPostgresPassword.Text)
    $argList += @("-PostgreSqlPort", $tbPostgresPort.Text)
    $argList += @("-SqlServerInstanceName", $tbSqlInstance.Text)
    $argList += @("-SsmsInstallPath", $tbSsmsPath.Text)

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "powershell.exe"
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    foreach ($arg in $argList) {
        [void]$psi.ArgumentList.Add($arg)
    }

    $logTextBox.Clear()
    Add-LogLine -TextBox $logTextBox -Text ("Command: powershell.exe " + (($argList | ForEach-Object {
        if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
    }) -join ' '))

    if ($tbLogFile.Text.Trim()) {
        Remove-Item -Path $tbLogFile.Text -ErrorAction SilentlyContinue
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $process.EnableRaisingEvents = $true

    $stdoutHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)
        if ($eventArgs.Data) {
            Add-LogLine -TextBox $logTextBox -Text $eventArgs.Data
            if ($tbLogFile.Text.Trim()) {
                Add-Content -Path $tbLogFile.Text -Value $eventArgs.Data
            }
        }
    }

    $stderrHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)
        if ($eventArgs.Data) {
            Add-LogLine -TextBox $logTextBox -Text ("[stderr] " + $eventArgs.Data)
            if ($tbLogFile.Text.Trim()) {
                Add-Content -Path $tbLogFile.Text -Value ("[stderr] " + $eventArgs.Data)
            }
        }
    }

    $exitHandler = [System.EventHandler]{
        param($sender, $eventArgs)
        $exitCode = $sender.ExitCode
        $form.BeginInvoke([System.Action]{
            $installButton.Enabled = $true
            if ($exitCode -eq 0) {
                $statusLabel.Text = "Installation completed successfully."
                Add-LogLine -TextBox $logTextBox -Text "Installation completed successfully."
            }
            else {
                $statusLabel.Text = "Installation failed. Exit code: $exitCode"
                Add-LogLine -TextBox $logTextBox -Text "Installation failed. Exit code: $exitCode"
            }
        }) | Out-Null
    }

    $process.add_OutputDataReceived($stdoutHandler)
    $process.add_ErrorDataReceived($stderrHandler)
    $process.add_Exited($exitHandler)

    $runningProcess = $process
    $installButton.Enabled = $false
    $statusLabel.Text = "Installation in progress..."

    [void]$process.Start()
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
})

[void]$form.ShowDialog()
