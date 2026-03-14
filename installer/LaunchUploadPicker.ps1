$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$PidFile = Join-Path $ProjectRoot 'data\uploadpicker.pid'
$Url = 'http://127.0.0.1:8000'

if (-not (Test-Path $PythonExe)) {
    [System.Windows.Forms.MessageBox]::Show('先に UploadPicker のセットアップを実行してください。', 'UploadPicker') | Out-Null
    exit 1
}

if (-not (Test-Path (Split-Path $PidFile -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $PidFile -Parent) -Force | Out-Null
}

if (Test-Path $PidFile) {
    try {
        $ExistingPid = Get-Content $PidFile | Select-Object -First 1
        if ($ExistingPid) {
            $RunningProcess = Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue
            if ($RunningProcess) {
                Start-Process $Url | Out-Null
                exit 0
            }
        }
    } catch {
    }
}

$ServerArgs = '-m app.runner'
$Process = Start-Process -FilePath $PythonExe -ArgumentList $ServerArgs -WorkingDirectory $ProjectRoot -WindowStyle Normal -PassThru
Set-Content -Path $PidFile -Value $Process.Id
Start-Sleep -Seconds 3
Start-Process $Url | Out-Null
