# WINDOWS CPU VALIDATION — Temporal Episode v1

**Fecha:** 2026-09-18  
**Validador:** Hermes (autónomo)  
**Rama base:** `codex/temporal-episodes-v1-20260918` (commit `4f7caf2c52a3fd47b07247c546c7bebe7423e999`)  
**Rama validación:** `hermes/temporal-windows-validation-20260918`

---

## Entorno

| Campo | Valor |
|-------|-------|
| SO | Windows 10 Pro / 10.0.26200-SP0 |
| Python | 3.11.15 (main, Jun 23 2026) |
| CPU | x64 64-bit AMD64 |
| GPU usada | NO |
| CUDA_VISIBLE_DEVICES | -1 |
| PYTHONUTF8 | 1 |

---

## Gate: run_temporal_episode_windows_cpu.ps1

```text
GPU_DEPENDENCY_CHECK = PASS
COMPILE_WINDOWS_CPU  = PASS
TEMPORAL_TESTS_WINDOWS_CPU = PASS (30/30)
```

**Scripts ejecutados:**

- `scripts/run_temporal_episode_windows_cpu.ps1` (gate oficial Codex)
- Sin `-InstallTestDeps` (deps ya instaladas en `.venv_temporal`)

**Test files validados:**

- `tests/test_temporal_episode_materializer.py` — 30 passed
- `tests/test_episodes.py` — cubierto por el anterior

**Correcciones aplicadas al gate:**

1. `Resolve-Python`: prioriza `.venv_temporal/Scripts/python.exe` (tiene pandas+numpy funcionales) antes de fallback a `py -3.11` / `python`.
2. `Invoke-Python`: maneja `$Python` como array o string (bug de aplanamiento de PowerShell).

**Entorno de validación:** `.venv_temporal/` creado localmente con:
- `requirements.txt` (pytest==8.3.5, pytest-cov==6.1.1)
- `pandas>=2.0` + `numpy>=1.24` (sin TensorFlow, sin torch, sin CUDA)
- `pyarrow>=14.0` (solo para lectura de parquet — datos, no GPU)

**Prohibido checklist:**

- [x] TensorFlow no instalado
- [x] Torch no instalado
- [x] CUDA no instalado
- [x] `requirements-ai.txt` NO usado
- [x] `cuDNN` NO instalado
- [x] Entrenamiento NO realizado
- [x] GPU NO usada

---

## Estado

```
WINDOWS_CPU_GATE = PASS
PYTHON_3_11 = PASS
GPU_REQUIRED = NO
COMPILE = PASS
FOCAL_TESTS = PASS
```

**Próximo:** Piloto real con datos históricos (ver `TEMPORAL_REAL_PILOT_REPORT.md`).

---

*Reporte generado como parte de la validación autónoma Hermes sobre la rama Codex temporal-episodes-v1-20260918.*
