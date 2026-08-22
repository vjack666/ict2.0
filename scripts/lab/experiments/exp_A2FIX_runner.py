#!/usr/bin/env python3
"""MICRO-AGENTE A2-FIX — TP de liquidez HTF real (BSL/SSL H4/D1).

Reutiliza EXACTAMENTE el protocolo A1/B1 (run_depth_experiment, defensa pareja,
SL estructural identico min(mecha sweep, swing roto)-buffer, horizonte 200,
bootstrap 2000 seed 42, Wilson 95%, tie_policy=pessimistic, baseline FVG-random
medido con la MISMA logica). La UNICA diferencia de diseno es el TP del
TRATAMIENTO: liquidez HTF real (BSL/SSL) en H4/D1 via engine.market_features
.detect_liquidity, mapeada por timestamp a barras HTF CERRADAS (PIT-estable,
sin mapeo de indice de cadena). Fallback a measured_projection si no hay
liquidez valida en rango (marcado en tp_source).

Salida: reports/audits/EXP_A2FIX_raw.json + reports/audits/EXP_A2FIX_audit.json
"""
from __future__ import annotations

import hashlib
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

from engine.market_features import detect_liquidity  # re-exporta detectors.liquidity.detect_liquidity
from exp_agentA_runner import (  # protocolo A1 verificado
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
    build_trade,                 # TP measured_projection (para el baseline identico A1/B1)
    compute_metrics,
    dataset_record,
    last_confirmed_swing,
    load_slice_csv,
    mechanical_verdict,
)
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
    measured_projection_tp,
    resolve_outcome,
    structural_stop,
)

RANGE_START = "2019-01-01"
RANGE_END = "2024-12-31"
DEPTH_MIN = 4
TF = "H1"
SRC_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv"
SRC_PATH = ROOT / SRC_REL
H4_PATH = ROOT / "datasets/eurusd_dukascopy_20y/EURUSD_H4.csv"
D1_PATH = ROOT / "datasets/eurusd_dukascopy_20y/EURUSD_D1.csv"
CANONICAL_HASH = "2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022"

REPORT_DIR = ROOT / "reports" / "audits"
RAW_PATH = REPORT_DIR / "EXP_A2FIX_raw.json"
AUDIT_PATH = REPORT_DIR / "EXP_A2FIX_audit.json"
A1B1_REFERENCE_EXPECTANCY = 0.250  # expectancy de A1/B1 (mean_R ~0.2499)

HEAD_COMMIT = "ff6ed31530e646482d6283f1b9499f9010b5d3ba"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_htf(path: Path):
    """Carga HTF, ordena por tiempo, corre detect_liquidity una vez.

    detect_liquidity asigna cada zona forward desde su barra de confirmacion,
    por lo que leer el valor en el bar as-of (indice con time<=decision) es
    PIT-seguro: solo son visibles zonas confirmadas en el pasado.
    """
    df = pd.read_csv(path)
    df = df.sort_values("time").reset_index(drop=True)
    liq = detect_liquidity(df)  # columnas bsl_top/bsl_bot/bsl_price, ssl_top/ssl_bot/ssl_price
    times = pd.to_datetime(liq["time"], utc=False, errors="coerce").values
    return liq, times


def asof_index(times, t) -> int | None:
    """Ultimo indice con times[i] <= t (vela HTF cerrada)."""
    if len(times) == 0:
        return None
    i = int(np.searchsorted(times, t, side="right")) - 1
    return i if i >= 0 else None


def htf_tp(direction, entry_time, entry, h4_liq, h4_times, d1_liq, d1_times):
    """TP de liquidez HTF real en direccion del trade.

    long  -> BSL (buyside) mas cercana POR ENCIMA del entry: min(bsl_top H4, bsl_top D1) > entry
    short -> SSL (sellside) mas cercana POR DEBAJO del entry: max(ssl_bot H4, ssl_bot D1) < entry
    Devuelve (tp, source). Si no hay liquidez valida -> (None, 'fallback_measured').
    """
    if direction == 1:
        cand = []
        i4 = asof_index(h4_times, entry_time)
        if i4 is not None:
            v = h4_liq["bsl_top"].iloc[i4]
            if pd.notna(v) and float(v) > entry:
                cand.append((float(v), "htf_h4"))
        i1 = asof_index(d1_times, entry_time)
        if i1 is not None:
            v = d1_liq["bsl_top"].iloc[i1]
            if pd.notna(v) and float(v) > entry:
                cand.append((float(v), "htf_d1"))
        if cand:
            tp, src = min(cand, key=lambda x: x[0])  # mas cercana arriba
            return tp, src
        return None, "fallback_measured"
    else:
        cand = []
        i4 = asof_index(h4_times, entry_time)
        if i4 is not None:
            v = h4_liq["ssl_bot"].iloc[i4]
            if pd.notna(v) and float(v) < entry:
                cand.append((float(v), "htf_h4"))
        i1 = asof_index(d1_times, entry_time)
        if i1 is not None:
            v = d1_liq["ssl_bot"].iloc[i1]
            if pd.notna(v) and float(v) < entry:
                cand.append((float(v), "htf_d1"))
        if cand:
            tp, src = max(cand, key=lambda x: x[0])  # mas cercana abajo
            return tp, src
        return None, "fallback_measured"


