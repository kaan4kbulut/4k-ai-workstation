@echo off
setlocal enabledelayedexpansion
title 4K AI WORKSTATION - Tasinabilir Kurulum
cd /d "%~dp0"

echo ================================================================================
echo           📦 4K AI WORKSTATION - TEK TIKLA OTOMATIK KURULUM
echo ================================================================================
echo [*] Kurulum baslatiliyor...

:: Python kontrolu
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python bulunamadi, otomatik indiriliyor ve kuruluyor...
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
)

:: Sanal ortam olustur
if not exist "%~dp0.venv" (
    echo [*] Izole calisma ortami (.venv) olusturuluyor...
    python -m venv "%~dp0.venv"
)

:: Paketleri kur
echo [*] Gerekli paketler yukleniyor (FastAPI, Uvicorn, HTTPX, SQLite)...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" --quiet

:: Masaustune kisayol olustur (PowerShell ile)
echo [*] Masaustune 4K AI Workstation kisayolu ekleniyor...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), '4K_AI_Workstation.lnk')); $s.TargetPath = '%~dp04K_AI_Workstation.bat'; $s.WorkingDirectory = '%~dp0'; $s.Save()" >nul 2>&1

echo ================================================================================
echo 🎉 KURULUM BASARIYLA TAMAMLANDI!
echo 👉 Masaustundeki '4K_AI_Workstation' kisayoluna cift tiklayarak baslatabilirsiniz.
echo ================================================================================
pause
