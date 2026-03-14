@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "TARGET_PID=%~1"
set "UPDATE_SCRIPT=%PROJECT_ROOT%installer\update_from_github.ps1"

if not exist "%UPDATE_SCRIPT%" (
    echo Update script was not found.
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%UPDATE_SCRIPT%" -ProjectRoot "%PROJECT_ROOT%" -TargetPid "%TARGET_PID%"
exit /b %errorlevel%
