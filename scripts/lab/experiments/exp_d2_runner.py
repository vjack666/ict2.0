#!/usr/bin/env python3
"""D2 — réplica temporal OOS de EXP_A1.

Replica el protocolo congelado del runner A1 sobre la era 2006-01-01 a
2018-12-31. No modifica parámetros, no usa A1 para ajustar nada y escribe un
par de artefactos audit/raw separado en current_batch.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lab.experiments import exp_agentA_runner as protocol

RANGE_START = "2006-01-01"
RANGE_END = "2018-12-31"
SRC_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv"
OUT_DIR = ROOT / "reports/audits/experiments/current_batch"


def sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    started = time.time()
    protocol.RANGE_START = RANGE_START
    protocol.RANGE_END = RANGE_END
    src = ROOT / SRC_REL
    df = protocol.load_slice_csv(src)
    print(f"D2: bars={len(df)} range={RANGE_START}..{RANGE_END}", flush=True)
    result = protocol.run_depth_experiment(
        df, depth_min=4, paired=True, tf_label="H1"
    )
    metrics = result["treatment"]
    gate, passed = protocol.mechanical_verdict(metrics)
    verdict = "PASS" if passed else ("BLOCKED" if (metrics.get("n_closed") or 0) < protocol.MIN_N_GATE else "FAIL")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    now = datetime.now(timezone.utc).isoformat()
    dataset = {
        "symbol": "EURUSD",
        "exec_tf": "H1",
        "source": SRC_REL,
        "range_start": RANGE_START,
        "range_end": RANGE_END,
        "bars": len(df),
        "dataset_hash": sha256(src),
        "is_canonical": True,
    }
    raw = {
        "schema_version": "1.0",
        "experiment": "EXP_D2",
        "component_isolated": "Temporal OOS replication of EXP_A1",
        "status": "EXECUTED",
        "pre_registration": "docs/experimentos/EXP_B_DESIGN.md#d2",
        "code_commit": head,
        "generated_at": now,
        "dataset": dataset,
        "config": {
            "protocol_source": "scripts/lab/experiments/exp_agentA_runner.py",
            "structure_mode": "lite",
            "max_active_chains": 4096,
            "depth_min": 4,
            "sl_rule": "min(sweep_wick,broken_swing)-buffer",
            "tp_rule": "measured_projection (fallback sancionado)",
            "horizon_bars": protocol.HORIZON_BARS,
            "sl_buffer": protocol.SL_BUFFER,
            "tie_policy": "pessimistic",
            "warmup_bars": protocol.WARMUP_BARS,
            "bootstrap": {"resamples": protocol.BOOTSTRAP_RESAMPLES, "seed": protocol.BOOTSTRAP_SEED, "cluster": "chain_id"},
            "baseline_seed": protocol.BASELINE_SEED,
            "pairing_seed": protocol.PAIRING_SEED,
            "parameter_change": False,
        },
        "motor_summary": result["motor_summary"],
        "chains_depth_ge": result["chains_depth_ge"],
        "treatment": result["treatment"],
        "baseline": result["baseline"],
        "delta_win_rate": result["delta_win_rate"],
        "delta_mean_r": result["delta_mean_r"],
        "n_treatment": result["n_treatment"],
        "n_baseline": result["n_baseline"],
        "paired": result["paired"],
        "n_paired_offsets": result["n_paired_offsets"],
        "elapsed_s": round(time.time() - started, 2),
        "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
    }
    audit = {
        "schema_version": "1.0",
        "experiment": "EXP_D2",
        "component_isolated": "Temporal OOS replication of EXP_A1",
        "code_commit": head,
        "generated_at": now,
        "pre_registration": "docs/experimentos/EXP_B_DESIGN.md#d2",
        "gate": gate,
        "protocol": {
            "leakage_check": "OK: era 2006-2018 is disjoint from A1 2019-2024; single-pass range execution",
            "parameter_change": False,
            "data_integrity": dataset,
        },
        "verdict": verdict,
        "rationale": "mecánico: PASS iff n_closed>=30 AND mean_r>0 AND bootstrap CI95 lower>0.",
        "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "EXP_D2_raw.json").write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    (OUT_DIR / "EXP_D2_audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"experiment": "EXP_D2", "verdict": verdict, "gate": gate, "n_closed": metrics.get("n_closed"), "mean_r": metrics.get("mean_r"), "ci": metrics.get("bootstrap", {}).get("mean_r_ci"), "elapsed_s": raw["elapsed_s"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
