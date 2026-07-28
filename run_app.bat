@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 wifi_vault_pro.py
) else (
    python wifi_vault_pro.py
)

if errorlevel 1 (
    echo.
    echo WiFi Vault Pro did not start. Make sure Python 3 is installed and available on PATH.
    echo Optional: py -3 -m pip install -r requirements.txt
    echo.
    pause
)
