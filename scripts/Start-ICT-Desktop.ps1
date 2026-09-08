$ErrorActionPreference = 'Stop'
$ictRoot = Split-Path -Parent $PSScriptRoot
$ictPython = 'C:\Python314\pythonw.exe'
if (-not (Test-Path -LiteralPath $ictPython)) { throw "No se encontró $ictPython" }
$ictUrl = 'http://127.0.0.1:8790'
try {
    $ictState = Invoke-RestMethod "$ictUrl/api/state" -TimeoutSec 2
    if ($ictState.source -eq 'MT5_LOCAL' -and $ictState.csrf_token) {
        $ictEdge = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
        if (Test-Path -LiteralPath $ictEdge) { Start-Process -FilePath $ictEdge -ArgumentList "--app=$ictUrl", '--window-size=1480,1000' }
        else { Start-Process $ictUrl }
        exit
    }
} catch { }
$ictLauncher = Join-Path $PSScriptRoot 'start_desktop_terminal.py'
Start-Process -FilePath $ictPython -ArgumentList "`"$ictLauncher`" --desktop" -WorkingDirectory $ictRoot -WindowStyle Hidden
