@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
title UploadPicker

:menu
cls
echo ==============================
echo      UploadPicker Menu
echo ==============================
echo 1. Install / Repair
echo 2. Start App
echo 3. Uninstall
echo 4. Exit
echo.
choice /c 1234 /n /m "Select [1-4]: "
if errorlevel 4 exit /b 0
if errorlevel 3 call :run_action "%SCRIPT_DIR%Uninstall UploadPicker.bat"
if errorlevel 2 call :run_action "%SCRIPT_DIR%Start UploadPicker.bat"
if errorlevel 1 call :run_action "%SCRIPT_DIR%Install UploadPicker.bat"
goto menu

:run_action
call "%~1"
if errorlevel 1 (
    echo.
    echo The selected action ended with an error.
    pause
)
exit /b 0
