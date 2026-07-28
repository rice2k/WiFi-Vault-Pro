@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set PY=py -3
) else (
    set PY=python
)

%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt

echo.
echo Optional dependencies installed. Reopen WiFi Vault Pro to use QR image display and QR PNG download.
pause
