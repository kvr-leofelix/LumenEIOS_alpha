@echo off
cd /d "%~dp0"

start "LumenEIOS API" cmd /k "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
start "LumenEIOS Web" cmd /k "npm run dev"
