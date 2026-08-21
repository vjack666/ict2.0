#!/usr/bin/env python3
"""AGENTE A — AISLAMIENTO (runner parametrizado, NO modifica el motor).

Reutiliza EXACTAMENTE el protocolo de exp_sequential_expectancy_depth4_lite.py:
mismo motor (run_sequential structure_mode="lite"), mismo SL/TP estructural,
mismo horizonte 200, bootstrap 2000, seed 42, Wilson 95%, tie_policy=pessimistic.

Unica variacion permitida por diseno de cada experimento:
- TF / origen de dataset (CSV canonico H1/H4 o parquet M15).
- depth_min (A5 prueba 3/4/5).
- DEFENSA PAREJA del baseline: se le asigna una mecha de sweep SIMULADA muestreada
  de la MISMA distribucion (offset sweep - broken_swing) que el tratamiento, para que
  su SL estructural use los MISMOS 2 terminos (min(sweep, broken_swing)).
- TP: por defecto measured_projection (fallback sancionado). A2 (TP HTF real) es
  BLOCKED por deuda PIT FULL-vs-PREFIX del navigator HTF->LTF (no se inventa TP).

Salida por experimento: reports/audits/experiments/current_batch/EXP_A<NN>_raw.json + _audit.json
"""
from __future__ import annotations

import json
import sys
import time
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.detectors.fvg import detect_fvg
from engine.sequential_events import (
    SeqConfig,
    Stage,
    _causal_swings,
    run_sequential,
    summarize_chains,
)
from engine.sequential_outcome import (
    OutcomeConfig,
    TradeLevels,
    bootstrap_clustered,
    measured_projection_tp,
    resolve_outcome,
    structural_stop,
    wilson_interval,
)

# ---- Protocolo fijo (contrato) ----
RANGE_START = "2019-01-01"
RANGE_END = "2024-12-31"
HORIZON_BARS = 200
SL_BUFFER = 0.0001
SWING_LEFT = 3
WARMUP_BARS = 20
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
BASELINE_SEED = 42
PAIRING_SEED = 4242  # fijo: muestreo determinista de offsets de sweep parejos
MIN_N_GATE = 30
CODE_COMMIT = "daef67cf212c4432c6e5e3a2b7c6cd404982059b"


def load_slice_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["time"])
    mask = (ts >= RANGE_START) & (ts <= RANGE_END + " 23:59:59")
    return df.loc[mask].sort_values("time").reset_index(drop=True)


def load_slice_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df[["time", "open", "high", "low", "close"]].copy()
    ts = pd.to_datetime(df["time"])
    mask = (ts >= RANGE_START) & (ts <= RANGE_END + " 23:59:59")
    return df.loc[mask].sort_values("time").reset_index(drop=True)


def last_confirmed_swing(swings, bar):
    if not swings:
        return None
    js = [j for j, _ in swings]
    limit = bar - SWING_LEFT
    pos = bisect_right(js, limit)
    if pos == 0:
        return None
    return float(swings[pos - 1][1])


def build_trade(direction, entry_bar, close, high, low, swing_lows, swing_highs,
                sweep_wick_low, sweep_wick_high, range_lo, range_hi, cfg):
    entry = float(close[entry_bar])
    if direction == 1:
        sl = structural_stop(1, sweep_extreme=sweep_wick_low,
                             broken_swing=last_confirmed_swing(swing_lows, entry_bar),
                             buffer=cfg.sl_buffer)
        broken = last_confirmed_swing(swing_lows, entry_bar)
    else:
        sl = structural_stop(-1, sweep_extreme=sweep_wick_high,
                             broken_swing=last_confirmed_swing(swing_highs, entry_bar),
                             buffer=cfg.sl_buffer)
        broken = last_confirmed_swing(swing_highs, entry_bar)
    tp = measured_projection_tp(direction, range_hi, range_lo)
    if sl is None or tp is None:
        return None
    levels = TradeLevels(direction=direction, entry=entry, sl=float(sl), tp=float(tp))
    return {"levels": levels, "broken": broken, "valid": levels.is_valid()}


