# Nexus AI Studio - start backend + dashboard
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\run.ps1
#
# Stops both services with Ctrl+C.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Sanal ortam yok. Once '.\setup.ps1' calistirin." -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $root

Write-Host "Backend baslatiliyor: http://127.0.0.1:8000" -ForegroundColor Cyan
$backend = Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "uvicorn", "ui.server:app", "--host", "127.0.0.1", "--port", "8000" `
    -PassThru -NoNewWindow

try {
    Start-Sleep -Seconds 3
    Write-Host "Panel baslatiliyor: http://localhost:8501" -ForegroundColor Cyan
    & $venvPython -m streamlit run ui/app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
}
finally {
    if ($backend -and -not $backend.HasExited) {
        Write-Host "Backend durduruluyor..." -ForegroundColor Yellow
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
