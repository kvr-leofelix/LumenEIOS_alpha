@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_BIN=python"
set "PYTHON_ARGS="
where python >nul 2>nul
if errorlevel 1 set "PYTHON_BIN=missing"
if not "%PYTHON_BIN%"=="missing" python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)" || set "PYTHON_BIN=missing"
if "%PYTHON_BIN%"=="missing" (
    where winget >nul 2>nul || (echo Install Python 3.12 from https://www.python.org/downloads/windows/ and retry.& goto :fail)
    echo Installing Python 3.12...
    winget install --id Python.Python.3.12 --exact --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (echo Python installation failed.& goto :fail)
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
    set "PYTHON_BIN=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if not exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_BIN=py"
        set "PYTHON_ARGS=-3.12"
    )
)
"%PYTHON_BIN%" %PYTHON_ARGS% -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)" || (echo Python 3.12 could not be started.& goto :fail)
where npm >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul || (echo Install Node.js 22 from https://nodejs.org/ and retry.& goto :fail)
    echo Installing Node.js LTS...
    winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (echo Node.js installation failed.& goto :fail)
    set "PATH=%PATH%;%ProgramFiles%\nodejs"
)
where npm >nul 2>nul || (echo npm could not be found after installing Node.js.& goto :fail)
nvidia-smi >nul 2>nul || (echo An NVIDIA GPU driver was not found. Install the driver and check nvidia-smi.& goto :fail)

if not exist ".venv\Scripts\python.exe" (
    "%PYTHON_BIN%" %PYTHON_ARGS% -m venv .venv
    if errorlevel 1 (echo Could not create the Python virtual environment.& goto :fail)
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (echo Updating pip failed.& goto :fail)
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (echo Backend dependency installation failed.& goto :fail)

".venv\Scripts\python.exe" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>nul
if errorlevel 1 (
    echo Installing CUDA-enabled PyTorch for OCR...
    ".venv\Scripts\python.exe" -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
    if errorlevel 1 (echo CUDA PyTorch installation failed. Check your NVIDIA driver and Python version.& goto :fail)
)
".venv\Scripts\python.exe" -m pip install -r backend\requirements-ocr.txt
if errorlevel 1 (echo OCR dependency installation failed.& goto :fail)
".venv\Scripts\python.exe" -c "import torch; assert torch.cuda.is_available(); print('OCR GPU:', torch.cuda.get_device_name(0))"
if errorlevel 1 (echo PyTorch cannot access the NVIDIA GPU.& goto :fail)
set "QWEN_VL_MODEL_ID=Qwen/Qwen2.5-VL-3B-Instruct"
echo Downloading the OCR model. This can take a while on the first run...
".venv\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-VL-3B-Instruct')"
if errorlevel 1 (echo OCR model download failed. Check internet access or HF_TOKEN.& goto :fail)

if not exist "node_modules\vite" (
    call npm ci
    if errorlevel 1 (echo Frontend dependency installation failed.& goto :fail)
)

start "LumenEIOS Backend and API" cmd /k "cd /d ""%CD%"" && ""%CD%\.venv\Scripts\python.exe"" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
start "LumenEIOS Frontend" cmd /k "cd /d ""%CD%"" && npm run dev"

echo Frontend: http://localhost:3000
echo API docs: http://localhost:8000/api/v1/docs
timeout /t 3 >nul
start "" http://localhost:3000
exit /b 0

:fail
pause
exit /b 1