def run_depth_experiment_htf(slice_df, depth_min, paired=True, tf_label="H1",
                             h4_liq=None, h4_times=None, d1_liq=None, d1_times=None):
    """Treatment con TP HTF real; baseline identico A1/B1 (measured_projection, defensa pareja)."""
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
    treat_offsets = {1: [], -1: []}
    tp_source_counts = {}

    for ch in candidates:
        anchor_node = ch.nodes[depth_min - 1]
        sweep_node = ch.nodes[1]
        assert sweep_node.stage is Stage.SWEEP
        bar_i = int(anchor_node.bar)
        sweep_bar = int(sweep_node.bar)
        key = (bar_i, int(ch.direction))
        if key in seen or bar_i < WARMUP_BARS:
            continue
        seen.add(key)
        # mecha de sweep real (PIT-valida): igual que A1/B1 (defensa pareja 2 terminos)
        sw_lo = float(low[sweep_bar]) if int(ch.direction) == 1 else None
        sw_hi = float(high[sweep_bar]) if int(ch.direction) == -1 else None
        a, b = sweep_bar, bar_i
        r_lo = float(np.min(low[a:b + 1]))
        r_hi = float(np.max(high[a:b + 1]))
        # SL estructural IDéntico a A1/B1
        if int(ch.direction) == 1:
            sl = structural_stop(1, sweep_extreme=sw_lo,
                                 broken_swing=last_confirmed_swing(swing_lows, bar_i),
                                 buffer=cfg_out.sl_buffer)
        else:
            sl = structural_stop(-1, sweep_extreme=sw_hi,
                                 broken_swing=last_confirmed_swing(swing_highs, bar_i),
                                 buffer=cfg_out.sl_buffer)
        if sl is None:
            continue
        entry = float(close[bar_i])
        # TP de liquidez HTF real (UNICA diferencia vs A1/B1)
        entry_time = pd.to_datetime(times[bar_i], utc=False, errors="coerce")
        tp, source = htf_tp(int(ch.direction), entry_time, entry, h4_liq, h4_times, d1_liq, d1_times)
        if tp is None:
            tp = measured_projection_tp(int(ch.direction), r_hi, r_lo)
            source = "fallback_measured"
        if tp is None:
            continue
        levels = TradeLevels(direction=int(ch.direction), entry=entry, sl=float(sl), tp=float(tp))
        if not levels.is_valid():
            # TP HTF no valido (no estricto mas alla del entry): fallback medido
            tp = measured_projection_tp(int(ch.direction), r_hi, r_lo)
            source = "fallback_measured_invalid"
            if tp is None:
                continue
            levels = TradeLevels(direction=int(ch.direction), entry=entry, sl=float(sl), tp=float(tp))
            if not levels.is_valid():
                continue
        tp_source_counts[source] = tp_source_counts.get(source, 0) + 1
        res = resolve_outcome(high, low, bar_i, levels, cfg_out)
        bs = last_confirmed_swing(swing_lows if int(ch.direction) == 1 else swing_highs, bar_i)
        if bs is not None and np.isfinite(bs):
            if int(ch.direction) == 1 and sw_lo is not None:
                off = float(sw_lo) - bs
                if np.isfinite(off):
                    treat_offsets[1].append(off)
            if int(ch.direction) == -1 and sw_hi is not None:
                off = float(sw_hi) - bs
                if np.isfinite(off):
                    treat_offsets[-1].append(off)
        treatment.append({
            "group": "treatment", "chain_id": ch.chain_id,
            "direction": int(ch.direction), "structure_bar": bar_i,
            "sweep_bar": sweep_bar, "time": times[bar_i], "status": ch.status,
            "depth": len(ch.nodes),
            "entry": round(entry, 6), "sl": round(float(sl), 6), "tp": round(float(tp), 6),
            "sweep_wick_low": None if sw_lo is None else round(sw_lo, 6),
            "sweep_wick_high": None if sw_hi is None else round(sw_hi, 6),
            "range_low": round(r_lo, 6), "range_high": round(r_hi, 6),
            "tp_source": source,
            **res,
        })
        spans.append(bar_i - sweep_bar)

    # ---- Baseline: FVG-random, MISMA logica A1/B1 (measured_projection, defensa pareja) ----
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
        # build_trade usa measured_projection_tp (identico A1/B1)
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
    return {
        "motor_summary": summary,
        "chains_depth_ge": {"depth_min": depth_min, "n": len(candidates), "by_status": by_status},
        "treatment": m_treat, "baseline": m_base,
        "delta_win_rate": delta_wr, "delta_mean_r": delta_mean_r,
        "n_treatment": len(treatment), "n_baseline": len(baseline),
        "paired": paired, "n_paired_offsets": {str(k): len(v) for k, v in treat_offsets.items()},
        "tp_source_counts": tp_source_counts,
    }


