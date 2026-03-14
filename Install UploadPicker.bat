@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "VENV_DIR=%PROJECT_ROOT%.venv"
set "NO_PAUSE="
set "PYTHON_BOOTSTRAP_EXE="
set "PYTHON_BOOTSTRAP_ARGS="
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTORCH_TORCH_VERSION=2.9.1"
set "PYTORCH_TORCHVISION_VERSION=0.24.1"
set "PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128"
set "PYTORCH_PROFILE_NAME=CUDA 12.8"
set "NVIDIA_GPU_NAME="
set "ENV_EXAMPLE=%PROJECT_ROOT%.env.example"
set "ENV_FILE=%PROJECT_ROOT%.env"
set "START_MENU_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\UploadPicker"
set "DESKTOP_MENU=%USERPROFILE%\Desktop\UploadPicker.bat"
set "DESKTOP_START=%USERPROFILE%\Desktop\Start UploadPicker.bat"
set "DESKTOP_UNINSTALL=%USERPROFILE%\Desktop\Uninstall UploadPicker.bat"
set "MENU_MENU=%START_MENU_DIR%\UploadPicker.bat"
set "MENU_START=%START_MENU_DIR%\Start UploadPicker.bat"
set "MENU_UNINSTALL=%START_MENU_DIR%\Uninstall UploadPicker.bat"

if /i "%~1"=="--no-pause" (
    set "NO_PAUSE=1"
    shift
)

call :resolve_python
if errorlevel 1 (
    echo Failed to find or install a usable Python runtime.
    call :maybe_pause
    exit /b 1
)

echo Using Python command: %PYTHON_BOOTSTRAP_EXE% %PYTHON_BOOTSTRAP_ARGS%

if not exist "%VENV_DIR%" (
    "%PYTHON_BOOTSTRAP_EXE%" %PYTHON_BOOTSTRAP_ARGS% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        call :maybe_pause
        exit /b 1
    )
)

if not exist "%PYTHON_EXE%" (
    echo Virtual environment was created incompletely.
    echo Missing: %PYTHON_EXE%
    call :maybe_pause
    exit /b 1
)

if exist "%ENV_EXAMPLE%" if not exist "%ENV_FILE%" copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul

"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    call :maybe_pause
    exit /b 1
)

pushd "%PROJECT_ROOT%"
"%PYTHON_EXE%" -m pip install -e .
popd
if errorlevel 1 (
    echo Failed to install UploadPicker.
    call :maybe_pause
    exit /b 1
)

where nvidia-smi >nul 2>nul
if not errorlevel 1 (
    call :configure_pytorch_for_gpu
    echo NVIDIA GPU detected: %NVIDIA_GPU_NAME%
    echo Selected PyTorch profile: %PYTORCH_PROFILE_NAME%
    echo Replacing CPU PyTorch with CUDA-enabled PyTorch runtime...
    "%PYTHON_EXE%" -m pip install --force-reinstall --no-cache-dir torch==%PYTORCH_TORCH_VERSION% torchvision==%PYTORCH_TORCHVISION_VERSION% --index-url %PYTORCH_INDEX_URL%
    if errorlevel 1 (
        echo CUDA-enabled PyTorch install failed. UploadPicker will continue to use CPU.
    )
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
call :maybe_pause
endlocal

goto :eof

:resolve_python
where py >nul 2>nul
if not errorlevel 1 (
    py -0p 2>nul | findstr /i /c:"3.11" >nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP_EXE=py"
        set "PYTHON_BOOTSTRAP_ARGS=-3.11"
        exit /b 0
    )
    py -0p 2>nul | findstr /r /c:" -3\.[0-9]" >nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP_EXE=py"
        set "PYTHON_BOOTSTRAP_ARGS=-3"
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP_EXE=python"
        set "PYTHON_BOOTSTRAP_ARGS="
        exit /b 0
    )
)

echo Python runtime was not found. Installing Python 3.11 via winget...
winget install --exact --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
if errorlevel 1 exit /b 1

where py >nul 2>nul
if not errorlevel 1 (
    py -0p 2>nul | findstr /i /c:"3.11" >nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP_EXE=py"
        set "PYTHON_BOOTSTRAP_ARGS=-3.11"
        exit /b 0
    )
    py -0p 2>nul | findstr /r /c:" -3\.[0-9]" >nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP_EXE=py"
        set "PYTHON_BOOTSTRAP_ARGS=-3"
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP_EXE=python"
        set "PYTHON_BOOTSTRAP_ARGS="
        exit /b 0
    )
)

exit /b 1

:configure_pytorch_for_gpu
set "NVIDIA_GPU_NAME_READ="
set "NVIDIA_GPU_NAME=Unknown NVIDIA GPU"
for /f "usebackq delims=" %%G in (`nvidia-smi --query-gpu=name --format=csv,noheader ^| findstr /r "."`) do (
    if not defined NVIDIA_GPU_NAME_READ (
        set "NVIDIA_GPU_NAME=%%G"
        set "NVIDIA_GPU_NAME_READ=1"
    )
)

set "PYTORCH_TORCH_VERSION=2.9.1"
set "PYTORCH_TORCHVISION_VERSION=0.24.1"
set "PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128"
set "PYTORCH_PROFILE_NAME=CUDA 12.8"

echo %NVIDIA_GPU_NAME% | findstr /i /r /c:"RTX 50[0-9][0-9]" /c:"RTX 60[0-9][0-9]" /c:"Blackwell" >nul
if not errorlevel 1 (
    set "PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu130"
    set "PYTORCH_PROFILE_NAME=CUDA 13.0"
    goto :eof
)

echo %NVIDIA_GPU_NAME% | findstr /i /r /c:"RTX 20[0-9][0-9]" /c:"RTX 30[0-9][0-9]" /c:"RTX 40[0-9][0-9]" /c:"RTX A[0-9]" /c:"RTX [0-9][0-9][0-9][0-9] Ada" /c:"GTX 16[0-9][0-9]" >nul
if not errorlevel 1 (
    set "PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128"
    set "PYTORCH_PROFILE_NAME=CUDA 12.8"
    goto :eof
)

set "PYTORCH_TORCH_VERSION=2.6.0"
set "PYTORCH_TORCHVISION_VERSION=0.21.0"
set "PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu124"
set "PYTORCH_PROFILE_NAME=CUDA 12.4"
goto :eof

:maybe_pause
if defined NO_PAUSE exit /b 0
pause
exit /b 0