def compute_metrics(trades, cluster_key):
    closed = [t for t in trades if t.get("exit_r") is not None]
    wins = sum(1 for t in closed if float(t["exit_r"]) > 0)
    rs = [float(t["exit_r"]) for t in closed]
    out = {
        "n_trades": len(trades),
        "n_closed": len(closed),
        "n_open": len([t for t in trades if t.get("outcome") == "OPEN"]),
        "n_invalid": len([t for t in trades if t.get("outcome") == "INVALID"]),
        "wins": wins,
        "losses": len(closed) - wins,
    }
    if closed:
        wr = wins / len(closed)
        lo, hi = wilson_interval(wins, len(closed))
        pos = sum(r for r in rs if r > 0)
        neg = sum(r for r in rs if r < 0)
        pf = round(pos / abs(neg), 4) if neg != 0 else None
        # drawdown of cumulative R equity curve (chronological entry order)
        eq = np.cumsum(np.array(rs, dtype=float))
        peak = np.maximum.accumulate(eq)
        dd = float(np.max(peak - eq)) if len(eq) else 0.0
        out.update({
            "win_rate": round(wr, 4),
            "win_rate_wilson95": [round(lo, 4), round(hi, 4)],
            "mean_r": round(float(np.mean(rs)), 4),
            "median_r": round(float(np.median(rs)), 4),
            "std_r": round(float(np.std(rs, ddof=1)) if len(rs) > 1 else 0.0, 4),
            "min_r": round(float(np.min(rs)), 4),
            "max_r": round(float(np.max(rs)), 4),
            "expectancy": round(float(np.mean(rs)), 4),
            "profit_factor": pf,
            "drawdown": round(dd, 4),
        })
    else:
        out.update({"win_rate": None, "win_rate_wilson95": None, "mean_r": None,
                    "expectancy": None, "profit_factor": None, "drawdown": None})
    out["bootstrap"] = bootstrap_clustered(trades, cluster_key,
                                           n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
    return out


def run_depth_experiment(slice_df, depth_min, paired=True, tf_label="H1", context_bucket_fn=None,
                         include_records=False):
    """Run treatment (depth>=depth_min) vs paired FVG-random baseline."""
    cfg_seq = SeqConfig(structure_mode="lite", max_active_chains=4096, swing_left=SWING_LEFT)
    cfg_out = OutcomeConfig(horizon_bars=HORIZON_BARS, sl_buffer=SL_BUFFER, tie_policy="pessimistic")
    high = slice_df["high"].to_numpy(float)
    low = slice_df["low"].to_numpy(float)
    close = slice_df["close"].to_numpy(float)
    times = list(slice_df["time"])
    n_bars = len(slice_df)

    chains = run_sequential(slice_df, cfg_seq, timeframe=tf_label)
    summary = summarize_chains(chains)
    swing_highs, swing_lows = _causal_swings(high, low, SWING_LEFT)

    candidates = [c for c in chains if len(c.nodes) >= depth_min]
    by_status = {}
    for c in candidates:
        by_status[c.status] = by_status.get(c.status, 0) + 1

    seen = set()
    treatment = []
    spans = []
    treat_offsets = {1: [], -1: []}  # sweep - broken_swing per direction
    for ch in candidates:
        # Anchor = the depth-d node (index depth_min-1). For depth>=4 this is the
        # STRUCTURE stage (contract H_A anchor). For A5 depth comparison we vary the
        # anchor node (DISPLACEMENT@3, STRUCTURE@4, OB@5) under the SAME SL/TP protocol.
        anchor_node = ch.nodes[depth_min - 1]
        sweep_node = ch.nodes[1]
        assert sweep_node.stage is Stage.SWEEP
        bar_i = int(anchor_node.bar)
        sweep_bar = int(sweep_node.bar)
        key = (bar_i, int(ch.direction))
        if key in seen or bar_i < WARMUP_BARS:
            continue
        seen.add(key)
        # Reconstruct the REAL sweep wick from the sweep candle OHLC. The motor
        # stores only pool_form_bar in the SWEEP node extra, so extra.get("sweep_low")
        # is always None -> the base script silently used a 1-term SL. The contract
        # SL rule is min(mecha sweep, swing roto)-buffer, so the sweep candle extreme
        # (PIT-valid: it is in the past at entry) is the correct 2nd term.
        extra = sweep_node.extra or {}
        sw_lo = float(low[sweep_bar]) if int(ch.direction) == 1 else None
        sw_hi = float(high[sweep_bar]) if int(ch.direction) == -1 else None
        a, b = sweep_bar, bar_i
        r_lo = float(np.min(low[a:b + 1]))
        r_hi = float(np.max(high[a:b + 1]))
        built = build_trade(int(ch.direction), bar_i, close, high, low, swing_lows, swing_highs,
                            None if sw_lo is None else float(sw_lo),
                            None if sw_hi is None else float(sw_hi),
                            r_lo, r_hi, cfg_out)
        if built is None:
            continue
        spans.append(bar_i - sweep_bar)
        res = resolve_outcome(high, low, bar_i, built["levels"], cfg_out)
        # collect offset for pairing
        bs = built["broken"]
        if bs is not None and np.isfinite(bs):
            if int(ch.direction) == 1 and sw_lo is not None:
                off = float(sw_lo) - bs
                if np.isfinite(off):
                    treat_offsets[1].append(off)
            if int(ch.direction) == -1 and sw_hi is not None:
                off = float(sw_hi) - bs
                if np.isfinite(off):
                    treat_offsets[-1].append(off)
        treatment_row = {
            "group": "treatment", "chain_id": ch.chain_id,
            "direction": int(ch.direction), "structure_bar": bar_i,
            "sweep_bar": sweep_bar, "time": times[bar_i], "status": ch.status,
            "depth": len(ch.nodes),
            "entry": round(built["levels"].entry, 6), "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "sweep_wick_low": None if sw_lo is None else round(float(sw_lo), 6),
            "sweep_wick_high": None if sw_hi is None else round(float(sw_hi), 6),
            "range_low": round(r_lo, 6), "range_high": round(r_hi, 6),
            **res,
        }
        if context_bucket_fn is not None:
            treatment_row["context_bucket"] = context_bucket_fn(bar_i, int(ch.direction))
        treatment.append(treatment_row)

    # ---- Baseline: FVG-random, misma logica SL/TP; DEFENSA PAREJA ----
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
    prng = np.random.default_rng(PAIRING_SEED)
    baseline = []
    for idx in order:
        if len(baseline) >= len(treatment):
            break
        cb, direction = fvg_events[idx]
        a = max(0, cb - k_window + 1)
        r_lo = float(np.min(low[a:cb + 1]))
        r_hi = float(np.max(high[a:cb + 1]))
        # simulated sweep wick from treatment distribution (offset relative to broken swing)
        bs = last_confirmed_swing(swing_lows if direction == 1 else swing_highs, cb)
        sim_lo = None
        sim_hi = None
        offs = treat_offsets.get(int(direction), [])
        if offs:
            off = float(prng.choice(offs))
            if bs is not None and np.isfinite(bs):
                if direction == 1:
                    sim_lo = bs + off
                else:
                    sim_hi = bs + off
        built = build_trade(direction, cb, close, high, low, swing_lows, swing_highs,
                            sim_lo, sim_hi, r_lo, r_hi, cfg_out)
        if built is None:
            continue
        res = resolve_outcome(high, low, cb, built["levels"], cfg_out)
        baseline.append({
            "group": "baseline", "chain_id": f"BASE_{cb}_{direction}",
            "direction": int(direction), "structure_bar": cb, "time": times[cb],
            "depth": 0, "fvg_window_bars": k_window,
            "entry": round(built["levels"].entry, 6), "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "sweep_wick_low": None if sim_lo is None else round(sim_lo, 6),
            "sweep_wick_high": None if sim_hi is None else round(sim_hi, 6),
            "range_low": round(r_lo, 6), "range_high": round(r_hi, 6),
            **res,
        })

    m_treat = compute_metrics(treatment, "chain_id")
    m_base = compute_metrics(baseline, "chain_id")
    delta_wr = (round(m_treat["win_rate"] - m_base["win_rate"], 4)
                if m_treat.get("win_rate") is not None and m_base.get("win_rate") is not None else None)
    delta_mean_r = (round(m_treat["mean_r"] - m_base["mean_r"], 4)
                    if m_treat.get("mean_r") is not None and m_base.get("mean_r") is not None else None)
    result = {
        "motor_summary": summary,
        "chains_depth_ge": {"depth_min": depth_min, "n": len(candidates), "by_status": by_status},
        "treatment": m_treat, "baseline": m_base,
        "delta_win_rate": delta_wr, "delta_mean_r": delta_mean_r,
        "n_treatment": len(treatment), "n_baseline": len(baseline),
        "paired": paired, "n_paired_offsets": {str(k): len(v) for k, v in treat_offsets.items()},
    }
    if include_records:
        result["treatment_records"] = treatment
        result["baseline_records"] = baseline
    return result


def write_outputs(exp_id, component, raw_obj, audit_obj):
    out_dir = ROOT / "reports" / "audits" / "experiments" / "current_batch"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"EXP_{exp_id}_raw.json").write_text(json.dumps(raw_obj, indent=2, default=str), encoding="utf-8")
    (out_dir / f"EXP_{exp_id}_audit.json").write_text(json.dumps(audit_obj, indent=2, default=str), encoding="utf-8")
    print(f"[{exp_id}] wrote EXP_{exp_id}_raw.json + EXP_{exp_id}_audit.json  verdict={audit_obj['verdict']}")


