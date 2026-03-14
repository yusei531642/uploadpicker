param(
    [string]$Action = ''
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPath = Join-Path $ProjectRoot '.venv'
$PythonExe = Join-Path $VenvPath 'Scripts\python.exe'
$EnvExample = Join-Path $ProjectRoot '.env.example'
$EnvFile = Join-Path $ProjectRoot '.env'
$LaunchScript = Join-Path $ProjectRoot 'installer\LaunchUploadPicker.ps1'
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'UploadPicker.lnk'
$StartMenuDir = Join-Path ([Environment]::GetFolderPath('Programs')) 'UploadPicker'
$StartMenuShortcut = Join-Path $StartMenuDir 'UploadPicker.lnk'

function Write-Log {
    param([System.Windows.Forms.TextBox]$OutputBox, [string]$Message)
    $OutputBox.AppendText("$Message`r`n")
    $OutputBox.SelectionStart = $OutputBox.TextLength
    $OutputBox.ScrollToCaret()
    [System.Windows.Forms.Application]::DoEvents()
}

function Get-PythonCommand {
    $Candidates = @(
        @{ FilePath = 'py'; Arguments = '-3.11 --version'; Command = 'py -3.11' },
        @{ FilePath = 'py'; Arguments = '-3 --version'; Command = 'py -3' },
        @{ FilePath = 'python'; Arguments = '--version'; Command = 'python' }
    )
    foreach ($Candidate in $Candidates) {
        try {
            $proc = Start-Process -FilePath $Candidate.FilePath -ArgumentList $Candidate.Arguments -PassThru -Wait -NoNewWindow -RedirectStandardOutput "$env:TEMP\uploadpicker_py_out.txt" -RedirectStandardError "$env:TEMP\uploadpicker_py_err.txt"
            if ($proc.ExitCode -eq 0) {
                return $Candidate.Command
            }
        } catch {
        }
    }
    return $null
}

function Install-PythonIfMissing {
    param([System.Windows.Forms.TextBox]$OutputBox)
    $cmd = Get-PythonCommand
    if ($cmd) {
        Write-Log $OutputBox "Python detected: $cmd"
        return $cmd
    }
    Write-Log $OutputBox 'Python not found. Installing Python 3.11 via winget...'
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'winget が見つかりません。Microsoft Store 版 App Installer か Python を先に入れてください。'
    }
    $install = Start-Process -FilePath 'winget' -ArgumentList 'install --exact --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements' -WorkingDirectory $ProjectRoot -PassThru -Wait -NoNewWindow
    if ($install.ExitCode -ne 0) {
        throw 'Python のインストールに失敗しました。'
    }
    Start-Sleep -Seconds 2
    $cmd = Get-PythonCommand
    if (-not $cmd) {
        throw 'Python のインストール後もコマンドが見つかりません。PowerShell を再起動して再試行してください。'
    }
    Write-Log $OutputBox "Python installed: $cmd"
    return $cmd
}

function Invoke-Step {
    param(
        [System.Windows.Forms.TextBox]$OutputBox,
        [string]$Command,
        [string]$Arguments
    )
    Write-Log $OutputBox ("> {0} {1}" -f $Command, $Arguments)
    $process = Start-Process -FilePath $Command -ArgumentList $Arguments -WorkingDirectory $ProjectRoot -PassThru -Wait -NoNewWindow
    if ($process.ExitCode -ne 0) {
        throw "Command failed: $Command $Arguments"
    }
}

function New-ShortcutFile {
    param([string]$ShortcutPath, [string]$TargetPath, [string]$Arguments, [string]$WorkingDirectory)
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Save()
}

