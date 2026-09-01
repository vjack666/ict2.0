#!/usr/bin/env python3
"""AGENTE C — FALSACION. Harness reutilizable para los 5 experimentos.

Replica EXACTAMENTE la logica de tratamiento (depth>=4 @ BOS-lite) del script
base exp_sequential_expectancy_depth4_lite.py: mismo motor (run_sequential
structure_mode='lite', max_active_chains=4096, swing_left=3), mismos criterios
de SL/TP estructural, horizonte, bootstrap (2000, seed 42), wilson, baseline
semilla 42. NO se cambia ningun parametro tras ver resultados.

Produce, por experimento:
  A) RAW   reports/audits/experiments/current_batch/EXP_C<NN>_raw.json
  B) AUDIT reports/audits/experiments/current_batch/EXP_C<NN>_audit.json  (gate mecanico + protocolo + veredicto)

GATE MECANICO (lo calcula el gate, no el deseo de refutar):
  n_closed < 30                         -> BLOCKED
  mean_r>0 y CI95 low > 0               -> PASS   (edge ROBUSTO OOS, no falsificado)
  lo contrario                          -> FAIL   (edge ROTO OOS, falsacion exitosa)
  datos structuralmente inusables       -> INVALID

H_C (congelada): el edge de expectancy positiva depth>=4 es ROBUSTO fuera de
la muestra EURUSD 2019-2024.
"""
from __future__ import annotations

import hashlib
import json
import time
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from engine.detectors.fvg import detect_fvg
from engine.sequential_events import (  # noqa: E402
    SeqConfig,
    Stage,
    _causal_swings,
    run_sequential,
    summarize_chains,
)
from engine.sequential_outcome import (  # noqa: E402
    OutcomeConfig,
    TradeLevels,
    bootstrap_clustered,
    measured_projection_tp,
    resolve_outcome,
    structural_stop,
    wilson_interval,
)

# ---- INVARIANTES (idénticos al experimento base) ----
MIN_DEPTH = 4
HORIZON_BARS = 200
SL_BUFFER = 0.0001
SWING_LEFT = 3
WARMUP_BARS = 20
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
BASELINE_SEED = 42
MIN_N_GATE = 30
CODE_COMMIT = "daef67cf212c4432c6e5e3a2b7c6cd404982059b"

PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.01}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_source(symbol: str, source_kind: str, path: Path,
                range_start: str, range_end: str):
    """Devuelve (slice_df, time_strings, meta). Normaliza CSV/parquet."""
    if source_kind == "csv":
        df = pd.read_csv(path)
        ts = pd.to_datetime(df["time"]).dt.tz_localize(None)
    else:
        df = pd.read_parquet(path)
        ts = pd.to_datetime(df["time"]).dt.tz_localize(None)
    mask = (ts >= pd.Timestamp(range_start)) & (ts <= pd.Timestamp(range_end) + pd.Timedelta(hours=23, minutes=59, seconds=59))
    sl = df.loc[mask].sort_values("time").reset_index(drop=True)
    # normaliza time a string para etiquetas
    if source_kind == "csv":
        times = sl["time"].astype(str).tolist()
    else:
        times = pd.to_datetime(sl["time"]).dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
    return sl, times


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
    else:
        sl = structural_stop(-1, sweep_extreme=sweep_wick_high,
                             broken_swing=last_confirmed_swing(swing_highs, entry_bar),
                             buffer=cfg.sl_buffer)
    tp = measured_projection_tp(direction, range_hi, range_lo)
    if sl is None or tp is None:
        return None
    levels = TradeLevels(direction=direction, entry=entry, sl=float(sl), tp=float(tp))
    return {"levels": levels, "valid": levels.is_valid()}


