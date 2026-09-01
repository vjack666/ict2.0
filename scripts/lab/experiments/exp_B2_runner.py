#!/usr/bin/env python3
"""MICRO-AGENTE B2 — INCREMENTALIDAD + sesgo D1 (experimento B2).

H_B2: 'Añadir filtro de sesgo D1 (entra solo si sesgo D1 alinea direccion con
la estructura) incrementa la expectancy del baseline LTF (B1) en R por
operacion, bajo protocolo idéntico. Metrica: expectancy (mean_R). Gate:
n_closed>=30. Comparador: B1.'

Diseno estricto (contrato B1/B2):
- MISMO motor run_sequential(structure_mode="lite") que B1; MISMO commit de
  motor (daef67cf; engine/ es byte-identico entre daef67cf y HEAD).
- MISMA construccion de trade que B1 (exp_agentA_runner.run_depth_experiment,
  depth_min=4): anchor = nodo STRUCTURE (ch.nodes[3]), mecha de sweep REAL
  (low[sweep_bar] si long / high[sweep_bar] si short), SL estructural de 2
  terminos min(mecha sweep, swing roto)-buffer, TP measured_projection,
  horizonte 200, tie_policy=pessimistic. NO se cambia SL/TP.
- UNICO cambio permitido: FILTRO de entrada por sesgo D1. Se usa la columna
  'trend' de engine.market_features.build_features(D1) (BULLISH/BEARISH/RANGING),
  PIT-verificada (FULL==PREFIX, 0 violaciones en smoke de este repo). El
  filtro mantiene un anchor solo si (dir==1 y D1 BULLISH) o (dir==-1 y D1
  BEARISH); RANGING y contratendencia se descartan. B2 es un subconjunto
  filtrado de B1.
- Determinismo: el tratamiento no usa RNG. Se ASSERTA que la reproduccion sin
  filtro coincide con B1 (n_closed=211, mean_R=0.2499) para garantizar
  'mismo motor, mismo commit'.
- Delta vs B1 con IC: bootstrap POR PARES agrupado por chain_id (B2* subconjunto
  de B1* en cada remuestreo) -> CI95 de Delta_expectancy y Delta_win_rate que
  respeta la dependencia subconjunto/superconjunto.

Salida: reports/audits/EXP_B2_raw.json + reports/audits/EXP_B2_audit.json
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

from engine.detectors.fvg import detect_fvg  # noqa: F401  (kept for parity; unused in B2)
from engine.market_features import build_features
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

# ---- Protocolo fijo (idéntico a exp_agentA_runner / B1) ----
RANGE_START = "2019-01-01"
RANGE_END = "2024-12-31"
HORIZON_BARS = 200
SL_BUFFER = 0.0001
SWING_LEFT = 3
WARMUP_BARS = 20
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
MIN_N_GATE = 30
DEPTH_MIN = 4
TF = "H1"
CODE_COMMIT = "daef67cf212c4432c6e5e3a2b7c6cd404982059b"  # mismo motor que B1

H1_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv"
D1_REL = "datasets/eurusd_dukascopy_20y/EURUSD_D1.csv"
H1_PATH = ROOT / H1_REL
D1_PATH = ROOT / D1_REL
CANONICAL_HASH = "2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022"

REPORT_DIR = ROOT / "reports" / "audits"
RAW_PATH = REPORT_DIR / "EXP_B2_raw.json"
AUDIT_PATH = REPORT_DIR / "EXP_B2_audit.json"

# B1 reference (control) — leído del disco como comparador canónico.
B1_RAW_PATH = ROOT / "reports" / "audits" / "EXP_B1_raw.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_slice_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
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
    """IDÉNTICO a exp_agentA_runner.build_trade (B1)."""
    entry = float(close[entry_bar])
    if direction == 1:
        sl = structural_stop(1, sweep_extreme=sweep_wick_low,
                             broken_swing=last_confirmed_swing(swing_lows, entry_bar),
                             buffer=cfg.sl_buffer)
    else:
        sl = structural_stop(-1, sweep_extreme=sweep_wick_high,
                             broken_swing=last_confirmed_swing(swing_highs, entry_bar),
                             buffer=cfg.sl_buffer)
    tp = measured_projection_tp(direction, range_hi, range_lo)
    if sl is None or tp is None:
        return None
    levels = TradeLevels(direction=direction, entry=entry, sl=float(sl), tp=float(tp))
    return {"levels": levels, "valid": levels.is_valid()}


def compute_metrics(trades, cluster_key):
    """IDÉNTICO a exp_agentA_runner.compute_metrics (B1)."""
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
    t = {k: out[k] for k in ("n_trades", "n_closed", "n_open", "wins", "losses",
                            "win_rate", "mean_r", "median_r", "std_r", "min_r",
                            "max_r", "expectancy", "profit_factor", "drawdown",
                            "win_rate_wilson95")}
    t["bootstrap"] = bootstrap_clustered(
        trades, cluster_key, n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
    return t


def build_d1_trend_timeline(d1_df: pd.DataFrame):
    """Construye el timeline de sesgo D1 (columna 'trend' de build_features).

    PIT-safe: build_features en el frame completo; la columna 'trend' fue
    verificada FULL==PREFIX (0 violaciones en smoke de este repo). Devuelve
    (d1_times_sorted, d1_trend_list) para mapear por bisect cada barra H1 a la
    ultima vela D1 cerrada <= t.
    """
    ann = build_features(d1_df)
    if "trend" not in ann.columns:
        raise RuntimeError("build_features(D1) no expone columna 'trend'")
    times = pd.to_datetime(ann["time"], utc=True, errors="coerce")
    # verify PIT-safety on a sample (FULL vs PREFIX)
    n = len(ann)
    idxs = [max(0, min(n - 1, int(n * f))) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    viol = 0
    for i in idxs:
        pref = build_features(d1_df.iloc[: i + 1].copy())
        if str(ann["trend"].iloc[i]) != str(pref["trend"].iloc[i]):
            viol += 1
    return times.sort_values().reset_index(drop=True), ann["trend"].reset_index(drop=True), viol


def d1_trend_at(h1_time: pd.Timestamp, d1_times, d1_trend) -> str:
    """Sesgo D1 cerrado mas reciente <= h1_time (PIT-safe lookup)."""
    j = bisect_right(d1_times, h1_time) - 1
    if j < 0:
        return "RANGING"
    return str(d1_trend.iloc[j])


def passes_d1_filter(direction: int, d1_trend: str) -> bool:
    """Filtro B2: long<->BULLISH, short<->BEARISH; RANGING/counter => drop."""
    if direction == 1:
        return d1_trend == "BULLISH"
    if direction == -1:
        return d1_trend == "BEARISH"
    return False


def paired_delta_bootstrap(trades_all: list[dict], passes_flag, seed=42, n=2000):
    """Bootstrap POR PARES agrupado por chain_id.

    Cada remuestreo: extrae clusters (chain_id) con reemplazo; B1* = todos los
    trades cerrados del resample; B2* = los que pasan el filtro D1. Delta* =
    media(B2*) - media(B1*) y wr(B2*) - wr(B1*). El CI respeta que B2 es
    subconjunto de B1 (dependencia).
    """
    closed = [t for t in trades_all if t.get("exit_r") is not None]
    if not closed:
        return {"delta_expectancy_ci95": None, "delta_win_rate_ci95": None, "n_boot": 0}
    # group by chain_id
    by_chain: dict[str, list[dict]] = {}
    for t in closed:
        by_chain.setdefault(str(t["chain_id"]), []).append(t)
    chains = list(by_chain.values())
    rng = np.random.default_rng(seed)
    d_r, d_wr = [], []
    for _ in range(n):
        pick = rng.integers(0, len(chains), size=len(chains))
        b1_rs, b2_rs = [], []
        b1_w, b2_w = 0, 0
        b1_n, b2_n = 0, 0
        for idx in pick:
            grp = chains[idx]
            for t in grp:
                r = float(t["exit_r"])
                b1_rs.append(r); b1_n += 1
                if r > 0:
                    b1_w += 1
                if passes_flag(t):
                    b2_rs.append(r); b2_n += 1
                    if r > 0:
                        b2_w += 1
        if not b1_rs:
            continue
        mean_b1 = float(np.mean(b1_rs))
        mean_b2 = float(np.mean(b2_rs)) if b2_rs else 0.0
        d_r.append(mean_b2 - mean_b1)
        wr_b1 = b1_w / b1_n if b1_n else 0.0
        wr_b2 = b2_w / b2_n if b2_n else 0.0
        d_wr.append(wr_b2 - wr_b1)
    if not d_r:
        return {"delta_expectancy_ci95": None, "delta_win_rate_ci95": None, "n_boot": 0}
    return {
        "delta_expectancy_ci95": [round(float(np.percentile(d_r, 2.5)), 4),
                                  round(float(np.percentile(d_r, 97.5)), 4)],
        "delta_win_rate_ci95": [round(float(np.percentile(d_wr, 2.5)), 4),
                                round(float(np.percentile(d_wr, 97.5)), 4)],
        "n_boot": n,
    }


def main() -> None:
    t0 = time.time()
    ds_hash = sha256_file(H1_PATH)
    assert ds_hash == CANONICAL_HASH, f"dataset H1 hash mismatch: {ds_hash}"

    d1_hash = sha256_file(D1_PATH)
    h1_slice = load_slice_csv(H1_PATH)
    n_bars = len(h1_slice)
    d1_df = pd.read_csv(D1_PATH)

    # --- D1 bias timeline (PIT-safe) ---
    d1_times, d1_trend, pit_viol = build_d1_trend_timeline(d1_df)
    if pit_viol > 0:
        raise RuntimeError(f"PIT debt en trend D1: {pit_viol} violaciones FULL vs PREFIX -> BLOCKED")
    print(f"D1 timeline OK; PIT violations={pit_viol}; D1 range "
          f"{d1_times.iloc[0]} .. {d1_times.iloc[-1]}", flush=True)

    # --- run_sequential (mismo motor B1) ---
    cfg_seq = SeqConfig(structure_mode="lite", max_active_chains=4096, swing_left=SWING_LEFT)
    cfg_out = OutcomeConfig(horizon_bars=HORIZON_BARS, sl_buffer=SL_BUFFER, tie_policy="pessimistic")
    high = h1_slice["high"].to_numpy(float)
    low = h1_slice["low"].to_numpy(float)
    close = h1_slice["close"].to_numpy(float)
    times = list(h1_slice["time"])
    h1_dt = pd.to_datetime(h1_slice["time"], utc=True, errors="coerce")

    print("run_sequential (lite)...", flush=True)
    chains = run_sequential(h1_slice, cfg_seq, timeframe="H1")
    summary = summarize_chains(chains)
    swing_highs, swing_lows = _causal_swings(high, low, SWING_LEFT)

    candidates = [c for c in chains if len(c.nodes) >= DEPTH_MIN]
    by_status = {}
    for c in candidates:
        by_status[c.status] = by_status.get(c.status, 0) + 1

    seen = set()
    treatment = []
    for ch in candidates:
        anchor_node = ch.nodes[DEPTH_MIN - 1]
        assert anchor_node.stage is Stage.STRUCTURE
        sweep_node = ch.nodes[1]
        assert sweep_node.stage is Stage.SWEEP
        bar_i = int(anchor_node.bar)
        sweep_bar = int(sweep_node.bar)
        key = (bar_i, int(ch.direction))
        if key in seen or bar_i < WARMUP_BARS:
            continue
        seen.add(key)
        # REAL sweep wick (misma logica que B1 / exp_agentA_runner)
        extra = sweep_node.extra or {}
        sw_lo = float(low[sweep_bar]) if int(ch.direction) == 1 else None
        sw_hi = float(high[sweep_bar]) if int(ch.direction) == -1 else None
        a, b = sweep_bar, bar_i
        r_lo = float(np.min(low[a: b + 1]))
        r_hi = float(np.max(high[a: b + 1]))
        built = build_trade(int(ch.direction), bar_i, close, high, low, swing_lows, swing_highs,
                            None if sw_lo is None else float(sw_lo),
                            None if sw_hi is None else float(sw_hi),
                            r_lo, r_hi, cfg_out)
        if built is None:
            continue
        res = resolve_outcome(high, low, bar_i, built["levels"], cfg_out)
        # D1 bias al tiempo del anchor (PIT-safe: ultima vela D1 cerrada <= t)
        d1b = d1_trend_at(h1_dt.iloc[bar_i], d1_times, d1_trend)
        treatment.append({
            "group": "treatment", "chain_id": ch.chain_id,
            "direction": int(ch.direction), "structure_bar": bar_i,
            "sweep_bar": sweep_bar, "time": times[bar_i], "status": ch.status,
            "depth": len(ch.nodes),
            "entry": round(built["levels"].entry, 6), "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "sweep_wick_low": None if sw_lo is None else round(float(sw_lo), 6),
            "sweep_wick_high": None if sw_hi is None else round(float(sw_hi), 6),
            "range_low": round(r_lo, 6), "range_high": round(r_hi, 6),
            "d1_trend": d1b,
            **res,
        })

    m_unfiltered = compute_metrics(treatment, "chain_id")
    # --- SANITY: reproduccion de B1 sin filtro debe coincidir con B1 ---
    b1_ctrl = json.loads(B1_RAW_PATH.read_text(encoding="utf-8"))
    b1_n_closed = int(b1_ctrl["treatment"]["n_closed"])
    b1_mean_r = float(b1_ctrl["treatment"]["mean_R"])
    assert m_unfiltered["n_closed"] == b1_n_closed, (
        f"REPRODUCCION B1 FALLA: n_closed {m_unfiltered['n_closed']} != B1 {b1_n_closed}")
    assert abs(m_unfiltered["mean_r"] - b1_mean_r) < 1e-3, (
        f"REPRODUCCION B1 FALLA: mean_R {m_unfiltered['mean_r']} != B1 {b1_mean_r}")
    print(f"REPRODUCTION OK vs B1: n_closed={m_unfiltered['n_closed']} "
          f"mean_R={m_unfiltered['mean_r']}", flush=True)

    # --- FILTRO D1: mantener solo anchors alineados con sesgo D1 ---
    kept, dropped = [], []
    n_ranging = n_counter = 0
    for t in treatment:
        if passes_d1_filter(int(t["direction"]), t["d1_trend"]):
            kept.append(t)
        else:
            dropped.append(t)
            if t["d1_trend"] == "RANGING":
                n_ranging += 1
            else:
                n_counter += 1
    print(f"FILTER: total={len(treatment)} kept={len(kept)} "
          f"dropped={len(dropped)} (ranging={n_ranging}, counter={n_counter})", flush=True)

    # --- METRICAS B2 (tratamiento filtrado) ---
    m_b2 = compute_metrics(kept, "chain_id")

    # --- DELTA vs B1 (comparador canónico en disco) ---
    b1_wr = float(b1_ctrl["treatment"]["win_rate"])
    delta_exp = round(m_b2["mean_r"] - b1_mean_r, 4) if m_b2.get("mean_r") is not None else None
    delta_wr = round(m_b2["win_rate"] - b1_wr, 4) if m_b2.get("win_rate") is not None else None
    # delta CI (paired bootstrap, B2 subset vs B1 superset)
    boot = paired_delta_bootstrap(
        treatment,
        lambda t: passes_d1_filter(int(t["direction"]), t["d1_trend"]),
        seed=BOOTSTRAP_SEED, n=BOOTSTRAP_RESAMPLES)
    # excludes zero?
    de_ci = boot.get("delta_expectancy_ci95")
    htf_contributes = bool(de_ci and de_ci[0] > 0 and de_ci[1] > 0)

    elapsed = round(time.time() - t0, 2)

    # ===== RAW =====
    raw = {
        "schema_version": "1.0",
        "experiment": "EXP_B2",
        "role": "INCREMENTAL_D1_BIAS_FILTER (subconjunto filtrado de B1)",
        "hypothesis": (
            "H_B2: Anadir filtro de sesgo D1 (entra solo si sesgo D1 alinea direccion con "
            "la estructura) incrementa la expectancy del baseline LTF (B1) en R por "
            "operacion, bajo protocolo identico. Metrica: expectancy (mean_R). Gate: "
            "n_closed>=30. Comparador: B1."
        ),
        "dataset": {
            "symbol": "EURUSD", "exec_tf": "H1", "source": H1_REL,
            "range_start": RANGE_START, "range_end": RANGE_END, "bars": n_bars,
            "dataset_hash": ds_hash, "is_canonical": True, "origin": "csv",
            "note": "Dataset canonico H1 2019-2024 (mismo que B1).",
        },
        "htf_input": {
            "source": D1_REL, "tf": "D1", "rows": int(len(d1_df)),
            "dataset_hash": d1_hash, "bias_column": "trend (engine.market_features.build_features)",
            "pit_safe_full_vs_prefix_violations": int(pit_viol),
            "note": "Sesgo D1 por columna trend de build_features; PIT-verificado (0 violaciones).",
        },
        "dataset_hash": ds_hash,
        "code_commit": CODE_COMMIT,
        "config": {
            "structure_mode": "lite", "max_active_chains": 4096, "swing_left": SWING_LEFT,
            "depth_min": DEPTH_MIN, "anchor": "STRUCTURE_bar_close (depth>=4)",
            "sl_rule": "min(sweep_wick, broken_swing)-buffer (defensa pareja, 2 terminos)",
            "tp_rule": "measured_projection (fallback sancionado)",
            "sl_buffer": SL_BUFFER, "horizon_bars": HORIZON_BARS,
            "tie_policy": "pessimistic", "warmup_bars": WARMUP_BARS,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
            "htf_context": True,
            "htf_filter": "keep iff (dir==1 and D1 BULLISH) or (dir==-1 and D1 BEARISH); RANGING/counter dropped",
        },
        "fecha": datetime.now(timezone.utc).isoformat(),
        "treatment": {
            "n_closed": m_b2.get("n_closed"),
            "n_trades": m_b2.get("n_trades"),
            "n_open": m_b2.get("n_open"),
            "mean_R": m_b2.get("mean_r"),
            "median_R": m_b2.get("median_r"),
            "win_rate": m_b2.get("win_rate"),
            "profit_factor": m_b2.get("profit_factor"),
            "expectancy": m_b2.get("expectancy"),
            "drawdown": m_b2.get("drawdown"),
            "wilson_95": m_b2.get("win_rate_wilson95"),
            "bootstrap_ci_95": (m_b2.get("bootstrap") or {}).get("mean_r_ci"),
        },
        "baseline": None,
        "baseline_note": "El comparador de B2 es B1 (control LTF en disco). No se genera baseline propio.",
        "filter": {
            "method": "D1 trend alignment via engine.market_features.build_features(D1)['trend']",
            "total_treatment_trades": len(treatment),
            "kept": len(kept),
            "dropped": len(dropped),
            "dropped_ranging": n_ranging,
            "dropped_counter_trend": n_counter,
        },
        "delta_vs_B1": {
            "b1_expectancy": b1_mean_r,
            "b2_expectancy": m_b2.get("mean_r"),
            "delta_expectancy": delta_exp,
            "delta_expectancy_ci95": boot.get("delta_expectancy_ci95"),
            "b1_win_rate": b1_wr,
            "b2_win_rate": m_b2.get("win_rate"),
            "delta_win_rate": delta_wr,
            "delta_win_rate_ci95": boot.get("delta_win_rate_ci95"),
            "htf_contributes": htf_contributes,
            "note": "Delta CI por bootstrap por pares agrupado por chain_id (B2 subconjunto de B1).",
        },
        "motor_summary": summary,
        "chains_depth_ge4": {"depth_min": DEPTH_MIN, "n": len(candidates), "by_status": by_status},
        "protocol": {
            "leakage_check": (
                "OK: run_sequential en una sola pasada sobre rango acotado 2019-2024 "
                "(PIT-estable DENTRO del rango). El sesgo D1 se obtiene de build_features(D1)"
                "['trend'], columna PIT-verificada (FULL==PREFIX, 0 violaciones): se lee el "
                "valor en la ultima vela D1 cerrada <= t del anchor H1. Sin leakage futuro."
            ),
            "parameter_change": False,
            "data_integrity": {
                "symbol": "EURUSD", "exec_tf": "H1", "source": H1_REL,
                "range_start": RANGE_START, "range_end": RANGE_END, "bars": n_bars,
                "dataset_hash": ds_hash, "is_canonical": True, "origin": "csv",
                "htf_source": D1_REL, "htf_dataset_hash": d1_hash,
                "note": "Dataset canonico H1 verificado por SHA256; mismo motor/commit que B1.",
            },
        },
        "elapsed_s": elapsed,
    }

    # ===== AUDIT =====
    n_closed = m_b2.get("n_closed") or 0
    ci = (m_b2.get("bootstrap") or {}).get("mean_r_ci")
    ci_lower_gt_0 = bool(ci and len(ci) == 2 and ci[0] > 0)
    if n_closed < MIN_N_GATE:
        verdict = "BLOCKED"
    elif (m_b2.get("mean_r") or 0) > 0 and ci_lower_gt_0:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    audit = {
        "schema_version": "1.0",
        "experiment": "EXP_B2",
        "role": "INCREMENTAL_D1_BIAS_FILTER (subconjunto filtrado de B1)",
        "code_commit": CODE_COMMIT,
        "date": datetime.now(timezone.utc).isoformat(),
        "gate": {
            "n_ge_30": bool(n_closed >= MIN_N_GATE),
            "expectancy_gt_0": bool((m_b2.get("mean_r") or 0) > 0),
            "ci_lower_gt_0": ci_lower_gt_0,
        },
        "incremental_hypothesis": {
            "description": "HTF aporta si delta expectancy IC95 excluye 0 frente a B1.",
            "delta_expectancy": delta_exp,
            "delta_expectancy_ci95": boot.get("delta_expectancy_ci95"),
            "htf_contributes": htf_contributes,
            "verdict": "HTF_APORTA" if htf_contributes else "FAIL_INCREMENTAL",
        },
        "protocol": {
            "leakage_check": raw["protocol"]["leakage_check"],
            "parameter_change": False,
            "data_integrity": raw["protocol"]["data_integrity"],
        },
        "verdict": verdict,
        "rationale": (
            "mecanico: PASS iff n_closed>=30 AND expectancy(mean_R)>0 AND bootstrap CI95 "
            "lower>0; BLOCKED si n_closed<30; FAIL en otro caso. El veredicto incremental "
            "('HTF aporta') es independiente: requiere delta expectancy IC95 excluya 0 "
            "frente a B1 (FAIL_INCREMENTAL si no)."
        ),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(f"WROTE {RAW_PATH}", flush=True)
    print(f"WROTE {AUDIT_PATH}", flush=True)
    print(json.dumps({
        "experiment": "EXP_B2",
        "verdict": verdict,
        "treatment": {k: m_b2.get(k) for k in ("n_closed", "n_trades", "n_open",
                    "win_rate", "mean_r", "expectancy", "profit_factor", "drawdown")},
        "b2_bootstrap_ci": ci,
        "filter": raw["filter"],
        "delta_vs_B1": raw["delta_vs_B1"],
        "reproduction_vs_B1": {"n_closed": m_unfiltered["n_closed"], "mean_R": m_unfiltered["mean_r"]},
        "elapsed_s": elapsed,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
