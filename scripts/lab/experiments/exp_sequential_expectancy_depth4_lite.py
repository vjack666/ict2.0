#!/usr/bin/env python3
"""EXP SEQUENTIAL EXPECTANCY DEPTH>=4 @ BOS-lite — H1 bounded range 2019-2024.

Pregunta: con SL/TP ESTRUCTURALES (no artefactos end>0@+24), ¿las cadenas
secuenciales depth>=4 (POOL->SWEEP->DISPLACEMENT->STRUCTURE) muestran
expectancy (R-multiples reales) distinta de entradas aleatorias en FVG?

- Motor: run_sequential(structure_mode="lite") UNA llamada sobre el rango
  acotado (PIT-estable DENTRO del rango; deuda FULL-vs-PREFIX documentada en
  .hermes-worklog/2026-08-20_2049_EXP_SEQXCONTEXT_INVALIDATED.md).
- Entry: close de la barra STRUCTURE (BOS-lite), point-in-time.
- SL estructural: docs/ict/14_STOP_LOSS_ESTRUCTURAL.md (mecha del sweep /
  swing roto, nunca ATR).
- TP estructural v1 (fallback sancionado): proyeccion medida del rango de la
  secuencia (extremo opuesto + altura). Limitacion documentada.
- NO emite senales de trading: objeto de estudio.
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

DATA_CSV = ROOT / "datasets" / "eurusd_dukascopy_20y" / "EURUSD_H1.csv"
OUT_JSON = ROOT / "reports" / "audits" / "sequential_expectancy_depth4_lite_H1.json"
OUT_MD = ROOT / "docs" / "experimentos" / "EXP_SEQUENTIAL_EXPECTANCY_DEPTH4_LITE_H1.md"

RANGE_START = "2019-01-01"
RANGE_END = "2024-12-31"
MIN_DEPTH = 4
HORIZON_BARS = 200
SL_BUFFER = 0.0001
SWING_LEFT = 3  # must match SeqConfig.swing_left
WARMUP_BARS = 20
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
BASELINE_SEED = 42
MIN_N_GATE = 30


def load_slice() -> pd.DataFrame:
    df = pd.read_csv(DATA_CSV)
    ts = pd.to_datetime(df["time"])
    mask = (ts >= RANGE_START) & (ts <= RANGE_END + " 23:59:59")
    sl = df.loc[mask].sort_values("time").reset_index(drop=True)
    return sl


def last_confirmed_swing(swings: list[tuple[int, float]], bar: int) -> float | None:
    """Most recent swing whose confirmation (bar_j + SWING_LEFT) <= bar. PIT-safe."""
    if not swings:
        return None
    js = [j for j, _ in swings]
    limit = bar - SWING_LEFT
    pos = bisect_right(js, limit)
    if pos == 0:
        return None
    return float(swings[pos - 1][1])


def build_trade(
    direction: int,
    entry_bar: int,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    swing_lows: list[tuple[int, float]],
    swing_highs: list[tuple[int, float]],
    sweep_wick_low: float | None,
    sweep_wick_high: float | None,
    range_lo: float,
    range_hi: float,
    cfg: OutcomeConfig,
) -> dict | None:
    """Identical structural SL/TP construction for treatment and baseline."""
    entry = float(close[entry_bar])
    if direction == 1:
        sl = structural_stop(
            1, sweep_extreme=sweep_wick_low,
            broken_swing=last_confirmed_swing(swing_lows, entry_bar),
            buffer=cfg.sl_buffer,
        )
    else:
        sl = structural_stop(
            -1, sweep_extreme=sweep_wick_high,
            broken_swing=last_confirmed_swing(swing_highs, entry_bar),
            buffer=cfg.sl_buffer,
        )
    tp = measured_projection_tp(direction, range_hi, range_lo)
    if sl is None or tp is None:
        return None
    levels = TradeLevels(direction=direction, entry=entry, sl=float(sl), tp=float(tp))
    return {"levels": levels, "valid": levels.is_valid()}


def metrics(trades: list[dict], cluster_key: str) -> dict:
    closed = [t for t in trades if t.get("exit_r") is not None]
    wins = sum(1 for t in closed if float(t["exit_r"]) > 0)
    rs = [float(t["exit_r"]) for t in closed]
    out: dict = {
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
        out.update(
            {
                "win_rate": round(wr, 4),
                "win_rate_wilson95": [round(lo, 4), round(hi, 4)],
                "mean_r": round(float(np.mean(rs)), 4),
                "median_r": round(float(np.median(rs)), 4),
                "std_r": round(float(np.std(rs, ddof=1)) if len(rs) > 1 else 0.0, 4),
                "min_r": round(float(np.min(rs)), 4),
                "max_r": round(float(np.max(rs)), 4),
            }
        )
    else:
        out.update({"win_rate": None, "win_rate_wilson95": None, "mean_r": None})
    out["bootstrap_clustered"] = bootstrap_clustered(
        trades, cluster_key, n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED
    )
    return out


def main() -> dict:
    t0 = time.time()
    print("EXP SEQUENTIAL EXPECTANCY DEPTH>=4 BOS-LITE — load slice", flush=True)
    slice_df = load_slice()
    n_bars = len(slice_df)
    print(f"bars={n_bars} ({slice_df['time'].iloc[0]} .. {slice_df['time'].iloc[-1]})", flush=True)

    cfg_seq = SeqConfig(structure_mode="lite", max_active_chains=4096, swing_left=SWING_LEFT)
    cfg_out = OutcomeConfig(horizon_bars=HORIZON_BARS, sl_buffer=SL_BUFFER, tie_policy="pessimistic")

    high = slice_df["high"].to_numpy(float)
    low = slice_df["low"].to_numpy(float)
    close = slice_df["close"].to_numpy(float)
    times = list(slice_df["time"])

    print("run_sequential (lite)...", flush=True)
    chains = run_sequential(slice_df, cfg_seq, timeframe="H1")
    summary = summarize_chains(chains)
    print(f"chains={summary['n_chains']} by_depth={summary['by_depth']}", flush=True)

    swing_highs, swing_lows = _causal_swings(high, low, SWING_LEFT)

    # --- Treatment: depth>=4 chains anchored at STRUCTURE ---
    candidates = [c for c in chains if len(c.nodes) >= MIN_DEPTH]
    by_status = {}
    for c in candidates:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    print(f"depth>={MIN_DEPTH}: {len(candidates)} status={by_status}", flush=True)

    seen: set[tuple[int, int]] = set()
    dedup_skipped = 0
    treatment: list[dict] = []
    spans: list[int] = []
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
        r_lo = float(np.min(low[a : b + 1]))
        r_hi = float(np.max(high[a : b + 1]))
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
        treatment.append(
            {
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
            }
        )

    n_treatment_valid = len(treatment)
    print(f"treatment trades={n_treatment_valid} (dedup/skip={dedup_skipped})", flush=True)

    # --- Baseline: random FVG entries, IDENTICAL structural SL/TP logic ---
    records = slice_df[["open", "high", "low", "close"]].copy()
    records["time"] = list(range(n_bars))
    fvgs = detect_fvg(records.to_dict("records"), timeframe="SEQ", symbol="")
    fvg_events: list[tuple[int, int]] = []  # (confirm_bar, direction)
    f_seen: set[tuple[int, int]] = set()
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
    baseline: list[dict] = []
    for idx in order:
        if len(baseline) >= n_treatment_valid:
            break
        cb, direction = fvg_events[idx]
        a = max(0, cb - k_window + 1)
        r_lo = float(np.min(low[a : cb + 1]))
        r_hi = float(np.max(high[a : cb + 1]))
        built = build_trade(
            direction, cb, close, high, low, swing_lows, swing_highs, None, None,
            r_lo, r_hi, cfg_out,
        )
        if built is None:
            continue
        res = resolve_outcome(high, low, cb, built["levels"], cfg_out)
        baseline.append(
            {
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
            }
        )
    print(f"baseline trades={len(baseline)} (fvg pool={len(fvg_events)}, window={k_window})", flush=True)

    # --- Metrics & gates ---
    m_treat = metrics(treatment, cluster_key="chain_id")
    m_base = metrics(baseline, cluster_key="chain_id")
    gate_n = m_treat["n_trades"] >= MIN_N_GATE and m_treat["n_closed"] >= MIN_N_GATE
    gate_base = m_base["n_trades"] >= MIN_N_GATE
    gates = {
        "N_TREATMENT_MIN_30": {"pass": bool(gate_n), "n": m_treat["n_trades"], "n_closed": m_treat["n_closed"]},
        "N_BASELINE_MIN_30": {"pass": bool(gate_base), "n": m_base["n_trades"]},
    }
    overall = "PASS" if gate_n and gate_base else "FAIL"

    delta_wr = None
    if m_treat.get("win_rate") is not None and m_base.get("win_rate") is not None:
        delta_wr = round(m_treat["win_rate"] - m_base["win_rate"], 4)
    delta_mean_r = None
    if m_treat.get("mean_r") is not None and m_base.get("mean_r") is not None:
        delta_mean_r = round(m_treat["mean_r"] - m_base["mean_r"], 4)

    report = {
        "schema_version": "1.0",
        "experiment": "SEQUENTIAL_EXPECTANCY_DEPTH4_LITE",
        "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
        "dataset": {
            "symbol": "EURUSD",
            "exec_tf": "H1",
            "source": str(DATA_CSV.relative_to(ROOT)),
            "range_start": RANGE_START,
            "range_end": RANGE_END,
            "bars": n_bars,
        },
        "config": {
            "structure_mode": cfg_seq.structure_mode,
            "max_active_chains": cfg_seq.max_active_chains,
            "swing_left": SWING_LEFT,
            "min_depth": MIN_DEPTH,
            "anchor": "STRUCTURE_bar_close",
            "sl_rule": "long=min(sweep_wick_low,broken_swing_low)-buffer; short=mirror",
            "tp_rule": "measured projection of sequence range (v1 sanctioned fallback)",
            "tp_baseline_window_bars": k_window,
            "sl_buffer": SL_BUFFER,
            "horizon_bars": HORIZON_BARS,
            "tie_policy": "pessimistic_intrabar_SL",
            "dedup": "(structure_bar,direction)",
            "warmup_bars": WARMUP_BARS,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "cluster": "chain_id"},
            "baseline_seed": BASELINE_SEED,
        },
        "motor_summary": summary,
        "chains_depth_ge4": {"n": len(candidates), "by_status": by_status, "dedup_or_warmup_skipped": dedup_skipped},
        "gates": gates,
        "gate": overall,
        "metrics_treatment": m_treat,
        "metrics_baseline": m_base,
        "delta_win_rate": delta_wr,
        "delta_mean_r": delta_mean_r,
        "deviations": [
            "TP uses the sanctioned measured-projection fallback: detect_liquidity_htf levels are LTF rolling extremes (left=3), not true HTF pools; clean HTF mapping would require the navigator layer carrying the known FULL-vs-PREFIX sequence-index debt.",
            "Baseline lacks a manipulation wick, so its structural stop uses only the broken-swing term of the SAME rule (sweep term absent by construction, not by different code path).",
            "max_active_chains raised to 4096 (experiment-local SeqConfig) to avoid silent pool-seed drops at the default 64; funnel configs untouched.",
        ],
        "trades": treatment + baseline,
        "elapsed_s": round(time.time() - t0, 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _write_md(report)
    print(json.dumps({
        "gate": overall,
        "gates": gates,
        "treatment": {k: m_treat[k] for k in ("n_trades", "n_open", "win_rate", "win_rate_wilson95", "mean_r")},
        "baseline": {k: m_base[k] for k in ("n_trades", "n_open", "win_rate", "win_rate_wilson95", "mean_r")},
        "delta_win_rate": delta_wr,
        "delta_mean_r": delta_mean_r,
        "out": str(OUT_JSON),
    }, indent=2), flush=True)
    return report


def _write_md(report: dict) -> None:
    mt, mb = report["metrics_treatment"], report["metrics_baseline"]
    gates = report["gates"]

    def fmt(m: dict) -> str:
        if m.get("win_rate") is None:
            return "sin datos cerrados"
        return (
            f"{m['win_rate'] * 100:.1f}% "
            f"({m['win_rate_wilson95'][0] * 100:.1f}-{m['win_rate_wilson95'][1] * 100:.1f}%)"
        )

    lines = [
        "# EXP — Expectancy con SL/TP estructural en DEPTH≥4 @ BOS-lite (H1, rango acotado)",
        "",
        "**Fecha:** " + report["generated_at"][:10],
        f"**Estado:** **EJECUTADO — GATE {report['gate']}**",
        "**Data:** EURUSD H1 Dukascopy 2019-01-01 → 2024-12-31 "
        f"({report['dataset']['bars']} barras)",
        "**Artefacto:** `reports/audits/experiments/sequential/sequential_expectancy_depth4_lite_H1.json`",
        "",
        "---",
        "",
        "## Hipótesis",
        "",
        "Las cadenas secuenciales depth≥4 (POOL→SWEEP→DISPLACEMENT→STRUCTURE) ancladas al",
        "close del BOS-lite, operadas con SL/TP ESTRUCTURALES (mecha del sweep / swing roto;",
        "proyección medida del rango), muestran expectancy en R-multiples reales superior a",
        "entradas aleatorias en FVG con la MISMA lógica de SL/TP.",
        "",
        "## Diseño",
        "",
        "- Motor: `run_sequential(structure_mode=\"lite\")`, UNA llamada sobre el rango acotado",
        "  (PIT-estable dentro del rango; deuda motor FULL-vs-PREFIX registrada en bitácora",
        "  2026-08-20 — no afecta este diseño de una sola pasada).",
        "- Unidad: cadena depth≥4; anchor = barra STRUCTURE; dirección = dirección de la cadena.",
        "- Dedup por `(structure_bar, direction)`.",
        f"- SL estructural: long = min(mecha sweep low, swing low roto) − {report['config']['sl_buffer']};",
        "  short espejo. Nunca ATR (`docs/ict/14_STOP_LOSS_ESTRUCTURAL.md`).",
        "- TP estructural v1 (fallback sancionado): extremo opuesto del rango de la secuencia",
        "  extendido por su altura (proyección medida). Limitación v1 documentada.",
        f"- Resolución: escaneo barra a barra desde la barra posterior al entry, horizonte",
        f" {report['config']['horizon_bars']} barras → \"open\" (excluido del win-rate, contado aparte);",
        "  empate intrabar SL+TP → pesimista (SL).",
        f"- Baseline: entradas aleatorias en FVG (mismo n), misma función de SL/TP",
        f" (ventana de rango = mediana sweep→structure = {report['config']['tp_baseline_window_bars']} barras).",
        f"- Bootstrap agrupado por chain_id, {report['config']['bootstrap']['resamples']} remuestreos,",
        f" seed {report['config']['bootstrap']['seed']}. CIs Wilson para win-rate.",
        "",
        "## Métricas",
        "",
        "| Grupo | n | cerrados | open | Win-rate (Wilson95) | mean R | median R |",
        "|--------|--:|---------:|-----:|--------------------|-------:|---------:|",
        f"| Tratamiento (depth≥4) | {mt['n_trades']} | {mt['n_closed']} | {mt['n_open']} | "
        f"{fmt(mt)} | {mt.get('mean_r')} | {mt.get('median_r')} |",
        f"| Baseline (FVG random) | {mb['n_trades']} | {mb['n_closed']} | {mb['n_open']} | "
        f"{fmt(mb)} | {mb.get('mean_r')} | {mb.get('median_r')} |",
        "",
        f"- Δ win-rate (trat − base): **{report['delta_win_rate']}**",
        f"- Δ mean R (trat − base): **{report['delta_mean_r']}**",
        f"- Bootstrap meanR CI tratamiento: `{(mt.get('bootstrap_clustered') or {}).get('mean_r_ci')}`",
        f"- Bootstrap meanR CI baseline: `{(mb.get('bootstrap_clustered') or {}).get('mean_r_ci')}`",
        "",
        "## Resultado",
        "",
        f"- Cadena total motor: {report['motor_summary']['n_chains']}; depth≥4: "
        f"{report['chains_depth_ge4']['n']} ({report['chains_depth_ge4']['by_status']}).",
        f"- Trades válidos tras dedup/warmup: tratamiento {mt['n_trades']}, baseline {mb['n_trades']}.",
        f"- Gate global: **{report['gate']}**.",
        "",
        "## Lectura correcta",
        "",
        "1. Los R son GEOMETRÍA de niveles estructurales fijados en el entry; no incluyen",
        "   spread, slippage ni comisión.",
        "2. El TP es proyección medida (fallback v1), no liquidez HTF real: los niveles",
        "   absolutos de R dependen de esa convención.",
        "3. \"open\" se excluye del win-rate: si el horizonte truncara tendencias ganadoras,",
        "   el WR reportado está sesgado a la baja; revisar n_open antes de interpretar.",
        "4. El empate intrabar se resuelve pesimista: los WR aquí son el piso, no el techo.",
        "5. Comparar contra baseline FVG-random controla geometría de riesgo, NO la tesis ICT:",
        "   un Δ positivo indica que el ANCLAJE secuencial aporta, no que la narrativa sea cierta.",
        "",
        "## Policy",
        "",
        "```",
        "DEPTH≥4 SEQUENTIAL + SL/TP estructural  =  objeto de estudio",
        "DEPTH≥4 SEQUENTIAL + SL/TP estructural  ≠  señal de trading aprobada",
        "```",
        "",
        "## Gate",
        "",
        "| Criterio | Umbral | Resultado |",
        "|----------|--------|-----------|",
        f"| n tratamiento (cerrados) | ≥30 | {mt['n_closed']} → {'PASS' if gates['N_TREATMENT_MIN_30']['pass'] else 'FAIL'} |",
        f"| n baseline | ≥30 | {mb['n_trades']} → {'PASS' if gates['N_BASELINE_MIN_30']['pass'] else 'FAIL'} |",
        f"| **Global** | ambos | **{report['gate']}** |",
        "",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
