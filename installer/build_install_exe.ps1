$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$PythonLauncher = 'py -3'

& py -3 -m pip install pyinstaller

& py -3 -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name UploadPicker-Install `
    installer\install_wizard.py
