@echo off
setlocal enabledelayedexpansion
title 4K AI WORKSTATION - Otonom Terminal Komut Merkezi
cd /d "%~dp0"

echo ================================================================================
echo           🚀 4K AI WORKSTATION - OTONOM TERMINAL KOMUT MERKEZI
echo ================================================================================

:: 1. Mevcut klasordeki .venv python kontrolu
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto :RUN
)

:: 2. Sistem python kontrolu
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [*] Sistem Python bulundu, sanal ortam kontrol ediliyor...
    python -m venv "%~dp0.venv" >nul 2>&1
    if exist "%~dp0.venv\Scripts\python.exe" (
        set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
        echo [*] Gerekli paketler kuruluyor, lutfen bekleyin...
        "%PYTHON_EXE%" -m pip install -r "%~dp0requirements.txt" --quiet >nul 2>&1
        goto :RUN
    )
)

:: 3. Python yoksa otomatik winget ile kurmayı dene
echo [!] Bu bilgisayarda Python tespit edilemedi.
echo [*] Otomatik kurulum baslatiliyor (Windows Paket Yoneticisi)...
winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [+] Python basariyla kuruldu! Lutfen bu dosyayi tekrar calistirin.
    pause
    exit /b 0
)

echo [X] Python bulunamadi. Lutfen python.org adresinden Python kurun.
pause
exit /b 1

:RUN
"%PYTHON_EXE%" "%~dp0workstation_cli.py" %*
