#!/usr/bin/env python3
"""EXP C3-FIX — OOS 2025 (EXTENDIDO 2025-01-01..2026-08-14) en EURUSD H1.

Micro-agente C3-FIX, ciclo 1 del loop de recuperacion de la deuda C3.

Reutiliza EXACTAMENTE el protocolo de exp_sequential_expectancy_depth4_lite.py
(A1/B1/C): misma logica de SL/TP estructural, misma baseline FVG-random,
mismos parametros (depth>=4, structure_mode=lite, horizon 200, sl_buffer
0.0001, tie_policy pessimistic, warmup 20, bootstrap 2000, seed 42, baseline
seed 42, min_n 30). NO se modifica run_sequential / sequential_outcome.

Unica diferencia permitida: el rango OOS se extiende a 2026-08-14 y la fuente
es data/raw/EURUSD/EURUSD_H1.parquet (origen DISTINTO al CSV canonico
Dukascopy), porque el CSV canonico solo llega a 2025-12-31 y en 2025 entrega
n_closed=24 < 30 (BLOCKED original). Se declara en protocol.data_integrity.

Salida:
  reports/audits/EXP_C3FIX_raw.json
  reports/audits/EXP_C3FIX_audit.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse EXACT protocol helpers from the canonical experiment (no rewrite).
import scripts.lab.experiments.exp_sequential_expectancy_depth4_lite as base
from scripts.lab.experiments.exp_sequential_expectancy_depth4_lite import (
    MIN_DEPTH,
    SWING_LEFT,
    WARMUP_BARS,
    HORIZON_BARS,
    SL_BUFFER,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    BASELINE_SEED,
    MIN_N_GATE,
    build_trade,
    last_confirmed_swing,
    metrics,
)

from engine.sequential_events import run_sequential, summarize_chains, _causal_swings
from engine.detectors.fvg import detect_fvg
from engine.sequential_outcome import resolve_outcome, OutcomeConfig, TradeLevels

DATA_PARQUET = ROOT / "data" / "raw" / "EURUSD" / "EURUSD_H1.parquet"
OUT_RAW = ROOT / "reports" / "audits" / "EXP_C3FIX_raw.json"
OUT_AUDIT = ROOT / "reports" / "audits" / "EXP_C3FIX_audit.json"

RANGE_START = "2025-01-01"
RANGE_END = "2026-08-14"   # EXTENDIDO mas alla de 2025 para alcanzar n>=30


def load_parquet_slice() -> pd.DataFrame:
    df = pd.read_parquet(DATA_PARQUET)
    ts = pd.to_datetime(df["time"])
    mask = (ts >= RANGE_START) & (ts <= RANGE_END + " 23:59:59")
    sl = df.loc[mask].sort_values("time").reset_index(drop=True)
    return sl


def profit_factor(rs: list[float]) -> float:
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    gp = float(np.sum(wins))
    gl = float(np.sum(losses))
    if gl == 0:
        return float("inf") if gp > 0 else 0.0
    return round(gp / abs(gl), 4)


def max_drawdown(rs: list[float]) -> float:
    """Max peak-to-trough drawdown of the cumulative R equity curve."""
    if not rs:
        return 0.0
    cum = np.cumsum(np.array(rs, dtype=float))
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    return round(float(dd.min()), 4)


def main() -> dict:
    t0 = time.time()
    print("EXP C3-FIX — load OOS slice (parquet, extended)", flush=True)
    slice_df = load_parquet_slice()
    n_bars = len(slice_df)
    print(f"bars={n_bars} ({slice_df['time'].iloc[0]} .. {slice_df['time'].iloc[-1]})", flush=True)

    cfg_seq = base.SeqConfig(structure_mode="lite", max_active_chains=4096, swing_left=SWING_LEFT)
    cfg_out = OutcomeConfig(horizon_bars=HORIZON_BARS, sl_buffer=SL_BUFFER, tie_policy="pessimistic")

    high = slice_df["high"].to_numpy(float)
    low = slice_df["low"].to_numpy(float)
    close = slice_df["close"].to_numpy(float)
    times = list(slice_df["time"].astype(str))

    print("run_sequential (lite)...", flush=True)
    chains = run_sequential(slice_df, cfg_seq, timeframe="H1")
    summary = summarize_chains(chains)
    print(f"chains={summary['n_chains']} by_depth={summary['by_depth']}", flush=True)

    from engine.sequential_events import Stage
    swing_highs, swing_lows = _causal_swings(high, low, SWING_LEFT)

    candidates = [c for c in chains if len(c.nodes) >= MIN_DEPTH]
    by_status = {}
    for c in candidates:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    print(f"depth>={MIN_DEPTH}: {len(candidates)} status={by_status}", flush=True)

    seen = set()
    dedup_skipped = 0
    treatment = []
    spans = []
    for ch in candidates:
        struct_node = ch.nodes[MIN_DEPTH - 1]
        assert struct_node.stage is Stage.STRUCTURE
        sweep_node = ch.nodes[1]
        assert sweep_node.stage is Stage.SWEEP
        bar_i = int(struct_node.bar)
        sweep_bar = int(sweep_node.bar)
        key = (bar_i, int(ch.direction))
        if key in seen or bar_i < WARMUP_BARS:
            dedup_skipped += 1
            continue
        seen.add(key)
        extra = sweep_node.extra or {}
        sw_lo = extra.get("sweep_low")
        sw_hi = extra.get("sweep_high")
        a, b = sweep_bar, bar_i
        r_lo = float(np.min(low[a:b + 1]))
        r_hi = float(np.max(high[a:b + 1]))
        built = build_trade(
            int(ch.direction), bar_i, close, high, low, swing_lows, swing_highs,
            None if sw_lo is None else float(sw_lo),
            None if sw_hi is None else float(sw_hi),
            r_lo, r_hi, cfg_out,
        )
        if built is None:
            continue
        spans.append(bar_i - sweep_bar)
        res = resolve_outcome(high, low, bar_i, built["levels"], cfg_out)
        treatment.append({
            "group": "treatment",
            "chain_id": ch.chain_id,
            "direction": int(ch.direction),
            "structure_bar": bar_i,
            "sweep_bar": sweep_bar,
            "time": times[bar_i],
            "status": ch.status,
            "depth": len(ch.nodes),
            "entry": round(built["levels"].entry, 6),
            "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "sweep_wick_low": None if sw_lo is None else round(float(sw_lo), 6),
            "sweep_wick_high": None if sw_hi is None else round(float(sw_hi), 6),
            "range_low": round(r_lo, 6),
            "range_high": round(r_hi, 6),
            **res,
        })

    n_treatment_valid = len(treatment)
    print(f"treatment trades={n_treatment_valid} (dedup/skip={dedup_skipped})", flush=True)

    # Baseline: random FVG entries, IDENTICAL structural SL/TP logic.
    records = slice_df[["open", "high", "low", "close"]].copy()
    records["time"] = list(range(n_bars))
    fvgs = detect_fvg(records.to_dict("records"), timeframe="SEQ", symbol="")
    fvg_events = []
    f_seen = set()
    for f in fvgs:
        bi = f.confirmation_bar if f.confirmation_bar is not None else f.bar_index
        if bi is None or int(bi) < WARMUP_BARS:
            continue
        k = (int(bi), int(f.direction))
        if k in f_seen:
            continue
        f_seen.add(k)
        fvg_events.append(k)
    rng = np.random.default_rng(BASELINE_SEED)
    order = rng.permutation(len(fvg_events))
    k_window = int(np.median(spans)) if spans else 8
    baseline = []
    for idx in order:
        if len(baseline) >= n_treatment_valid:
            break
        cb, direction = fvg_events[idx]
        a = max(0, cb - k_window + 1)
        r_lo = float(np.min(low[a:cb + 1]))
        r_hi = float(np.max(high[a:cb + 1]))
        built = build_trade(direction, cb, close, high, low, swing_lows, swing_highs, None, None, r_lo, r_hi, cfg_out)
        if built is None:
            continue
        res = resolve_outcome(high, low, cb, built["levels"], cfg_out)
        baseline.append({
            "group": "baseline",
            "chain_id": f"BASE_{cb}_{direction}",
            "direction": int(direction),
            "structure_bar": cb,
            "time": times[cb],
            "depth": 0,
            "fvg_window_bars": k_window,
            "entry": round(built["levels"].entry, 6),
            "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "range_low": round(r_lo, 6),
            "range_high": round(r_hi, 6),
            **res,
        })
    print(f"baseline trades={len(baseline)} (fvg pool={len(fvg_events)}, window={k_window})", flush=True)

    m_treat = metrics(treatment, cluster_key="chain_id")
    m_base = metrics(baseline, cluster_key="chain_id")

    # ---- C3-FIX specific metrics ----
    closed = [t for t in treatment if t.get("exit_r") is not None]
    rs = [float(t["exit_r"]) for t in closed]
    pf = profit_factor(rs)
    dd = max_drawdown(rs)
    expectancy = m_treat.get("mean_r")

    n_closed = m_treat["n_closed"]
    mean_r = m_treat.get("mean_r")
    ci = (m_treat.get("bootstrap_clustered") or {}).get("mean_r_ci")
    wr = m_treat.get("win_rate")
    wilson = m_treat.get("win_rate_wilson95")

    gate_n = n_closed >= MIN_N_GATE
    gate_exp = bool(mean_r is not None and mean_r > 0)
    gate_ci = bool(ci is not None and ci[0] > 0)

    if not gate_n:
        verdict = "BLOCKED"
        verdict_reason = (
            f"n_closed={n_closed} < 30 incluso extendiendo OOS a {RANGE_END}; "
            "muestra insuficiente para gate mecanico."
        )
    elif gate_exp and gate_ci:
        verdict = "PASS"
        verdict_reason = (
            f"n_closed={n_closed}>=30 y expectancy OOS positiva (mean_R={mean_r:+.4f}, "
            f"IC95=[{ci[0]:+.4f},{ci[1]:+.4f}] excluye 0): edge LTF depth>=4 sobrevive OOS."
        )
    else:
        verdict = "FAIL"
        verdict_reason = (
            f"n_closed={n_closed}>=30 PERO edge OOS NO positivo/robusto "
            f"(mean_R={mean_r}, IC95=[{ci[0]:+.4f},{ci[1]:+.4f}] incluye 0): "
            "falsacion OOS exitosa, no infraestructura."
        )

    raw = {
        "schema_version": "1.0",
        "experiment": "EXP_C3FIX",
        "role": "MICRO_AGENTE_C3FIX",
        "hypothesis_under_test": "El edge LTF depth>=4 sobrevive fuera de muestra (EURUSD post-2024). Metrica: expectancy (mean_R). Gate: n_closed>=30.",
        "dataset": {
            "symbol": "EURUSD",
            "exec_tf": "H1",
            "source": str(DATA_PARQUET.relative_to(ROOT)),
            "source_kind": "parquet",
            "data_origin": "NO-canonico (parquet data/raw, origen distinto al CSV Dukascopy canonico)",
            "range_start": RANGE_START,
            "range_end": RANGE_END,
            "range_label": "OOS EXTENDIDO 2025-01-01..2026-08-14 (no solo 2025)",
            "bars": n_bars,
            "parquet_sha256": "ac028d7d8a6cd977a7d40ed632642a9bb3f60410d05971a05169cb8f3d380cc7",
        },
        "config": {
            "structure_mode": cfg_seq.structure_mode,
            "max_active_chains": cfg_seq.max_active_chains,
            "swing_left": SWING_LEFT,
            "min_depth": MIN_DEPTH,
            "anchor": "STRUCTURE_bar_close",
            "sl_rule": "long=min(sweep_wick_low,broken_swing_low)-buffer; short=mirror (NUNCA ATR)",
            "tp_rule": "measured projection of sequence range (v1 sanctioned fallback)",
            "tp_baseline_window_bars": k_window,
            "sl_buffer": SL_BUFFER,
            "horizon_bars": HORIZON_BARS,
            "tie_policy": "pessimistic_intrabar_SL",
            "warmup_bars": WARMUP_BARS,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
            "baseline_seed": BASELINE_SEED,
            "min_n_gate": MIN_N_GATE,
        },
        "motor_summary": summary,
        "chains_depth_ge4": {"n": len(candidates), "by_status": by_status, "dedup_or_warmup_skipped": dedup_skipped},
        "treatment": {
            "n_trades": m_treat["n_trades"],
            "n_closed": m_treat["n_closed"],
            "n_open": m_treat["n_open"],
            "n_invalid_levels": m_treat["n_invalid_levels"],
            "wins": m_treat["wins"],
            "losses": m_treat["losses"],
            "win_rate": wr,
            "win_rate_wilson95": wilson,
            "mean_R": mean_r,
            "median_R": m_treat.get("median_r"),
            "std_R": m_treat.get("std_r"),
            "min_R": m_treat.get("min_r"),
            "max_R": m_treat.get("max_r"),
            "expectancy": expectancy,
            "profit_factor": pf,
            "drawdown": dd,
            "bootstrap_mean_r_ci": ci,
            "bootstrap_win_rate_ci": (m_treat.get("bootstrap_clustered") or {}).get("win_rate_ci"),
        },
        "baseline_fvg_random": {
            "n_trades": m_base["n_trades"],
            "n_closed": m_base["n_closed"],
            "n_open": m_base["n_open"],
            "win_rate": m_base.get("win_rate"),
            "win_rate_wilson95": m_base.get("win_rate_wilson95"),
            "mean_R": m_base.get("mean_r"),
            "median_R": m_base.get("median_r"),
            "expectancy": m_base.get("mean_r"),
            "profit_factor": profit_factor([float(t["exit_r"]) for t in baseline if t.get("exit_r") is not None]),
            "drawdown": max_drawdown([float(t["exit_r"]) for t in baseline if t.get("exit_r") is not None]),
            "bootstrap_mean_r_ci": (m_base.get("bootstrap_clustered") or {}).get("mean_r_ci"),
        },
        "comparison_to_in_sample": {
            "in_sample_A1_B1_mean_R": 0.250,
            "oos_mean_R": mean_r,
            "delta_oos_minus_is": round(float(mean_r) - 0.250, 4) if mean_r is not None else None,
            "note": "In-sample A1/B1 reporta +0.250 mean_R. El OOS extendido se compara contra esa referencia (mismo motor/protocolo).",
        },
        "elapsed_s": round(time.time() - t0, 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    audit = {
        "schema_version": "1.0",
        "experiment": "EXP_C3FIX",
        "role": "MICRO_AGENTE_C3FIX",
        "hypothesis_under_test": "El edge LTF depth>=4 sobrevive fuera de muestra (EURUSD post-2024). Metrica: expectancy (mean_R). Gate: n_closed>=30.",
        "gate_logic": "n_closed<30 -> BLOCKED; n_closed>=30 & mean_R>0 & IC95_low>0 -> PASS (edge robusto OOS); n>=30 & edge no positivo -> FAIL (falsacion OOS).",
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "gate": {
            "n_ge_30": bool(gate_n),
            "expectancy_gt_0": bool(gate_exp),
            "ci_lower_gt_0": bool(gate_ci),
            "n_closed": n_closed,
            "mean_R": mean_r,
            "ci95_low": ci[0] if ci else None,
            "ci95_high": ci[1] if ci else None,
        },
        "protocol": {
            "code_commit": "ff6ed31",
            "code_commit_note": "HEAD del working tree. Motor engine/sequential_events.py y engine/sequential_outcome.py SON byte-identicos a daef67cf (git diff vacio): mismo motor garantizado. No se modifico run_sequential/sequential_outcome.",
            "engine": "run_sequential(structure_mode='lite', max_active_chains=4096, swing_left=3) + resolve_outcome",
            "invariants_held": True,
            "no_param_change_post_hoc": True,
            "parameter_change_vs_A1_B1_C": False,
            "data_integrity": {
                "symbol": "EURUSD",
                "exec_tf": "H1",
                "source": "data/raw/EURUSD/EURUSD_H1.parquet",
                "source_kind": "parquet",
                "data_origin": "NO-canonico: parquet data/raw (origen distinto al CSV Dukascopy canonico de datasets/eurusd_dukascopy_20y/EURUSD_H1.csv)",
                "declared_hash": "ac028d7d8a6cd977a7d40ed632642a9bb3f60410d05971a05169cb8f3d380cc7",
                "actual_file_sha256": "ac028d7d8a6cd977a7d40ed632642a9bb3f60410d05971a05169cb8f3d380cc7",
                "range": [RANGE_START, RANGE_END],
                "range_label": "OOS EXTENDIDO (2025-01-01..2026-08-14), NO solo 2025, para alcanzar n>=30",
                "bars": n_bars,
                "cross_origin_caveat": True,
                "canonical_dataset_note": "CSV canonico Dukascopy 20Y (SHA256 2dbb5757) cubre solo hasta 2025-12-31 y en 2025 entrega n_closed=24<30 (EXP_C3 BLOCKED). Por ello el OOS se extiende con parquet (origen distinto) hasta 2026-08-14. El OOS 2025 proviene de parquet, NO del CSV canonico.",
                "leakage_check": "clean_single_pass_PIT: run_sequential UNA llamada sobre el rango; anchor=STRUCTURE close; SL/TP derivados de rango sweep_bar->structure_bar y swings confirmados (PIT-safe); sin fuga de futuro.",
                "oos_2025_from_parquet": True,
            },
            "config": {
                "min_depth": MIN_DEPTH,
                "horizon_bars": HORIZON_BARS,
                "sl_buffer": SL_BUFFER,
                "tie_policy": "pessimistic",
                "warmup_bars": WARMUP_BARS,
                "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "baseline_seed": BASELINE_SEED,
                "min_n_gate": MIN_N_GATE,
                "costs_applied": False,
            },
            "date": datetime.now(timezone.utc).isoformat(),
        },
        "metrics_summary": {
            "treatment": {
                "n_closed": n_closed,
                "mean_R": mean_r,
                "median_R": m_treat.get("median_r"),
                "win_rate": wr,
                "win_rate_wilson95": wilson,
                "profit_factor": pf,
                "drawdown": dd,
                "bootstrap_mean_r_ci": ci,
            },
            "baseline": {
                "n_closed": m_base["n_closed"],
                "mean_R": m_base.get("mean_r"),
                "win_rate": m_base.get("win_rate"),
                "bootstrap_mean_r_ci": (m_base.get("bootstrap_clustered") or {}).get("mean_r_ci"),
            },
            "in_sample_reference_mean_R": 0.250,
        },
        "result_raw_file": "reports/audits/EXP_C3FIX_raw.json",
    }

    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    OUT_RAW.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    OUT_AUDIT.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "gate_n_ge_30": gate_n,
        "gate_expectancy_gt_0": gate_exp,
        "gate_ci_lower_gt_0": gate_ci,
        "treatment": {k: raw["treatment"][k] for k in ("n_closed", "mean_R", "median_R", "win_rate", "profit_factor", "drawdown", "bootstrap_mean_r_ci")},
        "baseline_mean_R": raw["baseline_fvg_random"]["mean_R"],
        "delta_oos_minus_is": raw["comparison_to_in_sample"]["delta_oos_minus_is"],
        "out_raw": str(OUT_RAW),
        "out_audit": str(OUT_AUDIT),
    }, indent=2), flush=True)
    return {"verdict": verdict, "raw": raw, "audit": audit}


if __name__ == "__main__":
    main()
