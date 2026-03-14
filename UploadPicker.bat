@echo off
set SCRIPT_DIR=%~dp0
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
set /p CHOICE=Select [1-4]: 

if "%CHOICE%"=="1" (
    call "%SCRIPT_DIR%Install UploadPicker.bat"
    goto menu
)
if "%CHOICE%"=="2" (
    call "%SCRIPT_DIR%Start UploadPicker.bat"
    goto menu
)
if "%CHOICE%"=="3" (
    call "%SCRIPT_DIR%Uninstall UploadPicker.bat"
    goto menu
)
if "%CHOICE%"=="4" exit /b 0

echo.
echo Invalid selection.
pause
goto menu
