$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath (Join-Path $root "backtest\viewer")
Write-Host "Iniciando visor scanner local..."
Start-Process "C:\Python314\python.exe" -ArgumentList (Join-Path $root "scripts\live_scanner_http.py")
Start-Process "http://127.0.0.1:4173/"
npm run dev -- --host 127.0.0.1 --port 4173