def apply_costs_to_r(trade: dict, symbol: str, spread_pip: float, slip_pip: float,
                     outcome: str) -> float | None:
    """Recomputa el R neto de un trade ya resuelto (TP/SL) con costes realistas.

    - entry se llena en su contra por (spread+slip) pips
    - stop se llena en su contra por slip pips (limit en TP sin slip)
    - comision = 0 (no hay dato de comision por lote en el dataset)
    Solo afecta trades cerrados. OPEN queda sin cambios (None).
    """
    if outcome not in ("TP", "SL") or trade.get("exit_r") is None:
        return None
    e = trade["entry"]; s = trade["sl"]; t = trade["tp"]; d = trade["direction"]
    pip = PIP[symbol]
    adverse = (spread_pip + slip_pip) * pip
    exit_slip = slip_pip * pip
    if d == 1:
        e2 = e + adverse; s2 = s - exit_slip; t2 = t
        risk2 = e2 - s2
        r = (t2 - e2) / risk2 if outcome == "TP" else (s2 - e2) / risk2
    else:
        e2 = e - adverse; s2 = s + exit_slip; t2 = t
        risk2 = s2 - e2
        r = (e2 - t2) / risk2 if outcome == "TP" else (e2 - s2) / risk2
    return float(r)


def metrics(trades, cluster_key):
    closed = [t for t in trades if t.get("exit_r") is not None]
    wins = sum(1 for t in closed if float(t["exit_r"]) > 0)
    rs = [float(t["exit_r"]) for t in closed]
    out = {
        "n_trades": len(trades),
        "n_closed": len(closed),
        "n_open": len([t for t in trades if t.get("outcome") == "OPEN"]),
        "n_invalid_levels": len([t for t in trades if t.get("outcome") == "INVALID"]),
        "wins": wins,
        "losses": len(closed) - wins,
    }
    if closed:
        wr = wins / len(closed)
        lo, hi = wilson_interval(wins, len(closed))
        out.update({
            "win_rate": round(wr, 4),
            "win_rate_wilson95": [round(lo, 4), round(hi, 4)],
            "mean_r": round(float(np.mean(rs)), 4),
            "median_r": round(float(np.median(rs)), 4),
            "std_r": round(float(np.std(rs, ddof=1)) if len(rs) > 1 else 0.0, 4),
            "min_r": round(float(np.min(rs)), 4),
            "max_r": round(float(np.max(rs)), 4),
        })
    else:
        out.update({"win_rate": None, "win_rate_wilson95": None, "mean_r": None})
    out["bootstrap_clustered"] = bootstrap_clustered(
        trades, cluster_key, n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
    return out


def build_treatment(slice_df, times, high, low, close, cfg_seq, cfg_out):
    """Replica fiel del tratamiento depth>=4 del script base."""
    chains = run_sequential(slice_df, cfg_seq, timeframe="H1")
    summary = summarize_chains(chains)
    swing_highs, swing_lows = _causal_swings(high, low, SWING_LEFT)
    candidates = [c for c in chains if len(c.nodes) >= MIN_DEPTH]
    by_status = {}
    for c in candidates:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    seen = set(); dedup_skipped = 0; treatment = []; spans = []
    for ch in candidates:
        struct_node = ch.nodes[MIN_DEPTH - 1]
        assert struct_node.stage is Stage.STRUCTURE
        sweep_node = ch.nodes[1]
        assert sweep_node.stage is Stage.SWEEP
        bar_i = int(struct_node.bar); sweep_bar = int(sweep_node.bar)
        key = (bar_i, int(ch.direction))
        if key in seen or bar_i < WARMUP_BARS:
            dedup_skipped += 1; continue
        seen.add(key)
        extra = sweep_node.extra or {}
        sw_lo = extra.get("sweep_low"); sw_hi = extra.get("sweep_high")
        a, b = sweep_bar, bar_i
        r_lo = float(np.min(low[a:b + 1])); r_hi = float(np.max(high[a:b + 1]))
        built = build_trade(int(ch.direction), bar_i, close, high, low,
                            swing_lows, swing_highs,
                            None if sw_lo is None else float(sw_lo),
                            None if sw_hi is None else float(sw_hi),
                            r_lo, r_hi, cfg_out)
        if built is None:
            continue
        spans.append(bar_i - sweep_bar)
        res = resolve_outcome(high, low, bar_i, built["levels"], cfg_out)
        treatment.append({
            "group": "treatment", "chain_id": ch.chain_id,
            "direction": int(ch.direction), "structure_bar": bar_i,
            "sweep_bar": sweep_bar, "time": times[bar_i], "status": ch.status,
            "depth": len(ch.nodes),
            "entry": round(built["levels"].entry, 6),
            "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "sweep_wick_low": None if sw_lo is None else round(float(sw_lo), 6),
            "sweep_wick_high": None if sw_hi is None else round(float(sw_hi), 6),
            "range_low": round(r_lo, 6), "range_high": round(r_hi, 6),
            **res,
        })
    return treatment, summary, candidates, by_status, dedup_skipped, spans, swing_highs, swing_lows


def build_baseline(slice_df, times, high, low, close, cfg_out, n_treatment_valid, spans,
                   swing_lows, swing_highs):
    """Random-FVG baseline con la MISMA logica de SL/TP (del script base)."""
    records = slice_df[["open", "high", "low", "close"]].copy()
    records["time"] = list(range(len(slice_df)))
    fvgs = detect_fvg(records.to_dict("records"), timeframe="SEQ", symbol="")
    fvg_events = []; f_seen = set()
    for f in fvgs:
        bi = f.confirmation_bar if f.confirmation_bar is not None else f.bar_index
        if bi is None or int(bi) < WARMUP_BARS:
            continue
        k = (int(bi), int(f.direction))
        if k in f_seen:
            continue
        f_seen.add(k); fvg_events.append(k)
    rng = np.random.default_rng(BASELINE_SEED)
    order = rng.permutation(len(fvg_events))
    k_window = int(np.median(spans)) if spans else 8
    baseline = []
    for idx in order:
        if len(baseline) >= n_treatment_valid:
            break
        cb, direction = fvg_events[idx]
        a = max(0, cb - k_window + 1)
        r_lo = float(np.min(low[a:cb + 1])); r_hi = float(np.max(high[a:cb + 1]))
        built = build_trade(direction, cb, close, high, low, swing_lows, swing_highs,
                            None, None, r_lo, r_hi, cfg_out)
        if built is None:
            continue
        res = resolve_outcome(high, low, cb, built["levels"], cfg_out)
        baseline.append({
            "group": "baseline", "chain_id": f"BASE_{cb}_{direction}",
            "direction": int(direction), "structure_bar": cb, "time": times[cb],
            "depth": 0, "fvg_window_bars": k_window,
            "entry": round(built["levels"].entry, 6),
            "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "range_low": round(r_lo, 6), "range_high": round(r_hi, 6),
            **res,
        })
    return baseline, k_window


def mechanical_gate(m: dict) -> str:
    if m.get("n_closed") is None or m["n_closed"] < MIN_N_GATE:
        return "BLOCKED"
    mr = m.get("mean_r")
    ci = (m.get("bootstrap_clustered") or {}).get("mean_r_ci")
    ci_low = ci[0] if ci else None
    if mr is None:
        return "BLOCKED"
    if mr > 0 and (ci_low is not None) and ci_low > 0:
        return "PASS"   # edge robusto OOS (no falsificado)
    return "FAIL"       # edge roto OOS (falsacion exitosa)


# ---- CONFIGURACION DE LOS 5 EXPERIMENTOS ----
def configs():
    base = ROOT / "datasets" / "eurusd_dukascopy_20y" / "EURUSD_H1.csv"
    gbp = ROOT / "data" / "raw" / "GBPUSD" / "GBPUSD_H1.parquet"
    xau = ROOT / "data" / "raw" / "XAUUSD" / "XAUUSD_H1.parquet"
    return [
        dict(id="EXP_C1", symbol="GBPUSD", kind="parquet", path=gbp,
             range_start="2019-01-01", range_end="2024-12-31",
             costs=False, hash="a9661b4a24aacdd8", origin="MT5 parquet"),
        dict(id="EXP_C2", symbol="XAUUSD", kind="parquet", path=xau,
             range_start="2019-01-01", range_end="2024-12-31",
             costs=False, hash="89bdf3c62286bff0", origin="MT5 parquet"),
        dict(id="EXP_C3", symbol="EURUSD", kind="csv", path=base,
             range_start="2025-01-01", range_end="2025-12-31",
             costs=False, hash="2dbb5757", origin="Dukascopy 20Y CSV", oos=True),
        dict(id="EXP_C4", symbol="EURUSD", kind="csv", path=base,
             range_start="2019-01-01", range_end="2024-12-31",
             costs=True, hash="2dbb5757", origin="Dukascopy 20Y CSV",
             spread_pip=0.5, slip_pip=0.3),
        dict(id="EXP_C5", symbol="EURUSD", kind="csv", path=base,
             range_start="2019-01-01", range_end="2024-12-31",
             costs=False, hash="2dbb5757", origin="Dukascopy 20Y CSV",
             walk_forward=True),
    ]


WF_WINDOWS = [
    ("W1", "2019-01-01", "2020-06-30"),
    ("W2", "2020-07-01", "2021-12-31"),
    ("W3", "2022-01-01", "2023-06-30"),
    ("W4", "2023-07-01", "2024-12-31"),
]


def run_one(cfg):
    """Devuelve dict con raw + gate + protocol + verdict."""
    t0 = time.time()
    out = {"config_id": cfg["id"], "symbol": cfg["symbol"]}
    if cfg.get("walk_forward"):
        per_window = []
        for wname, ws, we in WF_WINDOWS:
            sl, times = load_source(cfg["symbol"], cfg["kind"], cfg["path"], ws, we)
            high = sl["high"].to_numpy(float); low = sl["low"].to_numpy(float)
            close = sl["close"].to_numpy(float)
            cfg_seq = SeqConfig(structure_mode="lite", max_active_chains=4096, swing_left=SWING_LEFT)
            cfg_out = OutcomeConfig(horizon_bars=HORIZON_BARS, sl_buffer=SL_BUFFER, tie_policy="pessimistic")
            tr, summ, cand, bstat, ded, spans, _, _ = build_treatment(sl, times, high, low, close, cfg_seq, cfg_out)
            m = metrics(tr, "chain_id")
            per_window.append({
                "window": wname, "range": [ws, we], "bars": len(sl),
                "n_trades": m["n_trades"], "n_closed": m["n_closed"],
                "win_rate": m.get("win_rate"), "mean_r": m.get("mean_r"),
                "mean_r_ci": (m.get("bootstrap_clustered") or {}).get("mean_r_ci"),
                "gate": mechanical_gate(m),
            })
        # tendencia temporal: slope de mean_r vs indice de ventana
        xs = np.arange(len(per_window))
        ys = np.array([w["mean_r"] if w["mean_r"] is not None else np.nan for w in per_window], float)
        valid = ~np.isnan(ys)
        slope = float(np.polyfit(xs[valid], ys[valid], 1)[0]) if valid.sum() >= 2 else None
        n_closed_all = sum(w["n_closed"] for w in per_window)
        any_broken = any(w["gate"] == "FAIL" for w in per_window)
        decay = bool(slope is not None and slope < 0 and any_broken)
        gate = "FAIL" if any_broken else ("PASS" if all(w["gate"] == "PASS" for w in per_window) else "FAIL")
        out["walk_forward"] = {
            "windows": per_window,
            "trend_slope_mean_r_per_window": round(slope, 5) if slope is not None else None,
            "temporal_decay_detected": decay,
            "any_window_broken": any_broken,
            "n_closed_total": n_closed_all,
        }
        out["metrics_treatment"] = {"note": "see walk_forward.windows", "n_closed_total": n_closed_all}
        out["gate"] = gate
        out["verdict"] = (
            f"Walk-forward: {sum(1 for w in per_window if w['gate']=='PASS')}/{len(per_window)} ventanas con edge positivo. "
            f"Pendiente de tiempo slope={slope}. "
            + ("INESTABILIDAD TEMPORAL: alguna ventana cae (edge roto OOS)." if any_broken
               else "Edge se mantiene en todas las ventanas (no falsificado por WF).")
        )
        out["raw_metrics"] = {"windows": per_window}
        out["elapsed_s"] = round(time.time() - t0, 2)
        return out

    # --- Experimentos C1,C2,C3,C4 (single range) ---
    sl, times = load_source(cfg["symbol"], cfg["kind"], cfg["path"],
                            cfg["range_start"], cfg["range_end"])
    high = sl["high"].to_numpy(float); low = sl["low"].to_numpy(float)
    close = sl["close"].to_numpy(float)
    cfg_seq = SeqConfig(structure_mode="lite", max_active_chains=4096, swing_left=SWING_LEFT)
    cfg_out = OutcomeConfig(horizon_bars=HORIZON_BARS, sl_buffer=SL_BUFFER, tie_policy="pessimistic")
    tr, summ, cand, bstat, ded, spans, swing_highs, swing_lows = build_treatment(sl, times, high, low, close, cfg_seq, cfg_out)

    # C4: correr tambien SIN coste (gross) para delta neto
    if cfg.get("costs"):
        tr_gross, _, _, _, _, _, _, _ = build_treatment(sl, times, high, low, close, cfg_seq, cfg_out)
        m_gross = metrics(tr_gross, "chain_id")
    else:
        m_gross = None

    # aplicar costes (C4) recomputando R sobre trades ya resueltos
    if cfg.get("costs"):
        spread_pip = cfg.get("spread_pip", 0.5); slip_pip = cfg.get("slip_pip", 0.3)
        for t in tr:
            if t.get("exit_r") is None:
                continue
            r_net = apply_costs_to_r(t, cfg["symbol"], spread_pip, slip_pip, t["outcome"])
            if r_net is not None:
                t["exit_r"] = r_net
                t["costs_applied"] = True

    m = metrics(tr, "chain_id")

    # baseline (defensa pareja, misma logica SL/TP) — solo si hay trades
    baseline = []; k_window = None
    if m["n_trades"] > 0:
        try:
            baseline, k_window = build_baseline(sl, times, high, low, close, cfg_out, m["n_trades"], spans, swing_lows, swing_highs)
        except Exception as e:  # noqa: BLE001
            baseline = []; k_window = None
            out["baseline_error"] = str(e)
    m_base = metrics(baseline, "chain_id") if baseline else {"n_trades": 0, "n_closed": 0}

    gate = mechanical_gate(m)
    delta_wr = (round(m["win_rate"] - m_base["win_rate"], 4)
                if (m.get("win_rate") is not None and m_base.get("win_rate") is not None) else None)
    delta_mean_r = (round(m["mean_r"] - m_base["mean_r"], 4)
                    if (m.get("mean_r") is not None and m_base.get("mean_r") is not None) else None)

    out.update({
        "range": [cfg["range_start"], cfg["range_end"]],
        "bars": len(sl),
        "motor_summary": summ,
        "chains_depth_ge4": {"n": len(cand), "by_status": bstat, "dedup_or_warmup_skipped": ded},
        "metrics_treatment": m,
        "metrics_baseline": m_base,
        "delta_win_rate_vs_random": delta_wr,
        "delta_mean_r_vs_random": delta_mean_r,
        "baseline_window_bars": k_window,
        "gate": gate,
        "gross_reference": m_gross,  # C4 only
    })
    if cfg.get("costs"):
        out["cost_model"] = {
            "spread_pip": spread_pip, "slip_pip": slip_pip,
            "adverse_entry_pip": spread_pip + slip_pip,
            "commission_per_lot": 0.0,
            "note": "EURUSD CSV no tiene columna spread -> spread fijo 0.5 pip; slippage 0.3 pip; comision 0 (no en dataset).",
        }
        if m_gross:
            out["delta_mean_r_gross_vs_net"] = round(m_gross["mean_r"] - m["mean_r"], 4) if (m_gross.get("mean_r") is not None and m.get("mean_r") is not None) else None
    out["verdict"] = verdict_text(cfg, m, m_gross, gate)
    out["elapsed_s"] = round(time.time() - t0, 2)
    out["raw_metrics"] = {"treatment": m, "baseline": m_base, "gross": m_gross}
    return out


def verdict_text(cfg, m, m_gross, gate):
    mr = m.get("mean_r"); ci = (m.get("bootstrap_clustered") or {}).get("mean_r_ci")
    if gate == "BLOCKED":
        return (f"BLOCKED: n_closed={m['n_closed']} < {MIN_N_GATE}. "
                "Muestra insuficiente para gate mecanico; no se puede concluir robustez OOS.")
    if gate == "PASS":
        return (f"EDGE VIVO: mean_R={mr} (CI95 {ci}), n_closed={m['n_closed']}>=30. "
                "Expectancy positiva sostenida fuera de muestra (no falsificado).")
    # FAIL
    if cfg.get("costs"):
        g = m_gross.get("mean_r") if m_gross else None
        return (f"EDGE ROTO POR COSTES: net mean_R={mr} (CI95 {ci}) vs gross={g}. "
                "Con costes realistas la expectancy cae por/debajo de 0 o su IC cruza 0. Halazgo principal de falsacion.")
    return (f"EDGE ROTO OOS: mean_R={mr} (CI95 {ci}), n_closed={m['n_closed']}. "
            "Expectancy NO positiva fuera de muestra (falsacion exitosa).")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="EXP_C1..EXP_C5 o 'all'")
    args = ap.parse_args()
    cfgs = configs()
    results = {}
    for cfg in cfgs:
        if args.only and args.only != "all" and cfg["id"] != args.only:
            continue
        print(f"\n===== {cfg['id']} ({cfg['symbol']} {cfg['range_start']}..{cfg['range_end']}) =====", flush=True)
        res = run_one(cfg)
        results[cfg["id"]] = res
        # GATE y metricas breves
        print(json.dumps({k: res.get(k) for k in ("gate", "bars", "verdict")}, default=str, indent=2)[:1200], flush=True)
        if "metrics_treatment" in res and isinstance(res["metrics_treatment"], dict) and "mean_r" in res["metrics_treatment"]:
            mt = res["metrics_treatment"]
            print(f"  treatment n_closed={mt['n_closed']} WR={mt.get('win_rate')} meanR={mt.get('mean_r')} "
                  f"CI={mt.get('bootstrap_clustered', {}).get('mean_r_ci')}", flush=True)
    # escribir JSON raw + audit
    for cfg in cfgs:
        if args.only and args.only != "all" and cfg["id"] != args.only:
            continue
        res = results[cfg["id"]]
        write_outputs(cfg, res)
    print("\nDONE.", flush=True)


