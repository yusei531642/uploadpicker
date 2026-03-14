@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "VENV_DIR=%PROJECT_ROOT%.venv"
set "PYTHON_BOOTSTRAP_EXE="
set "PYTHON_BOOTSTRAP_ARGS="
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "ENV_EXAMPLE=%PROJECT_ROOT%.env.example"
set "ENV_FILE=%PROJECT_ROOT%.env"
set "START_MENU_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\UploadPicker"
set "DESKTOP_MENU=%USERPROFILE%\Desktop\UploadPicker.bat"
set "DESKTOP_START=%USERPROFILE%\Desktop\Start UploadPicker.bat"
set "DESKTOP_UNINSTALL=%USERPROFILE%\Desktop\Uninstall UploadPicker.bat"
set "MENU_MENU=%START_MENU_DIR%\UploadPicker.bat"
set "MENU_START=%START_MENU_DIR%\Start UploadPicker.bat"
set "MENU_UNINSTALL=%START_MENU_DIR%\Uninstall UploadPicker.bat"

where py >nul 2>nul
if not errorlevel 1 goto use_py_launcher

where python >nul 2>nul
if not errorlevel 1 goto use_python

echo Python was not found. Installing Python 3.11 via winget...
winget install --exact --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo Failed to install Python.
    pause
    exit /b 1
)
set "PYTHON_BOOTSTRAP_EXE=py"
set "PYTHON_BOOTSTRAP_ARGS=-3.11"
goto python_ready

:use_py_launcher
set "PYTHON_BOOTSTRAP_EXE=py"
set "PYTHON_BOOTSTRAP_ARGS=-3.11"
py -3.11 --version >nul 2>nul
if errorlevel 1 set "PYTHON_BOOTSTRAP_ARGS=-3"
goto python_ready

:use_python
set "PYTHON_BOOTSTRAP_EXE=python"
set "PYTHON_BOOTSTRAP_ARGS="

:python_ready

echo Using Python command: %PYTHON_BOOTSTRAP_EXE% %PYTHON_BOOTSTRAP_ARGS%

if not exist "%VENV_DIR%" (
    "%PYTHON_BOOTSTRAP_EXE%" %PYTHON_BOOTSTRAP_ARGS% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

if exist "%ENV_EXAMPLE%" if not exist "%ENV_FILE%" copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul

"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

pushd "%PROJECT_ROOT%"
"%PYTHON_EXE%" -m pip install -e .
popd
if errorlevel 1 (
    echo Failed to install UploadPicker.
    pause
    exit /b 1
)

if not exist "%START_MENU_DIR%" mkdir "%START_MENU_DIR%"

>"%DESKTOP_MENU%" echo @echo off
>>"%DESKTOP_MENU%" echo call "%PROJECT_ROOT%UploadPicker.bat"
>"%DESKTOP_START%" echo @echo off
>>"%DESKTOP_START%" echo call "%PROJECT_ROOT%Start UploadPicker.bat"
>"%DESKTOP_UNINSTALL%" echo @echo off
>>"%DESKTOP_UNINSTALL%" echo call "%PROJECT_ROOT%Uninstall UploadPicker.bat"
>"%MENU_MENU%" echo @echo off
>>"%MENU_MENU%" echo call "%PROJECT_ROOT%UploadPicker.bat"
>"%MENU_START%" echo @echo off
>>"%MENU_START%" echo call "%PROJECT_ROOT%Start UploadPicker.bat"
>"%MENU_UNINSTALL%" echo @echo off
>>"%MENU_UNINSTALL%" echo call "%PROJECT_ROOT%Uninstall UploadPicker.bat"

echo Install completed.
pause
endlocal
