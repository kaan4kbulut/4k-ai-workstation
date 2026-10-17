# 4K AI WORKSTATION - environment setup
# Creates a local virtual environment and installs dependencies.
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Find-Python {
    # 1) `py` launcher
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @{ Exe = $py.Source; Args = @("-3") } }

    # 2) python on PATH
    $p = Get-Command python -ErrorAction SilentlyContinue
    if ($p -and $p.Source -notlike "*WindowsApps*") {
        return @{ Exe = $p.Source; Args = @() }
    }

    # 3) common per-user / machine install locations
    foreach ($candidate in @(
            "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        )) {
        if (Test-Path $candidate) { return @{ Exe = $candidate; Args = @() } }
    }

    throw "Python bulunamadi. Kurun:  winget install --scope user Python.Python.3.14"
}

$python = Find-Python
Write-Host "Python: $($python.Exe) $($python.Args -join ' ')" -ForegroundColor Cyan

if (-not (Test-Path "$root\.venv")) {
    Write-Host "Sanal ortam olusturuluyor (.venv)..." -ForegroundColor Cyan
    & $python.Exe @($python.Args) -m venv "$root\.venv"
}

$venvPython = "$root\.venv\Scripts\python.exe"
Write-Host "Bagimliliklar kuruluyor..." -ForegroundColor Cyan
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r "$root\requirements.txt"

Write-Host "Testler calistiriliyor..." -ForegroundColor Cyan
& $venvPython -m unittest discover -s "$root\tests"

Write-Host ""
Write-Host "Hazir. Sunucuyu baslatmak icin:  .\run.ps1" -ForegroundColor Green
