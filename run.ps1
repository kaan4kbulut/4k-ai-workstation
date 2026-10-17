# 4K AI WORKSTATION - Terminal Komut Merkezi
# Streamlit/tarayıcı olmadan doğrudan terminalde çalışır.
#
# Kullanım:
#   powershell -ExecutionPolicy Bypass -File .\run.ps1 [komut]
# Örnek:
#   .\run.ps1
#   .\run.ps1 status
#   .\run.ps1 usage

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Sanal ortam bulunamadi. Once '.\setup.ps1' calistirin." -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $root
& $venvPython "$root\workstation_cli.py" @args
