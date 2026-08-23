#!/usr/bin/env python3
"""Preregistered depth>=3 expansion with fixed chronological OOS blocks.

This is a distribution study only. It does not fit parameters, create entries,
calculate PnL, or authorize a backtest. The base causal and TNA gates are hard
barriers before any rows are scored.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import NavigatorConfig, StructureBias, MTFNavigator  # noqa: E402
from engine.sequential_events import SeqConfig, run_sequential, summarize_chains  # noqa: E402
from scripts.lab.experiments.exp_seq_ctx_01 import (  # noqa: E402
    HORIZONS,
    _aggregate,
    _bucket,
    _load_frames,
    _location,
    _outcomes,
    _require_gates,
)

MIN_DEPTH = int(os.environ.get("EXP_SEQ_CTX_MIN_DEPTH", "3"))
STRUCTURE_MODE = os.environ.get("EXP_SEQ_CTX_STRUCTURE_MODE", "canonical_bos")
VARIANT_ID = os.environ.get("EXP_SEQ_CTX_VARIANT", "EXP-SEQ-CTX-01B")
MIN_N = 30
OUT_DIR = ROOT / "reports" / "audits" / "experiments" / os.environ.get(
    "EXP_SEQ_CTX_OUTPUT", "seq_ctx_01b_oos"
)
OUT_JSON = OUT_DIR / "report.json"
OUT_MD = OUT_DIR / "report.md"
BLOCKS = (
    ("DESIGN", "2006-01-01", "2015-12-31 23:59:59+00:00"),
    ("VALIDATION", "2016-01-01", "2020-12-31 23:59:59+00:00"),
    ("HOLDOUT", "2021-01-01", "2025-12-31 23:59:59+00:00"),
)


def _tables(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_bucket[row["bucket"]].append(row)
    result = {f"ALL_DEPTH{MIN_DEPTH}": _aggregate(rows)}
    result.update(
        {
            name: _aggregate(by_bucket[name])
            for name in ("CTX_ALIGNED", "CTX_AGAINST", "CTX_NEUTRAL")
        }
    )
    return result


def _block_for(ts: Any) -> tuple[str, Any] | None:
    value = ts if getattr(ts, "tzinfo", None) else ts.tz_localize("UTC")
    for name, start, end in BLOCKS:
        lo = pd.Timestamp(start, tz="UTC")
        hi = pd.Timestamp(end, tz="UTC")
        if lo <= value <= hi:
            return name, hi
    return None


def _write_markdown(report: dict[str, Any]) -> None:
    pooled = report["pooled_oos_eligible"]
    lines = [
        "# EXP-SEQ-CTX-01B — expansión depth>=3 con OOS fijo",
        "",
        f"**Estado:** `{report['status']}`",
        "**Política:** distribución observacional; sin entry, PnL, entrenamiento ni promoción.",
        "",
        f"Pooled OOS elegible: ALIGNED={pooled['CTX_ALIGNED']['n']}, "
        f"AGAINST={pooled['CTX_AGAINST']['n']}, NEUTRAL={pooled['CTX_NEUTRAL']['n']}",
        "",
        "| Bloque | ALIGNED | AGAINST | NEUTRAL |",
        "|---|---:|---:|---:|",
    ]
    for block in ("DESIGN", "VALIDATION", "HOLDOUT"):
        table = report["blocks"][block]
        lines.append(
            f"| {block} | {table['CTX_ALIGNED']['n']} | "
            f"{table['CTX_AGAINST']['n']} | {table['CTX_NEUTRAL']['n']} |"
        )
    lines += [
        "",
        "Los conteos por bloque son descriptivos. `n>=30` pooled no demuestra edge.",
        "La variante depth>=3 no sustituye el resultado primario depth>=4.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    _require_gates()
    started = time.time()
    frames = _load_frames()
    h1 = frames["H1"]
    close = h1["close"].to_numpy(float)
    times = list(h1["time"])
    chains = run_sequential(h1, SeqConfig(structure_mode=STRUCTURE_MODE), timeframe="H1")
    candidates = [chain for chain in chains if len(chain.nodes) >= MIN_DEPTH]
    nav = MTFNavigator(frames, NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
    rows: list[dict[str, Any]] = []
    seen_bars: set[int] = set()
    for chain in candidates:
        structure = next((node for node in chain.nodes if node.stage.value == "STRUCTURE"), None)
        if structure is None:
            continue
        bar = int(structure.bar)
        if bar in seen_bars or bar < 0 or bar + max(HORIZONS) >= len(times):
            continue
        seen_bars.add(bar)
        state = nav.navigate(decision_time=times[bar], exec_tf="H1")
        constraints = state.constraints
        hint = constraints.direction_hint if constraints else StructureBias.UNKNOWN
        block = _block_for(times[bar])
        if block is None:
            continue
        block_name, block_end = block
        if times[bar + max(HORIZONS)] > block_end:
            continue
        row: dict[str, Any] = {
            "chain_id": chain.chain_id,
            "direction": int(chain.direction),
            "structure_bar": bar,
            "structure_time": times[bar].isoformat(),
            "depth": len(chain.nodes),
            "status": chain.status,
            "direction_hint": hint.value,
            "location": _location(state),
            "bucket": _bucket(int(chain.direction), hint),
            "oos_block": block_name,
        }
        row.update(_outcomes(close, bar, int(chain.direction)))
        rows.append(row)
        if len(rows) == 1 or len(rows) % 25 == 0:
            print(f"[oos] candidates={len(candidates)} eligible={len(rows)}", flush=True)

    blocks = {name: _tables([r for r in rows if r["oos_block"] == name]) for name, _, _ in BLOCKS}
    pooled = _tables(rows)
    aligned_n = pooled["CTX_ALIGNED"]["n"]
    against_n = pooled["CTX_AGAINST"]["n"]
    status = "PASS_SAMPLE_SUFFICIENT" if aligned_n >= MIN_N and against_n >= MIN_N else "INSUFFICIENT_N"
    report = {
        "experiment": VARIANT_ID,
        "variant_of": "EXP-SEQ-CTX-01",
        "status": status,
        "sample_sufficient_for_descriptive_comparison": status == "PASS_SAMPLE_SUFFICIENT",
        "usable_for_inference": False,
        "policy": "STUDY_DISTRIBUTION_NOT_ENTRY; NO_TRAINING; NO_BACKTEST",
        "dataset": "EURUSD Dukascopy 20Y",
        "sequence": {"module": "engine/sequential_events.py", "structure_mode": STRUCTURE_MODE, "min_depth": MIN_DEPTH, "summary": summarize_chains(chains)},
        "oos_control": {"blocks": [{"name": n, "start": s, "end": e} for n, s, e in BLOCKS], "horizon_boundary": "+48 must remain inside block"},
        "gates": {"causal": "reports/audits/experiments/seq_ctx_01/gate_causal.json", "tna": "reports/audits/tna_streaming_prefix_2026-08-22.json"},
        "min_n": MIN_N,
        "pooled_oos_eligible": pooled,
        "blocks": blocks,
        "rows": rows,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.time() - started, 3),
        "host": "local_pc",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    _write_markdown(report)
    print(json.dumps({"status": status, "eligible": len(rows), "aligned": aligned_n, "against": against_n, "out": str(OUT_JSON)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