def write_outputs(cfg, res):
    audit_dir = ROOT / "reports" / "audits" / "experiments" / "current_batch"
    audit_dir.mkdir(parents=True, exist_ok=True)
    raw_path = audit_dir / f"{cfg['id']}_raw.json"
    audit_path = audit_dir / f"{cfg['id']}_audit.json"

    # RAW (datos completos + trades)
    raw = {
        "schema_version": "1.0",
        "experiment": cfg["id"],
        "role": "AGENTE_C_FALSACION",
        "hypothesis": "H_C: el edge de expectancy positiva depth>=4 es ROBUSTO fuera de muestra EURUSD 2019-2024",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": res.get("elapsed_s"),
        "config": {
            "structure_mode": "lite", "max_active_chains": 4096, "swing_left": SWING_LEFT,
            "min_depth": MIN_DEPTH, "horizon_bars": HORIZON_BARS, "sl_buffer": SL_BUFFER,
            "tie_policy": "pessimistic", "warmup_bars": WARMUP_BARS,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
            "baseline_seed": BASELINE_SEED, "min_n_gate": MIN_N_GATE,
            "costs": cfg.get("costs", False),
        },
        "metrics_treatment": res.get("metrics_treatment"),
        "metrics_baseline": res.get("metrics_baseline"),
        "gross_reference": res.get("gross_reference"),
        "delta_win_rate_vs_random": res.get("delta_win_rate_vs_random"),
        "delta_mean_r_vs_random": res.get("delta_mean_r_vs_random"),
        "delta_mean_r_gross_vs_net": res.get("delta_mean_r_gross_vs_net"),
        "cost_model": res.get("cost_model"),
        "walk_forward": res.get("walk_forward"),
        "motor_summary": res.get("motor_summary"),
        "chains_depth_ge4": res.get("chains_depth_ge4"),
        "gate": res.get("gate"),
        "verdict": res.get("verdict"),
    }
    raw_path.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")

    # AUDIT (gate mecanico + protocolo + veredicto)
    gate_logic = (
        "n_closed<30 -> BLOCKED; mean_r>0 y CI95_low>0 -> PASS (edge robusto OOS); "
        "sino -> FAIL (edge roto OOS, falsacion exitosa)."
    )
    data_integrity = {
        "symbol": cfg["symbol"],
        "source": str(cfg["path"].relative_to(ROOT)),
        "source_kind": cfg["kind"],
        "data_origin": cfg["origin"],
        "declared_hash": cfg["hash"],
        "actual_file_sha256": sha256_file(cfg["path"]),
        "range": [cfg["range_start"], cfg["range_end"]],
        "bars": res.get("bars"),
        "cross_origin_caveat": cfg["kind"] == "parquet",
        "canonical_dataset_note": (
            "Parquet MT5 NO es el dataset canonico (EURUSD Dukascopy 20Y CSV). "
            "Se usa por unica fuente disponible para GBPUSD/XAUUSD; comparacion cross-origin "
            "debe interpretarse con reserva." if cfg["kind"] == "parquet" else
            "Dataset canonico EURUSD Dukascopy 20Y CSV (SHA256 prefijo 2dbb5757)."
        ),
    }
    audit = {
        "schema_version": "1.0",
        "experiment": cfg["id"],
        "role": "AGENTE_C_FALSACION",
        "hypothesis_under_test": "H_C (robustez OOS del edge depth>=4)",
        "gate_mechanical_logic": gate_logic,
        "gate": res.get("gate"),
        "verdict": res.get("verdict"),
        "protocol": {
            "code_commit": CODE_COMMIT,
            "engine": "run_sequential(structure_mode='lite', max_active_chains=4096, swing_left=3)",
            "invariants_held": True,
            "no_param_change_post_hoc": True,
            "config": {
                "min_depth": MIN_DEPTH, "horizon_bars": HORIZON_BARS, "sl_buffer": SL_BUFFER,
                "tie_policy": "pessimistic", "warmup_bars": WARMUP_BARS,
                "bootstrap_resamples": BOOTSTRAP_RESAMPLES, "bootstrap_seed": BOOTSTRAP_SEED,
                "baseline_seed": BASELINE_SEED, "min_n_gate": MIN_N_GATE,
                "costs_applied": cfg.get("costs", False),
            },
            "data_integrity": data_integrity,
            "date": datetime.now(timezone.utc).isoformat(),
        },
        "metrics": {
            "treatment": res.get("metrics_treatment"),
            "baseline": res.get("metrics_baseline"),
            "gross_reference": res.get("gross_reference"),
            "delta_mean_r_gross_vs_net": res.get("delta_mean_r_gross_vs_net"),
            "walk_forward": res.get("walk_forward"),
        },
        "result_raw_file": str(raw_path.relative_to(ROOT)),
    }
    audit_path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(f"  -> {raw_path.name}  |  {audit_path.name}", flush=True)


if __name__ == "__main__":
    main()
