@echo off
title QuantDesk India - Trading Bot
color 0A

echo =======================================================
echo          STARTING QUANTDESK INDIA WORKSTATION
echo =======================================================

cd /d "%~dp0"

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Creating .venv...
    python -m venv .venv
    IF ERRORLEVEL 1 (
        echo [ERROR] Failed to create virtual environment. Ensure Python 3.10+ is installed and on PATH.
        pause
        exit /b 1
    )
    echo [INFO] Installing required dependencies...
    .\.venv\Scripts\pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
call .\.venv\Scripts\activate

echo [INFO] Opening Quant Terminal in default browser...
start http://127.0.0.1:8000

echo [INFO] Launching Trading Bot application server...
python run.py

pause
