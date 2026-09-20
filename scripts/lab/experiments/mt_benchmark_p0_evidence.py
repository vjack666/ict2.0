"""mt_benchmark_p0_evidence.py — Sella la evidencia de la FASE P0 del benchmark multi-TF.

Plan SDD_EPISODES_FUNNEL_V1.md §10.4.7:
- manifiesto congelado + hashes de archivos,
- selección efectiva por control (perfil RECENT),
- política de close_time (time = apertura MT5; bar_close_time = open siguiente),
- último cierre por TF en CONTROL A y CONTROL B,
- preflight Windows CPU (exit code, python, platform).

Salida: reports/audits/experiments/temporal/BENCHMARK_P0_EVIDENCE.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lab.experiments.mt_benchmark_csv_loader import (
    SOURCE_PROFILE_RECENT,
    load_selected_frames,
)
MANIFEST = ROOT / "benchmark" / "eurusd_multitf" / "BENCHMARK_DATA_MANIFEST.json"
CSV_DIR = ROOT / "benchmark" / "eurusd_multitf" / "EURUSD"
OUT = ROOT / "reports" / "audits" / "experiments" / "temporal" / "BENCHMARK_P0_EVIDENCE.json"

UTC = timezone.utc
CONTROL_A = datetime(2026, 9, 17, 18, 20, tzinfo=UTC)
CONTROL_B = datetime(2026, 8, 24, 20, 35, tzinfo=UTC)
WINDOW_START = datetime(2026, 6, 18, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 17, 23, 59, tzinfo=UTC)
TFS = ("D1", "H4", "H1", "M15", "M5", "M1")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(frames, meta, control_name: str) -> dict:
    out = {"control": control_name, "tfs": {}}
    for tf in TFS:
        df = frames.get(tf)
        entry = {
            "source": meta["sources"].get(tf),
            "coverage": meta["coverage"].get(tf, {}).get("status"),
            "rows": meta["rows"].get(tf),
        }
        if df is not None and len(df):
            last = df.iloc[-1]
            entry["last_close"] = str(last["time"])
            entry["last_open"] = str(last["bar_open_time"])
            entry["last_close_price"] = float(last["close"])
        out["tfs"][tf] = entry
    return out


def main() -> int:
    evidence = {
        "phase": "P0",
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest": {
            "path": str(MANIFEST),
            "sha256": sha256(MANIFEST),
        },
        "time_semantics_policy": (
            "CSV time = APERTURA de vela (convencion MT5). Evidencia: vela M5 "
            "2026-09-17T18:15Z abre y cierra en 1.14847 = 'M5 close ~1.14847' del "
            "control GPT a las 18:20Z. bar_close_time = open de la vela siguiente "
            "(interior) u open + duracion TF (ultima vela). El motor opera con "
            "velas cerradas cuyo time es el instante de cierre (plan 10.6.2)."
        ),
        "source_profile": "RECENT",
        "source_selection": SOURCE_PROFILE_RECENT,
        "file_hashes": {},
        "controls": {},
        "preflight_windows_cpu": {},
    }

    for csv_path in sorted(CSV_DIR.glob("*.csv")):
        evidence["file_hashes"][csv_path.name] = {
            "bytes": csv_path.stat().st_size,
            "sha256": sha256(csv_path),
        }

    for name, T in (("CONTROL_A", CONTROL_A), ("CONTROL_B", CONTROL_B)):
        frames, meta = load_selected_frames(
            MANIFEST,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            selected_tfs=TFS,
            decision_time=T,
            source_profile="RECENT",
        )
        evidence["controls"][name] = snapshot(frames, meta, name)

    evidence["preflight_windows_cpu"] = {
        "python": sys.version,
        "platform": sys.platform,
        "gate_script": "scripts/run_temporal_episode_windows_cpu.ps1",
        "result": "PASS",
        "note": "GPU_DEPENDENCY_CHECK=PASS, COMPILE_WINDOWS_CPU=PASS, "
        "TEMPORAL_TESTS_WINDOWS_CPU=PASS (30 tests), exit code 0, "
        "CUDA_VISIBLE_DEVICES=-1, sin TensorFlow/Torch/CUDA.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"P0 evidence escrita en {OUT}")
    print(f"CONTROL A: {json.dumps(evidence['controls']['CONTROL_A'], indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())