@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python and add it to PATH.
    pause
    exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
    echo npm was not found. Install Node.js and add it to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create the Python virtual environment.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo Backend dependency installation failed.
    pause
    exit /b 1
)

if not exist "node_modules\vite" (
    call npm install
    if errorlevel 1 (
        echo Frontend dependency installation failed.
        pause
        exit /b 1
    )
)

start "LumenEIOS Backend and API" cmd /k ""%CD%\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
start "LumenEIOS Frontend" cmd /k "cd /d ""%CD%"" && npm run dev"

echo Frontend: http://localhost:3000
echo API docs: http://localhost:8000/api/v1/docs
echo Qwen OCR loads on first use and requires separate CUDA/PyTorch setup. See README.md.
timeout /t 3 >nul
start "" http://localhost:3000
