#!/usr/bin/env python3
"""EXP-SEQ-CTX-01 distribution matrix, guarded by the causal gate."""
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

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import MTFNavigator, NavigatorConfig, StructureBias  # noqa: E402
from engine.sequential_events import SeqConfig, run_sequential, summarize_chains  # noqa: E402

DATASET = ROOT / "datasets" / "eurusd_dukascopy_20y"
GATE = ROOT / "reports" / "audits" / "experiments" / "seq_ctx_01" / "gate_causal.json"
TNA_GATE = ROOT / "reports" / "audits" / "tna_streaming_prefix_2026-08-22.json"
OUT_JSON = ROOT / "reports" / "audits" / "experiments" / "seq_ctx_01" / "matrix.json"
OUT_MD = ROOT / "reports" / "audits" / "experiments" / "seq_ctx_01" / "matrix.md"
HORIZONS = (6, 12, 24, 48)
MIN_N = 30


def _load_frames() -> dict[str, pd.DataFrame]:
    frames = {}
    for tf in ("D1", "H4", "H1"):
        frame = pd.read_csv(DATASET / f"EURUSD_{tf}.csv")
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
        frames[tf] = frame.sort_values("time").reset_index(drop=True)
    return frames


def _require_gates() -> None:
    if not GATE.exists():
        raise SystemExit(f"CAUSAL_GATE_MISSING: {GATE}")
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    if gate.get("status") != "PASS" or not gate.get("usable_for_inference"):
        raise SystemExit("CAUSAL_GATE_NOT_PASS: matrix aborted before inference")
    if not TNA_GATE.exists():
        raise SystemExit(f"TNA_GATE_MISSING: {TNA_GATE}")
    tna = json.loads(TNA_GATE.read_text(encoding="utf-8"))
    if tna.get("full_prefix") != "PASS_BY_LAYER_INDUCTION" or tna.get("gate") != "PASS":
        raise SystemExit("TNA_GATE_NOT_PASS: matrix aborted before inference")


def _bucket(direction: int, hint: StructureBias) -> str:
    if hint in (StructureBias.UNKNOWN, StructureBias.MIXED):
        return "CTX_NEUTRAL"
    hint_direction = 1 if hint is StructureBias.BULLISH else -1
    return "CTX_ALIGNED" if hint_direction == direction else "CTX_AGAINST"


def _location(state: Any) -> str:
    layers = getattr(state, "layers", {}) or {}
    h4 = layers.get("H4")
    if h4 is not None:
        for key, value in (getattr(h4, "answers", {}) or {}).items():
            if "WHERE" in str(key).upper() or "LOCATION" in str(key).upper():
                if isinstance(value, dict) and "location" in value:
                    return str(value["location"]).upper()
                if isinstance(value, str):
                    return value.upper()
    return "UNKNOWN"


def _outcomes(close: np.ndarray, bar: int, direction: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for horizon in HORIZONS:
        end = bar + horizon
        if end >= len(close):
            result[f"end_{horizon}"] = None
            result[f"end_pos_{horizon}"] = None
        else:
            move = float(direction) * float(close[end] - close[bar])
            result[f"end_{horizon}"] = move
            result[f"end_pos_{horizon}"] = 1.0 if move > 0 else 0.0
    return result


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"n": len(rows)}
    for horizon in HORIZONS:
        values = [r[f"end_{horizon}"] for r in rows if r.get(f"end_{horizon}") is not None]
        positives = [r[f"end_pos_{horizon}"] for r in rows if r.get(f"end_pos_{horizon}") is not None]
        result[f"n_end_{horizon}"] = len(values)
        result[f"end_pos_{horizon}"] = round(float(np.mean(positives)) * 100, 2) if positives else None
        result[f"mean_end_{horizon}"] = round(float(np.mean(values)), 6) if values else None
    return result


