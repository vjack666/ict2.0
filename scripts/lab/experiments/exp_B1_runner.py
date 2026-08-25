#!/usr/bin/env python3
"""MICRO-AGENTE B1 — BASELINE LTF (control de B2-B5).

Reutiliza EXACTAMENTE el protocolo de exp_agentA_runner.py (que replica el
experimento base exp_sequential_expectancy_depth4_lite.py bajo el contrato
A1): mismo motor run_sequential(structure_mode="lite"), mismo SL/TP
estructural (defensa pareja de 2 terminos: min(mecha sweep, swing roto)-buffer),
TP measured_projection, horizonte 200, bootstrap 2000 seed 42, Wilson 95%,
tie_policy=pessimistic, baseline FVG-random con defensa pareja (mecha de sweep
SIMULADA muestreada de la MISMA distribucion del tratamiento).

B1 = control LTF SIN contexto HTF (depth>=4, H1, 2019-2024). NO modifica el
motor ni el script base; solo importa sus funciones de protocolo.

Salida: reports/audits/EXP_B1_raw.json + reports/audits/EXP_B1_audit.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reutiliza el protocolo A1 (paired defense) ya verificado por otros agentes.
from exp_agentA_runner import (  # type: ignore
    BASELINE_SEED,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CODE_COMMIT,
    HORIZON_BARS,
    MIN_N_GATE,
    PAIRING_SEED,
    SL_BUFFER,
    SWING_LEFT,
    WARMUP_BARS,
    dataset_record,
    mechanical_verdict,
    run_depth_experiment,
)

REPORT_DIR = ROOT / "reports" / "audits"
RAW_PATH = REPORT_DIR / "EXP_B1_raw.json"
AUDIT_PATH = REPORT_DIR / "EXP_B1_audit.json"

RANGE_START = "2019-01-01"
RANGE_END = "2024-12-31"
DEPTH_MIN = 4
TF = "H1"
SRC_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv"
SRC_PATH = ROOT / SRC_REL
CANONICAL_HASH = "2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_slice() -> pd.DataFrame:
    df = pd.read_csv(SRC_PATH)
    ts = pd.to_datetime(df["time"])
    mask = (ts >= RANGE_START) & (ts <= RANGE_END + " 23:59:59")
    return df.loc[mask].sort_values("time").reset_index(drop=True)


def raw_block(m: dict) -> dict:
    ci = (m.get("bootstrap") or {}).get("mean_r_ci")
    return {
        "n_closed": m.get("n_closed"),
        "n_trades": m.get("n_trades"),
        "n_open": m.get("n_open"),
        "mean_R": m.get("mean_r"),
        "median_R": m.get("median_r"),
        "win_rate": m.get("win_rate"),
        "profit_factor": m.get("profit_factor"),
        "expectancy": m.get("expectancy"),
        "drawdown": m.get("drawdown"),
        "wilson_95": m.get("win_rate_wilson95"),
        "bootstrap_ci_95": ci,
    }


def main() -> None:
    ds_hash = sha256_file(SRC_PATH)
    assert ds_hash == CANONICAL_HASH, f"dataset hash mismatch: {ds_hash}"

    slice_df = load_slice()
    n_bars = len(slice_df)

    # --- run_sequential una sola vez, depth>=4, defensa pareja (protocolo A1) ---
    result = run_depth_experiment(slice_df.copy(), DEPTH_MIN, paired=True, tf_label=TF)
    m_treat = result["treatment"]
    m_base = result["baseline"]

    # ---- RAW (sin interpretacion) ----
    raw = {
        "schema_version": "1.0",
        "experiment": "EXP_B1",
        "role": "BASELINE_LTF_CONTROL (control de B2-B5)",
        "hypothesis": (
            "H_B1: EURUSD H1 depth>=4, defensa pareja (SL 2 terminos), SIN contexto HTF, "
            "bajo protocolo A1. Metrica primaria: expectancy (mean_R). Gate: n_closed>=30. "
            "Este es el control que usaran B2-B5 para medir delta incremental."
        ),
        "dataset": dataset_record(
            "csv", SRC_REL, n_bars, ds_hash, True, TF,
            "Dataset canonico H1 2019-2024; control LTF sin HTF.",
        ),
        "dataset_hash": ds_hash,
        "code_commit": CODE_COMMIT,
        "config": {
            "structure_mode": "lite",
            "max_active_chains": 4096,
            "swing_left": SWING_LEFT,
            "depth_min": DEPTH_MIN,
            "anchor": "STRUCTURE_bar_close (depth>=4)",
            "sl_rule": "min(sweep_wick, broken_swing)-buffer (defensa pareja, 2 terminos)",
            "tp_rule": "measured_projection (fallback sancionado)",
            "sl_buffer": SL_BUFFER,
            "horizon_bars": HORIZON_BARS,
            "tie_policy": "pessimistic",
            "warmup_bars": WARMUP_BARS,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
            "baseline_seed": BASELINE_SEED,
            "pairing_seed": PAIRING_SEED,
            "paired_sweep_defense": True,
            "htf_context": False,
        },
        "fecha": datetime.now(timezone.utc).isoformat(),
        "treatment": raw_block(m_treat),
        "baseline": raw_block(m_base),
        "control_reference": {
            "expectancy_treatment": m_treat.get("mean_r"),
            "expectancy_baseline": m_base.get("mean_r"),
            "win_rate_treatment": m_treat.get("win_rate"),
            "win_rate_baseline": m_base.get("win_rate"),
            "delta_expectancy_treatment_minus_baseline": (
                round(m_treat["mean_r"] - m_base["mean_r"], 4)
                if m_treat.get("mean_r") is not None and m_base.get("mean_r") is not None
                else None
            ),
            "delta_win_rate_treatment_minus_baseline": result.get("delta_win_rate"),
        },
        "motor_summary": result["motor_summary"],
        "chains_depth_ge4": result["chains_depth_ge"],
    }

    # ---- AUDIT (gate mecanico) ----
    gate, _ = mechanical_verdict(m_treat)
    n_closed = m_treat.get("n_closed") or 0
    ci = (m_treat.get("bootstrap") or {}).get("mean_r_ci")
    ci_lower_gt_0 = bool(ci and len(ci) == 2 and ci[0] > 0)
    if not (n_closed >= MIN_N_GATE):
        verdict = "BLOCKED"
    elif (m_treat.get("mean_r") or 0) > 0 and ci_lower_gt_0:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    audit = {
        "schema_version": "1.0",
        "experiment": "EXP_B1",
        "role": "BASELINE_LTF_CONTROL (control de B2-B5)",
        "code_commit": CODE_COMMIT,
        "date": datetime.now(timezone.utc).isoformat(),
        "gate": {
            "n_ge_30": bool(gate["n_ge_30"]),
            "expectancy_gt_0": bool(gate["expectancy_gt_0"]),
            "ci_lower_gt_0": bool(gate["ci_lower_gt_0"]),
        },
        "protocol": {
            "leakage_check": (
                "OK: run_sequential en una sola pasada sobre rango acotado 2019-2024; "
                "PIT-estable DENTRO del rango (deuda FULL-vs-PREFIX afecta al indice HTF del "
                "navigator, NO a este diseno mono-TF de una pasada). Sin contexto HTF en B1."
            ),
            "parameter_change": False,
            "data_integrity": dataset_record(
                "csv", SRC_REL, n_bars, ds_hash, True, TF,
                "Dataset canonico H1 verificado por SHA256; sin modificacion de parametros.",
            ),
        },
        "verdict": verdict,
        "rationale": (
            "mecanico: PASS iff n_closed>=30 AND expectancy(mean_R)>0 AND bootstrap CI95 lower>0; "
            "BLOCKED si n_closed<30; FAIL en otro caso. Calculado por el gate, no por interpretacion."
        ),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(f"WROTE {RAW_PATH}")
    print(f"WROTE {AUDIT_PATH}")
    print(json.dumps({
        "experiment": "EXP_B1",
        "verdict": verdict,
        "treatment": {k: m_treat.get(k) for k in ("n_closed", "n_trades", "win_rate", "mean_r", "expectancy", "profit_factor", "drawdown")},
        "baseline": {k: m_base.get(k) for k in ("n_closed", "n_trades", "win_rate", "mean_r", "expectancy", "profit_factor", "drawdown")},
        "gate": gate,
        "treatment_bootstrap_ci": (m_treat.get("bootstrap") or {}).get("mean_r_ci"),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
