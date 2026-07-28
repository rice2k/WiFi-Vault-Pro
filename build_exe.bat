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
%PY% -m PyInstaller --noconfirm --onefile --windowed --name "WiFiVaultPro_Rice2k" wifi_vault_pro.py

echo.
echo Build complete. Look in the dist folder for WiFiVaultPro_Rice2k.exe.
pause
