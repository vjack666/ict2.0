param(
    [string]$RepoRoot = "",
    [switch]$InstallTestDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

Set-Location $RepoRoot

# Temporal Episode v1 is CPU-only. Prevent accidental CUDA use if another
# package on the machine exposes a GPU.
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:PYTHONUTF8 = "1"

function Resolve-Python {
    try {
        & py -3.11 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return @("py", "-3.11")
        }
    } catch {}

    try {
        & python -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return @("python")
        }
    } catch {}

    throw "No se encontró Python. Instala Python 3.11 x64 o habilita el launcher 'py'."
}

$Python = Resolve-Python

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
    if ($Python.Count -eq 2) {
        & $Python[0] $Python[1] @Args
    } else {
        & $Python[0] @Args
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python terminó con código $LASTEXITCODE"
    }
}

Write-Host "=== Temporal Episode v1 / Windows CPU gate ==="
Invoke-Python "-c" "import sys,platform; print('python=',sys.version); print('platform=',platform.platform()); assert sys.version_info[:2] == (3,11), 'Se requiere Python 3.11 para la certificación'"

if ($InstallTestDeps) {
    Invoke-Python "-m" pip install -r requirements.txt
}

# This path must not require the AI/GPU requirements file.
Invoke-Python "-c" "from pathlib import Path; s=Path(r'scripts/lab/experiments/mt_temporal_episode_materializer.py').read_text(encoding='utf-8').lower(); assert 'tensorflow' not in s and 'torch' not in s and 'cuda' not in s; print('GPU_DEPENDENCY_CHECK=PASS')"

Invoke-Python "-m" compileall -q engine scripts/lab/experiments/mt_temporal_episode_materializer.py tests/test_temporal_episode_materializer.py
Write-Host "COMPILE_WINDOWS_CPU=PASS"

Invoke-Python "-m" pytest tests/test_temporal_episode_materializer.py tests/test_episodes.py -q
Write-Host "TEMPORAL_TESTS_WINDOWS_CPU=PASS"

Write-Host "can_trade=false"
Write-Host "entry_authorized=false"
Write-Host "READY_FOR_TEMPORAL_BASELINE remains NO until real 20-50 episode pilot passes."