def mechanical_verdict(m):
    n_ge_30 = (m.get("n_closed") or 0) >= MIN_N_GATE
    exp_gt_0 = (m.get("mean_r") or 0) > 0
    ci = (m.get("bootstrap") or {}).get("mean_r_ci")
    ci_lower_gt_0 = bool(ci and len(ci) == 2 and ci[0] > 0)
    return {
        "n_ge_30": bool(n_ge_30),
        "expectancy_gt_0": bool(exp_gt_0),
        "ci_lower_gt_0": ci_lower_gt_0,
    }, (n_ge_30 and exp_gt_0 and ci_lower_gt_0)


def dataset_record(origin, source_rel, bars, ds_hash, is_canonical, tf, note=None):
    return {
        "symbol": "EURUSD", "exec_tf": tf, "source": source_rel,
        "range_start": RANGE_START, "range_end": RANGE_END, "bars": bars,
        "dataset_hash": ds_hash, "is_canonical": is_canonical, "origin": origin,
        "note": note,
    }


def main():
    exp_id = sys.argv[1] if len(sys.argv) > 1 else "A1"
    t0 = time.time()
    if exp_id == "A2":
        # BLOCKED: TP de liquidez HTF real no disponible (deuda PIT FULL-vs-PREFIX).
        raw = {
            "schema_version": "1.0", "experiment": "EXP_A2",
            "component_isolated": "TP de liquidez HTF real (vs measured_projection fallback)",
            "status": "BLOCKED", "executed": False,
            "dataset": dataset_record("csv", "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv",
                                      36934, "2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022",
                                      True, "H1",
                                      "Definido sobre EURUSD H1 depth>=4; el componente AUSENTE es el TP "
                                      "de liquidez HTF real (no el dataset)."),
            "config": {"depth_min": 4, "tp_source_intended": "HTF liquidity (BLOCKED: unavailable)",
                       "tp_rule_applied_in_lite": "measured_projection (fallback sancionado)",
                       "sl_rule": "min(mecha sweep, swing roto)-buffer",
                       "horizon_bars": HORIZON_BARS, "tie_policy": "pessimistic",
                       "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED}},
            "reason": "No existe capa navigator HTF->LTF limpia para fijar TP de liquidez HTF real; "
                      "deuda PIT FULL-vs-PREFIX documentada en "
                      ".hermes-worklog/2026-08-20_2049_EXP_SEQXCONTEXT_INVALIDATED.md. "
                      "detect_liquidity_htf() seul calcula extremos LTF rolling (left=3), NO pools HTF "
                      "reales; mapearlos a LTF requiere el navigator con la deuda citada. No se inventa TP.",
            "code_commit": CODE_COMMIT, "date": datetime.now(timezone.utc).isoformat(),
        }
        audit = {
            "schema_version": "1.0", "experiment": "EXP_A2",
            "component_isolated": "TP de liquidez HTF real (vs measured_projection fallback)",
            "code_commit": CODE_COMMIT, "date": datetime.now(timezone.utc).isoformat(),
            "gate": {"n_ge_30": False, "expectancy_gt_0": False, "ci_lower_gt_0": False,
                     "note": "no ejecutado"},
            "protocol": {
                "leakage_check": "BLOCKED: TP HTF real requiere navigator HTF->LTF con deuda PIT "
                                 "FULL-vs-PREFIX no resuelta (ver bitacora 2026-08-20).",
                "parameter_change": False,
                "data_integrity": dataset_record("csv", "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv",
                                                 36934, "2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022",
                                                 True, "H1",
                                                 "Dataset canonico valido; componente TP HTF real ausente."),
            },
            "verdict": "BLOCKED",
            "rationale": "mecanico: experimento no puede ejecutarse EXACTAMENTE (componente TP HTF real "
                         "ausente / no limpio); se declara BLOCKED, no se inventa el TP.",
        }
        write_outputs("A2", raw["component_isolated"], raw, audit)
        return

    # A1/A3/A4/A5 -> executed
    if exp_id == "A1":
        tf, src, origin, canonical, note = ("H1", "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv",
                                            "csv", True, None)
        depth_list = [4]
        component = "Anclaje secuencial depth>=4 vs entrada FVG-aleatoria (defensa pareja, SL/TP estructural idénticos)"
    elif exp_id == "A3":
        tf, src, origin, canonical, note = ("H4", "datasets/eurusd_dukascopy_20y/EURUSD_H4.csv",
                                            "csv", True, None)
        depth_list = [4]
        component = "Anclaje secuencial depth>=4 en H4 (mismo método A1, defensa pareja)"
    elif exp_id == "A4":
        tf, src, origin, canonical, note = ("M15", "data/raw/EURUSD/EURUSD_M15.parquet",
                                            "parquet", False,
                                            "Origen PARQUET distinto al CSV canonico; rango solo 2022-2024 "
                                            "(no 2019-2024); hash 336d6f1d3f39736238f12f9d15e1d2b7f8bd10a4d42944b21d9d1fe74f505ef7")
        depth_list = [4]
        component = "Anclaje secuencial depth>=4 en M15 (parquet, defensa pareja)"
    elif exp_id == "A5":
        tf, src, origin, canonical, note = ("H1", "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv",
                                            "csv", True, None)
        depth_list = [3, 4, 5]
        component = "Componente PROFUNDIDAD: depth>=3 vs >=4 vs >=5 (H1, mismo protocolo, defensa pareja)"
    else:
        raise SystemExit(f"unknown exp_id {exp_id}")

    src_path = ROOT / src
    if origin == "csv":
        slice_df = load_slice_csv(src_path)
    else:
        slice_df = load_slice_parquet(src_path)
    n_bars = len(slice_df)
    ds_hash = hashlib_sha256(src_path)

    # run_sequential once; filter by depth per experiment
    results = {}
    for d in depth_list:
        r = run_depth_experiment(slice_df, d, paired=True, tf_label=tf)
        results[d] = r

    # Build per-depth RAW + AUDIT
    raw_depths = {}
    audit_depths = {}
    for d in depth_list:
        r = results[d]
        gate, pass_all = mechanical_verdict(r["treatment"])
        raw_depths[d] = {
            "depth_min": d,
            "treatment": r["treatment"], "baseline": r["baseline"],
            "delta_win_rate": r["delta_win_rate"], "delta_mean_r": r["delta_mean_r"],
            "motor_summary": r["motor_summary"],
            "chains_depth_ge": r["chains_depth_ge"],
            "n_treatment": r["n_treatment"], "n_baseline": r["n_baseline"],
            "paired": r["paired"], "n_paired_offsets": r["n_paired_offsets"],
        }
        audit_depths[d] = {
            "depth_min": d,
            "gate": gate,
            "protocol": {
                "leakage_check": "OK: run_sequential en una sola pasada sobre rango acotado; "
                                 "PIT-estable DENTRO del rango (deuda FULL-vs-PREFIX documentada "
                                 "afecta al indice HTF del navigator, NO a este diseno mono-TF de "
                                 "una pasada).",
                "parameter_change": False,
                "data_integrity": dataset_record(origin, src, n_bars, ds_hash, canonical, tf, note),
            },
            "verdict": "PASS" if pass_all else ("BLOCKED" if (r["treatment"].get("n_closed") or 0) < MIN_N_GATE else "FAIL"),
            "rationale": "mecanico: PASS iff n_closed>=30 AND expectancy(mean_r)>0 AND bootstrap CI95 lower>0.",
        }

    if exp_id == "A5":
        # Each depth is its own paired experiment; report all three. The primary
        # anchor per H_A is depth>=4. depth>=5 (n<30) is a BLOCKED sub-case.
        overall = audit_depths.get(4, {}).get("verdict", "BLOCKED")
        raw = {
            "schema_version": "1.0", "experiment": "EXP_A5", "component_isolated": component,
            "code_commit": CODE_COMMIT, "date": datetime.now(timezone.utc).isoformat(),
            "dataset": dataset_record(origin, src, n_bars, ds_hash, canonical, tf, note),
            "config": {"structure_mode": "lite", "max_active_chains": 4096, "swing_left": SWING_LEFT,
                       "depth_list": depth_list, "sl_rule": "min(sweep_wick,broken_swing)-buffer",
                       "tp_rule": "measured_projection (fallback sancionado)", "sl_buffer": SL_BUFFER,
                       "horizon_bars": HORIZON_BARS, "tie_policy": "pessimistic", "warmup_bars": WARMUP_BARS,
                       "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
                       "baseline_seed": BASELINE_SEED, "pairing_seed": PAIRING_SEED,
                       "paired_sweep_defense": True},
            "depths": raw_depths,
            "overall_verdict": overall,
            "elapsed_s": round(time.time() - t0, 2),
        }
        audit = {
            "schema_version": "1.0", "experiment": "EXP_A5", "component_isolated": component,
            "code_commit": CODE_COMMIT, "date": datetime.now(timezone.utc).isoformat(),
            "depth_cases": audit_depths,
            "overall_verdict": overall,
            "verdict": overall,
            "rationale": "mecanico por depth: depth>=5 con n_closed<30 => BLOCKED (sub-caso).",
        }
        write_outputs("A5", component, raw, audit)
        return

    # single-depth (A1/A3/A4): primary = treatment
    r = results[depth_list[0]]
    raw = {
        "schema_version": "1.0", "experiment": f"EXP_{exp_id}", "component_isolated": component,
        "code_commit": CODE_COMMIT, "date": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset_record(origin, src, n_bars, ds_hash, canonical, tf, note),
        "config": {"structure_mode": "lite", "max_active_chains": 4096, "swing_left": SWING_LEFT,
                   "depth_min": depth_list[0], "sl_rule": "min(sweep_wick,broken_swing)-buffer",
                   "tp_rule": "measured_projection (fallback sancionado)", "sl_buffer": SL_BUFFER,
                   "horizon_bars": HORIZON_BARS, "tie_policy": "pessimistic", "warmup_bars": WARMUP_BARS,
                   "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
                   "baseline_seed": BASELINE_SEED, "pairing_seed": PAIRING_SEED,
                   "paired_sweep_defense": True},
        "motor_summary": r["motor_summary"],
        "chains_depth_ge": r["chains_depth_ge"],
        "treatment": r["treatment"], "baseline": r["baseline"],
        "delta_win_rate": r["delta_win_rate"], "delta_mean_r": r["delta_mean_r"],
        "n_treatment": r["n_treatment"], "n_baseline": r["n_baseline"],
        "paired": r["paired"], "n_paired_offsets": r["n_paired_offsets"],
        "elapsed_s": round(time.time() - t0, 2),
    }
    gate, pass_all = mechanical_verdict(r["treatment"])
    verdict = "PASS" if pass_all else ("BLOCKED" if (r["treatment"].get("n_closed") or 0) < MIN_N_GATE else "FAIL")
    audit = {
        "schema_version": "1.0", "experiment": f"EXP_{exp_id}", "component_isolated": component,
        "code_commit": CODE_COMMIT, "date": datetime.now(timezone.utc).isoformat(),
        "gate": gate,
        "protocol": {
            "leakage_check": "OK: run_sequential en una sola pasada sobre rango acotado; "
                             "PIT-estable DENTRO del rango (deuda FULL-vs-PREFIX afecta al indice HTF "
                             "del navigator, NO a este diseno mono-TF de una pasada).",
            "parameter_change": False,
            "data_integrity": dataset_record(origin, src, n_bars, ds_hash, canonical, tf, note),
        },
        "verdict": verdict,
        "rationale": "mecanico: PASS iff n_closed>=30 AND expectancy(mean_r)>0 AND bootstrap CI95 lower>0.",
    }
    write_outputs(exp_id, component, raw, audit)


def hashlib_sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    main()