def _write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# EXP-SEQ-CTX-01 — matriz Sequence × Context State",
        "",
        f"**Estado:** `{report['gate']}`",
        "**Política:** distribución observacional; no entry, no PnL, no promoción.",
        "",
        "| Bucket | n | +24 positivo (%) | media +24 |",
        "|---|---:|---:|---:|",
    ]
    for name in ("ALL_DEPTH4", "CTX_ALIGNED", "CTX_AGAINST", "CTX_NEUTRAL"):
        row = report["tables"][name]
        lines.append(f"| {name} | {row['n']} | {row.get('end_pos_24')} | {row.get('mean_end_24')} |")
    lines += [
        "",
        "La matriz solo es interpretable si el gate causal y el gate TNA requeridos están en PASS.",
        "Los resultados no constituyen edge operativo ni autorización de backtest.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    _require_gates()
    started = time.time()
    frames = _load_frames()
    h1 = frames["H1"]
    close = h1["close"].to_numpy(float)
    times = list(h1["time"])
    print("[matrix] run_sequential", flush=True)
    chains = run_sequential(h1, SeqConfig(structure_mode="canonical_bos"), timeframe="H1")
    depth4 = [chain for chain in chains if len(chain.nodes) >= 4]
    nav = MTFNavigator(frames, NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
    rows: list[dict[str, Any]] = []
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_bars: set[int] = set()
    for ordinal, chain in enumerate(depth4, start=1):
        structure = next((node for node in chain.nodes if node.stage.value == "STRUCTURE"), None)
        if structure is None or int(structure.bar) in seen_bars:
            continue
        bar = int(structure.bar)
        if bar < 0 or bar >= len(times):
            continue
        seen_bars.add(bar)
        state = nav.navigate(decision_time=times[bar], exec_tf="H1")
        constraints = state.constraints
        hint = constraints.direction_hint if constraints else StructureBias.UNKNOWN
        row = {
            "chain_id": chain.chain_id,
            "direction": int(chain.direction),
            "structure_bar": bar,
            "structure_time": times[bar].isoformat(),
            "depth": len(chain.nodes),
            "status": chain.status,
            "direction_hint": hint.value,
            "location": _location(state),
            "bucket": _bucket(int(chain.direction), hint),
        }
        row.update(_outcomes(close, bar, int(chain.direction)))
        rows.append(row)
        by_bucket[row["bucket"]].append(row)
        if ordinal == 1 or ordinal % 10 == 0:
            print(f"[matrix] candidates={ordinal} scored={len(rows)}", flush=True)

    tables = {"ALL_DEPTH4": _aggregate(rows)}
    tables.update({name: _aggregate(by_bucket[name]) for name in ("CTX_ALIGNED", "CTX_AGAINST", "CTX_NEUTRAL")})
    aligned = tables["CTX_ALIGNED"]
    against = tables["CTX_AGAINST"]
    delta = None
    if aligned.get("end_pos_24") is not None and against.get("end_pos_24") is not None:
        delta = round(aligned["end_pos_24"] - against["end_pos_24"], 2)
    gate = "PASS_INTERPRETABLE" if aligned["n"] >= MIN_N and against["n"] >= MIN_N else "INSUFFICIENT_N"
    report = {
        "experiment": "EXP-SEQ-CTX-01",
        "dataset": "EURUSD Dukascopy 20Y",
        "policy": "STUDY_DISTRIBUTION_NOT_ENTRY",
        "causal_gate": str(GATE.relative_to(ROOT)),
        "tna_gate": str(TNA_GATE.relative_to(ROOT)),
        "gate": gate,
        "usable_for_inference": gate == "PASS_INTERPRETABLE",
        "sequence": {"module": "engine/sequential_events.py", "structure_mode": "canonical_bos", "min_depth": 4, "summary": summarize_chains(chains), "n_scored": len(rows)},
        "context_state": {"source": "engine.mtf_navigation.MTFNavigator", "ema_used": False, "buckets": ["CTX_ALIGNED", "CTX_AGAINST", "CTX_NEUTRAL"]},
        "horizons_bars": list(HORIZONS),
        "tables": tables,
        "delta_end_pos_24_aligned_minus_against": delta,
        "rows": rows,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.time() - started, 3),
        "host": "local_pc",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    _write_markdown(report)
    print(json.dumps({"gate": gate, "n": len(rows), "out": str(OUT_JSON)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
