#!/usr/bin/env python3
"""MICRO-AGENTE B4 — INCREMENTALIDAD + sesgo D1 Y H4 top-down (experimento B4).

H_B4: 'Anadir filtro de sesgo D1 Y H4 (entra solo si AMBOS alinean direccion
con la estructura, top-down D1->H4->H1) incrementa la expectancy del baseline
LTF (B1) en R por operacion, bajo protocolo identico. Metrica: expectancy
(mean_R). Gate: n_closed>=30. Comparador: B1.'

Diseno estricto (contrato B1/B2/B3/B4):
- MISMO motor run_sequential(structure_mode="lite") que B1/B2/B3; MISMO commit
  de motor (daef67cf; engine/ es byte-identico entre daef67cf y HEAD).
- MISMA construccion de trade que B1/B2/B3 (anchor = nodo STRUCTURE
  (ch.nodes[3]), mecha de sweep REAL (low[sweep_bar] si long / high[sweep_bar]
  si short), SL estructural de 2 terminos min(mecha sweep, swing roto)-buffer,
  TP measured_projection, horizonte 200, tie_policy=pessimistic). NO se cambia
  SL/TP.
- UNICO cambio permitido: FILTRO de entrada por sesgo D1 Y H4 (top-down). Se
  usan las columnas 'trend' de engine.market_features.build_features(D1) y
  build_features(H4) (BULLISH/BEARISH/RANGING), PIT-verificadas (FULL==PREFIX,
  0 violaciones). El filtro mantiene un anchor solo si (dir==1 y D1 BULLISH y H4
  BULLISH) o (dir==-1 y D1 BEARISH y H4 BEARISH): AMBOS deben alinear
  (top-down D1->H4). RANGING o contratendencia en cualquiera se descarta. B4 es
  un subconjunto filtrado de B1 (y de B2/B3).
- Determinismo: el tratamiento no usa RNG. Se ASSERTA que la reproduccion sin
  filtro coincide con B1 (n_closed=211, mean_R=0.2499) para garantizar
  'mismo motor, mismo commit'.
- Delta vs B1 con IC: bootstrap POR PARES agrupado por chain_id (B4* subconjunto
  de B1* en cada remuestreo) -> CI95 de Delta_expectancy y Delta_win_rate que
  respeta la dependencia subconjunto/superconjunto.

Salida: reports/audits/EXP_B4_raw.json + reports/audits/EXP_B4_audit.json
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

# ---- Protocolo fijo (identico a exp_agentA_runner / B1 / B2 / B3) ----
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
CODE_COMMIT = "daef67cf212c4432c6e5e3a2b7c6cd404982059b"  # mismo motor que B1/B2/B3

H1_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv"
H4_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H4.csv"
D1_REL = "datasets/eurusd_dukascopy_20y/EURUSD_D1.csv"
H1_PATH = ROOT / H1_REL
H4_PATH = ROOT / H4_REL
D1_PATH = ROOT / D1_REL
CANONICAL_HASH = "2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022"

REPORT_DIR = ROOT / "reports" / "audits"
RAW_PATH = REPORT_DIR / "EXP_B4_raw.json"
AUDIT_PATH = REPORT_DIR / "EXP_B4_audit.json"

# B1 reference (control) — leido del disco como comparador canonico.
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
    """IDENTICO a exp_agentA_runner.build_trade (B1/B2/B3)."""
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
    """IDENTICO a exp_agentA_runner.compute_metrics (B1/B2/B3)."""
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


def build_trend_timeline(df: pd.DataFrame, label: str):
    """Construye el timeline de sesgo (columna 'trend' de build_features).

    PIT-safe: build_features en el frame completo; la columna 'trend' se
    verifica FULL==PREFIX (muestreo 5 barras). Devuelve
    (times_sorted, trend_list, viol).
    """
    ann = build_features(df)
    if "trend" not in ann.columns:
        raise RuntimeError(f"build_features({label}) no expone columna 'trend'")
    times = pd.to_datetime(ann["time"], utc=True, errors="coerce")
    n = len(ann)
    idxs = [max(0, min(n - 1, int(n * f))) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    viol = 0
    for i in idxs:
        pref = build_features(df.iloc[: i + 1].copy())
        if str(ann["trend"].iloc[i]) != str(pref["trend"].iloc[i]):
            viol += 1
    return times.sort_values().reset_index(drop=True), ann["trend"].reset_index(drop=True), viol


def trend_at(h1_time: pd.Timestamp, times, trend) -> str:
    """Sesgo cerrado mas reciente <= h1_time (PIT-safe lookup)."""
    j = bisect_right(times, h1_time) - 1
    if j < 0:
        return "RANGING"
    return str(trend.iloc[j])


def passes_filter(direction: int, d1_trend: str, h4_trend: str) -> bool:
    """Filtro B4 top-down: long<->BULLISH en AMBOS (D1 y H4); short<->BEARISH en
    AMBOS; cualquier RANGING o contratendencia descarta."""
    if direction == 1:
        return d1_trend == "BULLISH" and h4_trend == "BULLISH"
    if direction == -1:
        return d1_trend == "BEARISH" and h4_trend == "BEARISH"
    return False


def paired_delta_bootstrap(trades_all: list[dict], seed=42, n=2000):
    """Bootstrap POR PARES agrupado por chain_id.

    Cada remuestreo: extrae clusters (chain_id) con reemplazo; B1* = todos los
    trades cerrados del resample; B4* = los que pasan el filtro D1+H4. Delta* =
    media(B4*) - media(B1*) y wr(B4*) - wr(B1*). El CI respeta que B4 es
    subconjunto de B1 (dependencia).
    """
    closed = [t for t in trades_all if t.get("exit_r") is not None]
    if not closed:
        return {"delta_expectancy_ci95": None, "delta_win_rate_ci95": None, "n_boot": 0}
    by_chain: dict[str, list[dict]] = {}
    for t in closed:
        by_chain.setdefault(str(t["chain_id"]), []).append(t)
    chains = list(by_chain.values())
    rng = np.random.default_rng(seed)
    d_r, d_wr = [], []
    for _ in range(n):
        pick = rng.integers(0, len(chains), size=len(chains))
        b1_rs, b4_rs = [], []
        b1_w, b4_w = 0, 0
        b1_n, b4_n = 0, 0
        for idx in pick:
            grp = chains[idx]
            for t in grp:
                r = float(t["exit_r"])
                b1_rs.append(r); b1_n += 1
                if r > 0:
                    b1_w += 1
                if passes_filter(int(t["direction"]), t["d1_trend"], t["h4_trend"]):
                    b4_rs.append(r); b4_n += 1
                    if r > 0:
                        b4_w += 1
        if not b1_rs:
            continue
        mean_b1 = float(np.mean(b1_rs))
        mean_b4 = float(np.mean(b4_rs)) if b4_rs else 0.0
        d_r.append(mean_b4 - mean_b1)
        wr_b1 = b1_w / b1_n if b1_n else 0.0
        wr_b4 = b4_w / b4_n if b4_n else 0.0
        d_wr.append(wr_b4 - wr_b1)
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

    h4_hash = sha256_file(H4_PATH)
    d1_hash = sha256_file(D1_PATH)
    h1_slice = load_slice_csv(H1_PATH)
    n_bars = len(h1_slice)
    h4_df = pd.read_csv(H4_PATH)
    d1_df = pd.read_csv(D1_PATH)

    # --- HTF bias timelines (PIT-safe) ---
    h4_times, h4_trend, pit_h4 = build_trend_timeline(h4_df, "H4")
    if pit_h4 > 0:
        raise RuntimeError(f"PIT debt en trend H4: {pit_h4} violaciones FULL vs PREFIX -> BLOCKED")
    d1_times, d1_trend, pit_d1 = build_trend_timeline(d1_df, "D1")
    if pit_d1 > 0:
        raise RuntimeError(f"PIT debt en trend D1: {pit_d1} violaciones FULL vs PREFIX -> BLOCKED")
    print(f"H4 timeline OK; PIT violations={pit_h4}; H4 range {h4_times.iloc[0]} .. {h4_times.iloc[-1]}", flush=True)
    print(f"D1 timeline OK; PIT violations={pit_d1}; D1 range {d1_times.iloc[0]} .. {d1_times.iloc[-1]}", flush=True)

    # --- run_sequential (mismo motor B1/B2/B3) ---
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
        # REAL sweep wick (misma logica que B1/B2/B3 / exp_agentA_runner)
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
        # HTF bias al tiempo del anchor (PIT-safe: ultima vela cerrada <= t)
        d1b = trend_at(h1_dt.iloc[bar_i], d1_times, d1_trend)
        h4b = trend_at(h1_dt.iloc[bar_i], h4_times, h4_trend)
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
            "h4_trend": h4b,
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

    # --- FILTRO D1+H4 (top-down AND): mantener solo anchors alineados en AMBOS ---
    kept, dropped = [], []
    n_d1_out = n_h4_out = n_both_out = 0
    for t in treatment:
        d1 = t["d1_trend"]
        h4 = t["h4_trend"]
        d1_ok = (int(t["direction"]) == 1 and d1 == "BULLISH") or (int(t["direction"]) == -1 and d1 == "BEARISH")
        h4_ok = (int(t["direction"]) == 1 and h4 == "BULLISH") or (int(t["direction"]) == -1 and h4 == "BEARISH")
        if d1_ok and h4_ok:
            kept.append(t)
        else:
            dropped.append(t)
            if not d1_ok:
                n_d1_out += 1
            if not h4_ok:
                n_h4_out += 1
            if not (d1_ok or h4_ok):
                n_both_out += 1
    print(f"FILTER: total={len(treatment)} kept={len(kept)} "
          f"dropped={len(dropped)} (d1_out={n_d1_out}, h4_out={n_h4_out}, both_out={n_both_out})", flush=True)

    # --- METRICAS B4 (tratamiento filtrado) ---
    m_b4 = compute_metrics(kept, "chain_id")

    # --- DELTA vs B1 (comparador canonico en disco) ---
    b1_wr = float(b1_ctrl["treatment"]["win_rate"])
    delta_exp = round(m_b4["mean_r"] - b1_mean_r, 4) if m_b4.get("mean_r") is not None else None
    delta_wr = round(m_b4["win_rate"] - b1_wr, 4) if m_b4.get("win_rate") is not None else None
    # delta CI (paired bootstrap, B4 subset vs B1 superset)
    boot = paired_delta_bootstrap(treatment, seed=BOOTSTRAP_SEED, n=BOOTSTRAP_RESAMPLES)
    # excludes zero?
    de_ci = boot.get("delta_expectancy_ci95")
    htf_contributes = bool(de_ci and de_ci[0] > 0 and de_ci[1] > 0)

    elapsed = round(time.time() - t0, 2)

    # ===== RAW =====
    raw = {
        "schema_version": "1.0",
        "experiment": "EXP_B4",
        "role": "INCREMENTAL_D1_AND_H4_TOPDOWN_BIAS_FILTER (subconjunto filtrado de B1)",
        "hypothesis": (
            "H_B4: Anadir filtro de sesgo D1 Y H4 (entra solo si AMBOS alinean direccion con "
            "la estructura, top-down D1->H4->H1) incrementa la expectancy del baseline LTF (B1) "
            "en R por operacion, bajo protocolo identico. Metrica: expectancy (mean_R). Gate: "
            "n_closed>=30. Comparador: B1."
        ),
        "dataset": {
            "symbol": "EURUSD", "exec_tf": "H1", "source": H1_REL,
            "range_start": RANGE_START, "range_end": RANGE_END, "bars": n_bars,
            "dataset_hash": ds_hash, "is_canonical": True, "origin": "csv",
            "note": "Dataset canonico H1 2019-2024 (mismo que B1/B2/B3).",
        },
        "htf_input": {
            "d1": {
                "source": D1_REL, "tf": "D1", "rows": int(len(d1_df)),
                "dataset_hash": d1_hash, "bias_column": "trend (engine.market_features.build_features)",
                "pit_safe_full_vs_prefix_violations": int(pit_d1),
                "note": "Sesgo D1 por columna trend de build_features; PIT-verificado (0 violaciones).",
            },
            "h4": {
                "source": H4_REL, "tf": "H4", "rows": int(len(h4_df)),
                "dataset_hash": h4_hash, "bias_column": "trend (engine.market_features.build_features)",
                "pit_safe_full_vs_prefix_violations": int(pit_h4),
                "note": "Sesgo H4 por columna trend de build_features; PIT-verificado (0 violaciones).",
            },
            "top_down_logic": "keep iff (dir==1 and D1 BULLISH and H4 BULLISH) or (dir==-1 and D1 BEARISH and H4 BEARISH); RANGING/counter en cualquiera descarta (AND top-down).",
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
            "htf_filter": "keep iff (dir==1 and D1 BULLISH and H4 BULLISH) or (dir==-1 and D1 BEARISH and H4 BEARISH); RANGING/counter dropped (top-down AND)",
        },
        "fecha": datetime.now(timezone.utc).isoformat(),
        "treatment": {
            "n_closed": m_b4.get("n_closed"),
            "n_trades": m_b4.get("n_trades"),
            "n_open": m_b4.get("n_open"),
            "mean_R": m_b4.get("mean_r"),
            "median_R": m_b4.get("median_r"),
            "win_rate": m_b4.get("win_rate"),
            "profit_factor": m_b4.get("profit_factor"),
            "expectancy": m_b4.get("expectancy"),
            "drawdown": m_b4.get("drawdown"),
            "wilson_95": m_b4.get("win_rate_wilson95"),
            "bootstrap_ci_95": (m_b4.get("bootstrap") or {}).get("mean_r_ci"),
        },
        "baseline": None,
        "baseline_note": "El comparador de B4 es B1 (control LTF en disco). No se genera baseline propio.",
        "filter": {
            "method": "D1+H4 trend alignment via engine.market_features.build_features(D1/H4)['trend'] (top-down AND)",
            "total_treatment_trades": len(treatment),
            "kept": len(kept),
            "dropped": len(dropped),
            "dropped_d1_out": n_d1_out,
            "dropped_h4_out": n_h4_out,
            "dropped_both_out": n_both_out,
        },
        "delta_vs_B1": {
            "b1_expectancy": b1_mean_r,
            "b4_expectancy": m_b4.get("mean_r"),
            "delta_expectancy": delta_exp,
            "delta_expectancy_ci95": boot.get("delta_expectancy_ci95"),
            "b1_win_rate": b1_wr,
            "b4_win_rate": m_b4.get("win_rate"),
            "delta_win_rate": delta_wr,
            "delta_win_rate_ci95": boot.get("delta_win_rate_ci95"),
            "htf_contributes": htf_contributes,
            "note": "Delta CI por bootstrap por pares agrupado por chain_id (B4 subconjunto de B1).",
        },
        "motor_summary": summary,
        "chains_depth_ge4": {"depth_min": DEPTH_MIN, "n": len(candidates), "by_status": by_status},
        "protocol": {
            "leakage_check": (
                "OK: run_sequential en una sola pasada sobre rango acotado 2019-2024 "
                "(PIT-estable DENTRO del rango). Los sesgos D1 y H4 se obtienen de "
                "build_features(D1)['trend'] y build_features(H4)['trend'], columnas "
                "PIT-verificadas (FULL==PREFIX, 0 violaciones): se lee el valor en la "
                "ultima vela D1/H4 cerrada <= t del anchor H1. Sin leakage futuro."
            ),
            "parameter_change": False,
            "data_integrity": {
                "symbol": "EURUSD", "exec_tf": "H1", "source": H1_REL,
                "range_start": RANGE_START, "range_end": RANGE_END, "bars": n_bars,
                "dataset_hash": ds_hash, "is_canonical": True, "origin": "csv",
                "htf_d1_source": D1_REL, "htf_d1_dataset_hash": d1_hash,
                "htf_h4_source": H4_REL, "htf_h4_dataset_hash": h4_hash,
                "note": "Dataset canonico H1 verificado por SHA256; mismo motor/commit que B1/B2/B3.",
            },
        },
        "elapsed_s": elapsed,
    }

    # ===== AUDIT =====
    n_closed = m_b4.get("n_closed") or 0
    ci = (m_b4.get("bootstrap") or {}).get("mean_r_ci")
    ci_lower_gt_0 = bool(ci and len(ci) == 2 and ci[0] > 0)
    if n_closed < MIN_N_GATE:
        verdict = "BLOCKED"
    elif (m_b4.get("mean_r") or 0) > 0 and ci_lower_gt_0:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    audit = {
        "schema_version": "1.0",
        "experiment": "EXP_B4",
        "role": "INCREMENTAL_D1_AND_H4_TOPDOWN_BIAS_FILTER (subconjunto filtrado de B1)",
        "code_commit": CODE_COMMIT,
        "date": datetime.now(timezone.utc).isoformat(),
        "gate": {
            "n_ge_30": bool(n_closed >= MIN_N_GATE),
            "expectancy_gt_0": bool((m_b4.get("mean_r") or 0) > 0),
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
        "experiment": "EXP_B4",
        "verdict": verdict,
        "treatment": {k: m_b4.get(k) for k in ("n_closed", "n_trades", "n_open",
                    "win_rate", "mean_r", "expectancy", "profit_factor", "drawdown")},
        "b4_bootstrap_ci": ci,
        "filter": raw["filter"],
        "delta_vs_B1": raw["delta_vs_B1"],
        "reproduction_vs_B1": {"n_closed": m_unfiltered["n_closed"], "mean_R": m_unfiltered["mean_r"]},
        "elapsed_s": elapsed,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
