#!/usr/bin/env python3
"""EXP SEQUENCE × CONTEXT STATE — H1 20Y.

Pregunta: ¿la misma secuencia (depth≥4) tiene distribución de outcome
distinta según Context State (ALIGNED / AGAINST / NEUTRAL)?

- NO emite entradas ni PnL de sistema.
- Context State vía MTFNavigator (estructura/BOS, regime, location) — NO EMA.
- Contrato: docs/contratos/CONTRATO_CONTEXT_STATE.md
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import MTFNavigator, NavigatorConfig, StructureBias
from engine.sequential_events import SeqConfig, run_sequential, summarize_chains

DATA = ROOT / "data" / "raw" / "EURUSD"
OUT_JSON = ROOT / "reports" / "audits" / "exp_sequence_x_context_state_H1_20Y.json"
OUT_MD = ROOT / "reports" / "audits" / "exp_sequence_x_context_state_H1_20Y.md"
HORIZONS = (6, 12, 24, 48)
MIN_N_INTERPRET = 30


def _load(tf: str) -> pd.DataFrame:
    p = DATA / f"EURUSD_{tf}.parquet"
    if not p.exists():
        csv = ROOT / "datasets" / "eurusd_dukascopy_20y" / f"EURUSD_{tf}.csv"
        df = pd.read_csv(csv)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)
    df = pd.read_parquet(p)
    return df.sort_values("time").reset_index(drop=True)


def _bucket(direction: int, hint: StructureBias, location_favorable: bool | None) -> str:
    if hint in (StructureBias.UNKNOWN, StructureBias.MIXED):
        return "CTX_NEUTRAL"
    hint_dir = 1 if hint is StructureBias.BULLISH else -1
    if hint_dir == direction:
        return "CTX_ALIGNED"
    return "CTX_AGAINST"


def _location_favorable(hint: StructureBias, location: str | None) -> bool | None:
    if location is None or location == "UNKNOWN":
        return None
    if hint is StructureBias.BULLISH:
        return location in ("DISCOUNT", "MID")
    if hint is StructureBias.BEARISH:
        return location in ("PREMIUM", "MID")
    return None


def _extract_location(nav_state: Any) -> str:
    layers = getattr(nav_state, "layers", None) or {}
    h4 = layers.get("H4")
    if h4 is not None:
        answers = getattr(h4, "answers", {}) or {}
        for k, v in answers.items():
            if "WHERE" in str(k).upper() or "location" in str(k).lower():
                if isinstance(v, dict) and "location" in v:
                    return str(v["location"]).upper()
                if isinstance(v, str):
                    return v.upper()
    d1 = layers.get("D1")
    if d1 is not None:
        rh, rl, close = d1.range_high, d1.range_low, d1.last_close
        if rh is not None and rl is not None and rh > rl:
            mid = 0.5 * (rh + rl)
            if close < mid:
                return "DISCOUNT"
            if close > mid:
                return "PREMIUM"
            return "MID"
    return "UNKNOWN"


def _outcomes(close, bar: int, direction: int):
    out = {}
    n = len(close)
    for h in HORIZONS:
        j = bar + h
        if j >= n:
            out[f"end_{h}"] = None
            out[f"end_pos_{h}"] = None
        else:
            move = float(direction) * float(close[j] - close[bar])
            out[f"end_{h}"] = move
            out[f"end_pos_{h}"] = 1.0 if move > 0 else 0.0
    return out


def _agg(rows):
    if not rows:
        return {"n": 0}
    res = {"n": len(rows)}
    for h in HORIZONS:
        vals = [r[f"end_{h}"] for r in rows if r.get(f"end_{h}") is not None]
        pos = [r[f"end_pos_{h}"] for r in rows if r.get(f"end_pos_{h}") is not None]
        if not vals:
            res[f"end_pos_{h}"] = None
            res[f"mean_end_{h}"] = None
            res[f"n_end_{h}"] = 0
        else:
            res[f"end_pos_{h}"] = round(float(np.mean(pos)) * 100, 2)
            res[f"mean_end_{h}"] = round(float(np.mean(vals)), 6)
            res[f"n_end_{h}"] = len(vals)
    return res


def main():
    t0 = time.time()
    print("EXP SEQUENCE × CONTEXT STATE — load frames", flush=True)
    frames = {tf: _load(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    close = h1["close"].to_numpy(float)
    times = list(h1["time"])
    print(f"H1 bars={len(h1)}", flush=True)

    print("run_sequential (canonical_bos)...", flush=True)
    chains = run_sequential(h1, SeqConfig(structure_mode="canonical_bos"), timeframe="H1")
    summary = summarize_chains(chains)
    print(f"chains={summary['n_chains']} by_depth={summary['by_depth']}", flush=True)

    depth4 = [c for c in chains if len(c.nodes) >= 4]
    print(f"depth>=4: {len(depth4)}", flush=True)

    nav = MTFNavigator(frames, NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))

    by_bucket = defaultdict(list)
    all_rows = []
    seen_bars = set()
    errors = 0

    for i, ch in enumerate(depth4):
        struct = next((n for n in ch.nodes if n.stage.value == "STRUCTURE"), None)
        if struct is None:
            continue
        bar = int(struct.bar)
        if bar in seen_bars:
            continue
        seen_bars.add(bar)
        if bar < 0 or bar >= len(times):
            continue
        t = times[bar]
        try:
            state = nav.navigate(decision_time=t, exec_tf="H1")
        except Exception:
            errors += 1
            continue
        constraints = state.constraints
        hint = constraints.direction_hint if constraints else StructureBias.UNKNOWN
        location = _extract_location(state)
        loc_fav = _location_favorable(hint, location)
        bucket = _bucket(int(ch.direction), hint, loc_fav)
        row = {
            "chain_id": ch.chain_id,
            "direction": int(ch.direction),
            "structure_bar": bar,
            "depth": len(ch.nodes),
            "status": ch.status,
            "direction_hint": hint.value,
            "location": location,
            "location_favorable": loc_fav,
            "bucket": bucket,
            "regime_stack": dict(constraints.regime_stack) if constraints else {},
        }
        row.update(_outcomes(close, bar, int(ch.direction)))
        by_bucket[bucket].append(row)
        all_rows.append(row)

    tables = {
        "ALL_DEPTH4": _agg(all_rows),
        "CTX_ALIGNED": _agg(by_bucket["CTX_ALIGNED"]),
        "CTX_AGAINST": _agg(by_bucket["CTX_AGAINST"]),
        "CTX_NEUTRAL": _agg(by_bucket["CTX_NEUTRAL"]),
    }

    n_a = tables["CTX_ALIGNED"]["n"]
    n_g = tables["CTX_AGAINST"]["n"]
    interpretable = n_a >= MIN_N_INTERPRET and n_g >= MIN_N_INTERPRET
    end24_a = tables["CTX_ALIGNED"].get("end_pos_24")
    end24_g = tables["CTX_AGAINST"].get("end_pos_24")
    delta = None
    if end24_a is not None and end24_g is not None:
        delta = round(end24_a - end24_g, 2)

    if not interpretable:
        gate = "INSUFFICIENT_N"
        reading = "n insuficiente en ALIGNED u AGAINST — no declarar diferencia de distribución"
    elif delta is not None and abs(delta) >= 5.0:
        gate = "HYPOTHESIS_COMPATIBLE"
        reading = (
            f"end>0@+24 ALIGNED={end24_a}% vs AGAINST={end24_g}% (Δ={delta} pp). "
            "Compatible con H1 a nivel exploratorio; NO es edge operativo ni autorización de entry."
        )
    else:
        gate = "HYPOTHESIS_NOT_SUPPORTED"
        reading = (
            f"end>0@+24 ALIGNED={end24_a}% vs AGAINST={end24_g}% (Δ={delta} pp). "
            "No se observa separación material bajo este diseño."
        )

    report = {
        "experiment": "SEQUENCE_X_CONTEXT_STATE",
        "dataset": "EURUSD Dukascopy 20Y",
        "symbol": "EURUSD",
        "exec_tf": "H1",
        "policy": "STUDY_DISTRIBUTION_NOT_ENTRY",
        "contract": "docs/contratos/CONTRATO_CONTEXT_STATE.md",
        "sequence": {
            "module": "engine/sequential_events.py",
            "structure_mode": "canonical_bos",
            "min_depth": 4,
            "anchor": "STRUCTURE_bar",
            "summary": summary,
            "n_depth4_raw": len(depth4),
            "n_scored_dedup_bar": len(all_rows),
        },
        "context_state": {
            "source": "engine/mtf_navigation.MTFNavigator",
            "ema_used": False,
            "buckets": ["CTX_ALIGNED", "CTX_AGAINST", "CTX_NEUTRAL"],
        },
        "horizons_bars": list(HORIZONS),
        "tables": tables,
        "delta_end_pos_24_aligned_minus_against": delta,
        "gate": gate,
        "reading": reading,
        "navigate_errors": errors,
        "elapsed_s": round(time.time() - t0, 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": "Grok cloud",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    _write_md(report)
    print(json.dumps({"gate": gate, "tables": tables, "delta": delta, "out": str(OUT_JSON)}, indent=2), flush=True)
    return report


def _write_md(report: dict) -> None:
    lines = [
        "# EXP — SEQUENCE × CONTEXT STATE (H1 20Y)",
        "",
        f"**Gate:** `{report['gate']}`",
        f"**Generated:** {report['generated_at']}",
        "",
        report["reading"],
        "",
        "## Tablas (end>0 % / mean end)",
        "",
        "| Bucket | n | end>0 +6 | +12 | +24 | +48 | mean_end +24 |",
        "|--------|--:|---------:|----:|----:|----:|-------------:",
    ]
    for name in ("ALL_DEPTH4", "CTX_ALIGNED", "CTX_AGAINST", "CTX_NEUTRAL"):
        t = report["tables"][name]
        if t.get("n", 0) == 0:
            lines.append(f"| {name} | 0 | — | — | — | — | — |")
            continue
        lines.append(
            f"| {name} | {t['n']} | {t.get('end_pos_6')} | {t.get('end_pos_12')} | "
            f"{t.get('end_pos_24')} | {t.get('end_pos_48')} | {t.get('mean_end_24')} |"
        )
    lines += [
        "",
        f"- Δ (ALIGNED − AGAINST) end>0@+24: **{report.get('delta_end_pos_24_aligned_minus_against')}** pp",
        f"- elapsed: {report['elapsed_s']}s",
        f"- EMA used: **false**",
        "",
        "## Policy",
        "",
        "```",
        "SEQUENCE × CONTEXT  =  objeto de estudio",
        "SEQUENCE × CONTEXT  ≠  señal de trading",
        "```",
        "",
    ]
    OUT_MD.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