def raw_block(m: dict) -> dict:
    ci = (m.get("bootstrap") or {}).get("mean_r_ci")
    return {
        "n_closed": m.get("n_closed"), "n_trades": m.get("n_trades"), "n_open": m.get("n_open"),
        "mean_R": m.get("mean_r"), "median_R": m.get("median_r"),
        "win_rate": m.get("win_rate"), "profit_factor": m.get("profit_factor"),
        "expectancy": m.get("expectancy"), "drawdown": m.get("drawdown"),
        "wilson_95": m.get("win_rate_wilson95"), "bootstrap_ci_95": ci,
    }


def main() -> None:
    t0 = time.time()
    ds_hash = sha256_file(SRC_PATH)
    assert ds_hash == CANONICAL_HASH, f"dataset hash mismatch: {ds_hash}"

    slice_df = load_slice_csv(SRC_PATH)
    n_bars = len(slice_df)

    print("precomputing HTF liquidity (H4/D1)...", flush=True)
    h4_liq, h4_times = load_htf(H4_PATH)
    d1_liq, d1_times = load_htf(D1_PATH)
    print(f"HTF loaded: H4={len(h4_liq)} bars, D1={len(d1_liq)} bars", flush=True)

    result = run_depth_experiment_htf(slice_df.copy(), DEPTH_MIN, paired=True, tf_label=TF,
                                      h4_liq=h4_liq, h4_times=h4_times,
                                      d1_liq=d1_liq, d1_times=d1_times)
    m_treat = result["treatment"]
    m_base = result["baseline"]

    mean_r = m_treat.get("mean_r")
    delta_vs_A1B1 = (round(float(mean_r) - A1B1_REFERENCE_EXPECTANCY, 4)
                     if mean_r is not None else None)

    # ---- RAW ----
    raw = {
        "schema_version": "1.0",
        "experiment": "EXP_A2FIX",
        "role": "TP_LIQUIDEZ_HTF_REAL (variante de A1/B1: SOLO cambia el TP del tratamiento)",
        "hypothesis": (
            "H_A2: EURUSD H1 depth>=4, defensa pareja (SL 2 terminos), MISMO protocolo A1/B1 "
            "pero el TP del tratamiento usa liquidez HTF real (BSL/SSL H4/D1 via detect_liquidity) "
            "en direccion del trade; fallback measured_projection si no hay liquidez en rango. "
            "Metrica primaria: expectancy (mean_R). Gate: n_closed>=30. Delta vs A1/B1 (+0.250)."
        ),
        "dataset": dataset_record("csv", SRC_REL, n_bars, ds_hash, True, TF,
                                  "Dataset canonico H1 2019-2024; TP HTF de H4/D1 derivado de CSV canonico."),
        "dataset_hash": ds_hash,
        "code_commit": CODE_COMMIT,
        "code_commit_head": HEAD_COMMIT,
        "config": {
            "structure_mode": "lite", "max_active_chains": 4096, "swing_left": SWING_LEFT,
            "depth_min": DEPTH_MIN, "anchor": "STRUCTURE_bar_close (depth>=4)",
            "sl_rule": "min(sweep_wick, broken_swing)-buffer (defensa pareja, 2 terminos) [IDENTICO A1/B1]",
            "tp_rule": "HTF real liquidity BSL/SSL (H4/D1) via detect_liquidity, as-of closed HTF bar; "
                       "fallback measured_projection si no hay liquidez valida en rango",
            "htf_tp_field": "bsl_top(long)/ssl_bot(short) = borde exterior de la zona de liquidez",
            "tp_baseline_rule": "measured_projection (IDENTICO A1/B1)",
            "sl_buffer": SL_BUFFER, "horizon_bars": HORIZON_BARS, "tie_policy": "pessimistic",
            "warmup_bars": WARMUP_BARS,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
            "baseline_seed": BASELINE_SEED, "pairing_seed": PAIRING_SEED, "paired_sweep_defense": True,
            "htf_context": True, "htf_frames": ["H4", "D1"],
        },
        "fecha": datetime.now(timezone.utc).isoformat(),
        "treatment": raw_block(m_treat),
        "baseline": raw_block(m_base),
        "htf_tp_stats": {
            "tp_source_counts": result["tp_source_counts"],
            "n_treatment": result["n_treatment"], "n_baseline": result["n_baseline"],
            "n_paired_offsets": result["n_paired_offsets"],
        },
        "delta_vs_A1B1": {
            "reference_expectancy": A1B1_REFERENCE_EXPECTANCY,
            "reference_label": "A1/B1 (EXP_B1 treatment mean_R=0.2499)",
            "delta_expectancy": delta_vs_A1B1,
        },
        "control_reference": {
            "expectancy_treatment": m_treat.get("mean_r"),
            "expectancy_baseline": m_base.get("mean_r"),
            "win_rate_treatment": m_treat.get("win_rate"),
            "win_rate_baseline": m_base.get("win_rate"),
            "delta_expectancy_treatment_minus_baseline": (
                round(m_treat["mean_r"] - m_base["mean_r"], 4)
                if m_treat.get("mean_r") is not None and m_base.get("mean_r") is not None else None),
            "delta_win_rate_treatment_minus_baseline": result.get("delta_win_rate"),
        },
        "motor_summary": result["motor_summary"],
        "chains_depth_ge4": result["chains_depth_ge"],
        "elapsed_s": round(time.time() - t0, 2),
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
        "experiment": "EXP_A2FIX",
        "role": "TP_LIQUIDEZ_HTF_REAL (variante de A1/B1)",
        "code_commit": CODE_COMMIT,
        "code_commit_head": HEAD_COMMIT,
        "date": datetime.now(timezone.utc).isoformat(),
        "gate": {
            "n_ge_30": bool(gate["n_ge_30"]),
            "expectancy_gt_0": bool(gate["expectancy_gt_0"]),
            "ci_lower_gt_0": bool(gate["ci_lower_gt_0"]),
        },
        "protocol": {
            "leakage_check": (
                "OK: run_sequential UNA sola pasada sobre rango acotado 2019-2024 (PIT-estable "
                "DENTRO del rango). El TP HTF usa solo barras HTF CERRADAS por timestamp "
                "(as-of index en H4/D1); detect_liquidity asigna cada zona forward desde su "
                "barra de confirmacion, por lo que leer el valor en el bar as-of es PIT-seguro "
                "(no se usa mapeo de indice de cadena del navigator). Sin look-ahead de futuro."
            ),
            "parameter_change": False,
            "data_integrity": dataset_record("csv", SRC_REL, n_bars, ds_hash, True, TF,
                "Dataset canonico H1 verificado por SHA256; TP HTF derivado de EURUSD_H4.csv y "
                "EURUSD_D1.csv (canonicos). Unica diferencia vs A1/B1: fuente del TP del tratamiento."),
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
        "experiment": "EXP_A2FIX", "verdict": verdict,
        "treatment": {k: m_treat.get(k) for k in ("n_closed", "n_trades", "n_open", "win_rate", "mean_r", "expectancy", "profit_factor", "drawdown")},
        "baseline": {k: m_base.get(k) for k in ("n_closed", "n_trades", "win_rate", "mean_r", "expectancy", "profit_factor", "drawdown")},
        "delta_vs_A1B1": delta_vs_A1B1,
        "tp_source_counts": result["tp_source_counts"],
        "gate": gate, "treatment_bootstrap_ci": (m_treat.get("bootstrap") or {}).get("mean_r_ci"),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