function Create-Shortcuts {
    if (-not (Test-Path $StartMenuDir)) {
        New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
    }
    $PowerShellPath = (Get-Command powershell.exe).Source
    $Args = "-ExecutionPolicy Bypass -File `"$LaunchScript`""
    New-ShortcutFile -ShortcutPath $DesktopShortcut -TargetPath $PowerShellPath -Arguments $Args -WorkingDirectory $ProjectRoot
    New-ShortcutFile -ShortcutPath $StartMenuShortcut -TargetPath $PowerShellPath -Arguments $Args -WorkingDirectory $ProjectRoot
}

function Install-UploadPicker {
    param([System.Windows.Forms.TextBox]$OutputBox)
    $pythonCmd = Install-PythonIfMissing -OutputBox $OutputBox
    if (-not (Test-Path $VenvPath)) {
        Invoke-Step -OutputBox $OutputBox -Command 'cmd.exe' -Arguments "/c $pythonCmd -m venv \"$VenvPath\""
    } else {
        Write-Log $OutputBox 'Virtual environment already exists. Reusing it.'
    }
    if ((Test-Path $EnvExample) -and (-not (Test-Path $EnvFile))) {
        Copy-Item $EnvExample $EnvFile
        Write-Log $OutputBox '.env created from .env.example'
    }
    Invoke-Step -OutputBox $OutputBox -Command $PythonExe -Arguments '-m pip install --upgrade pip'
    Invoke-Step -OutputBox $OutputBox -Command $PythonExe -Arguments '-m pip install -e .'
    Create-Shortcuts
    Write-Log $OutputBox 'Install completed.'
}

function Uninstall-UploadPicker {
    param([System.Windows.Forms.TextBox]$OutputBox)
    $confirm = [System.Windows.Forms.MessageBox]::Show('`.venv` と `data` を削除します。続行しますか？', 'UploadPicker', [System.Windows.Forms.MessageBoxButtons]::YesNo)
    if ($confirm -ne [System.Windows.Forms.DialogResult]::Yes) {
        return
    }
    $paths = @(
        (Join-Path $ProjectRoot '.venv'),
        (Join-Path $ProjectRoot 'data')
    )
    foreach ($path in $paths) {
        if (Test-Path $path) {
            Remove-Item -Path $path -Recurse -Force
            Write-Log $OutputBox "Removed: $path"
        }
    }
    foreach ($shortcut in @($DesktopShortcut, $StartMenuShortcut)) {
        if (Test-Path $shortcut) {
            Remove-Item $shortcut -Force
            Write-Log $OutputBox "Removed shortcut: $shortcut"
        }
    }
    if (Test-Path $StartMenuDir) {
        Remove-Item $StartMenuDir -Force
    }
    Write-Log $OutputBox 'Uninstall completed.'
}

function Invoke-ActionDirect {
    param([string]$RequestedAction)
    $buffer = New-Object System.Windows.Forms.TextBox
    switch ($RequestedAction.ToLowerInvariant()) {
        'install' {
            Install-UploadPicker -OutputBox $buffer
            return $true
        }
        'launch' {
            Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$LaunchScript`"" -WorkingDirectory $ProjectRoot | Out-Null
            return $true
        }
        'uninstall' {
            Uninstall-UploadPicker -OutputBox $buffer
            return $true
        }
        default {
            return $false
        }
    }
}

if ($Action) {
    try {
        if (Invoke-ActionDirect -RequestedAction $Action) {
            exit 0
        }
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'UploadPicker Error') | Out-Null
        exit 1
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'UploadPicker Setup Wizard'
$form.Size = New-Object System.Drawing.Size(760, 520)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [System.Drawing.Color]::FromArgb(20, 24, 33)
$form.ForeColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Text = 'UploadPicker Setup Wizard'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 20, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(24, 20)
$form.Controls.Add($title)

$desc = New-Object System.Windows.Forms.Label
$desc.Text = 'Install / Launch / Uninstall をまとめたローカル配布用ウィザードです。Python が無い場合は自動導入を試みます。'
$desc.AutoSize = $true
$desc.Location = New-Object System.Drawing.Point(26, 64)
$form.Controls.Add($desc)

$installButton = New-Object System.Windows.Forms.Button
$installButton.Text = 'Install / Repair'
$installButton.Size = New-Object System.Drawing.Size(180, 42)
$installButton.Location = New-Object System.Drawing.Point(26, 108)
$form.Controls.Add($installButton)

$launchButton = New-Object System.Windows.Forms.Button
$launchButton.Text = 'Launch App'
$launchButton.Size = New-Object System.Drawing.Size(180, 42)
$launchButton.Location = New-Object System.Drawing.Point(220, 108)
$form.Controls.Add($launchButton)

$uninstallButton = New-Object System.Windows.Forms.Button
$uninstallButton.Text = 'Uninstall'
$uninstallButton.Size = New-Object System.Drawing.Size(180, 42)
$uninstallButton.Location = New-Object System.Drawing.Point(414, 108)
$form.Controls.Add($uninstallButton)

$outputBox = New-Object System.Windows.Forms.TextBox
$outputBox.Multiline = $true
$outputBox.ScrollBars = 'Vertical'
$outputBox.ReadOnly = $true
$outputBox.BackColor = [System.Drawing.Color]::FromArgb(14, 16, 22)
$outputBox.ForeColor = [System.Drawing.Color]::White
$outputBox.Size = New-Object System.Drawing.Size(690, 300)
$outputBox.Location = New-Object System.Drawing.Point(26, 168)
$form.Controls.Add($outputBox)

$installButton.Add_Click({
    try {
        Install-UploadPicker -OutputBox $outputBox
        [System.Windows.Forms.MessageBox]::Show('Install completed.', 'UploadPicker') | Out-Null
    } catch {
        Write-Log $outputBox $_.Exception.Message
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'UploadPicker Error') | Out-Null
    }
})

$launchButton.Add_Click({
    try {
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$LaunchScript`"" -WorkingDirectory $ProjectRoot | Out-Null
        Write-Log $outputBox 'Launch requested.'
    } catch {
        Write-Log $outputBox $_.Exception.Message
    }
})

$uninstallButton.Add_Click({
    try {
        Uninstall-UploadPicker -OutputBox $outputBox
        [System.Windows.Forms.MessageBox]::Show('Uninstall completed.', 'UploadPicker') | Out-Null
    } catch {
        Write-Log $outputBox $_.Exception.Message
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'UploadPicker Error') | Out-Null
    }
})

[void]$form.ShowDialog()
