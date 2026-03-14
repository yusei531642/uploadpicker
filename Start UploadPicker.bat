@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo UploadPicker is not installed yet.
    echo Run "Install UploadPicker.bat" first.
    pause
    exit /b 1
)

pushd "%PROJECT_ROOT%"
start "UploadPicker Server" "%PYTHON_EXE%" -m app.runner
timeout /t 3 >nul
start "" http://127.0.0.1:8000
popd
endlocal
