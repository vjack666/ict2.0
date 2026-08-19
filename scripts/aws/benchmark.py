"""benchmark.py — Linea base ict2.0 (tu PC) para comparar con EC2.

Mide, por evidencia, los tiempos de los cuellos reales:
  - A0-A9 (audit stack)
  - Funnel 20Y
  - AHF temporal (lo que acabamos de armar: tna_audit_runner.py)
  - EXP-004b (walkforward) si existe

Registra: tiempo, CPU logica, RAM total, procesos usados (1, luego todos los cores).

Uso:
  ict2.0> .venv/Scripts/python.exe scripts/aws/benchmark.py
Salida: reports/audits/benchmark_<host>.json
"""
from __future__ import annotations
import datetime as _dt
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import psutil  # type: ignore

OUT = ROOT / "reports" / "audits"


def _host_tag() -> str:
    return platform.node().split(".")[0].lower() or "pc"


def _run(name: str, cmd: list[str], n_proc: int | None = None) -> dict:
    env = dict(os.environ)
    # asegurar que el repo raiz este en sys.path para `import engine`
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    if n_proc:
        env["ICT_BENCH_PROC"] = str(n_proc)
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
        rc = r.returncode
        tail = (r.stdout or r.stderr)[-800:]
    except subprocess.TimeoutExpired:
        rc, tail = -1, "TIMEOUT(1800s)"
    dt = time.perf_counter() - t0
    return {"name": name, "rc": rc, "seconds": round(dt, 2), "n_proc": n_proc, "tail": tail}


def main() -> dict:
    py = str(ROOT / ".venv" / "Scripts" / "python.exe") if (ROOT / ".venv").exists() \
        else sys.executable
    jobs = []
    # A0-A9 funnel stack
    jobs.append(("A0_A9", [py, "-m", "audits.codigo.bootstrap"]))
    # Funnel 20Y (si existe el runner de funnel)
    funnel = ROOT / "audits" / "codigo" / "mtf_seq_funnel.py"
    if funnel.exists():
        jobs.append(("FUNNEL_20Y", [py, str(funnel)]))
    # AHF temporal (lo que armanos)
    tna = ROOT / "scripts" / "tna_audit_runner.py"
    if tna.exists():
        jobs.append(("AHF_TEMPORAL", [py, str(tna)]))

    results = []
    for name, cmd in jobs:
        # 1 core
        r1 = _run(f"{name}_1core", cmd, n_proc=1)
        results.append(r1)
        # todos los cores
        rN = _run(f"{name}_{psutil.cpu_count()}", cmd, n_proc=psutil.cpu_count())
        results.append(rN)

    report = {
        "host": _host_tag(),
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "cpu_logical": psutil.cpu_count(),
        "cpu_physical": psutil.cpu_count(logical=False),
        "ram_gb": round(psutil.virtual_memory().total / 1e9, 1),
        "python": sys.version.split()[0],
        "results": results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"benchmark_{_host_tag()}.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("host", "cpu_logical", "ram_gb", "results")}, indent=2, default=str))
    print("OUT:", out)
    return report


if __name__ == "__main__":
    main()
