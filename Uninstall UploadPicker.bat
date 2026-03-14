@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "START_MENU_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\UploadPicker"

echo This will remove .venv, data, and generated shortcuts.
set /p CONFIRM=Continue? [y/N]: 
if /I not "%CONFIRM%"=="Y" exit /b 0

if exist "%PROJECT_ROOT%.venv" rmdir /s /q "%PROJECT_ROOT%.venv"
if exist "%PROJECT_ROOT%data" rmdir /s /q "%PROJECT_ROOT%data"
if exist "%USERPROFILE%\Desktop\UploadPicker.bat" del /f /q "%USERPROFILE%\Desktop\UploadPicker.bat"
if exist "%USERPROFILE%\Desktop\Install UploadPicker.bat" del /f /q "%USERPROFILE%\Desktop\Install UploadPicker.bat"
if exist "%USERPROFILE%\Desktop\Start UploadPicker.bat" del /f /q "%USERPROFILE%\Desktop\Start UploadPicker.bat"
if exist "%USERPROFILE%\Desktop\Uninstall UploadPicker.bat" del /f /q "%USERPROFILE%\Desktop\Uninstall UploadPicker.bat"
if exist "%START_MENU_DIR%\UploadPicker.bat" del /f /q "%START_MENU_DIR%\UploadPicker.bat"
if exist "%START_MENU_DIR%\Install UploadPicker.bat" del /f /q "%START_MENU_DIR%\Install UploadPicker.bat"
if exist "%START_MENU_DIR%\Start UploadPicker.bat" del /f /q "%START_MENU_DIR%\Start UploadPicker.bat"
if exist "%START_MENU_DIR%\Uninstall UploadPicker.bat" del /f /q "%START_MENU_DIR%\Uninstall UploadPicker.bat"
if exist "%START_MENU_DIR%" rmdir /s /q "%START_MENU_DIR%"

echo Uninstall completed.
pause
endlocal
