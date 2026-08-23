#!/usr/bin/env python3
"""Causal barrier for EXP-SEQ-CTX-01.

The gate compares the same decision timestamp in a navigator built from the
full dataset and a navigator built from every row whose timestamp is
``<= decision_time``.  It deliberately does not calculate outcomes or the
SxContext matrix: no inference is allowed until this barrier passes.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import MTFNavigator, NavigatorConfig  # noqa: E402

DATASET = ROOT / "datasets" / "eurusd_dukascopy_20y"
OUTPUT = ROOT / "reports" / "audits" / "experiments" / "seq_ctx_01" / "gate_causal.json"
TIMEFRAMES = ("D1", "H4", "H1")
DECISIONS = 120
WARMUP_H1 = 1_000


def _load_frames() -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for tf in TIMEFRAMES:
        frame = pd.read_csv(DATASET / f"EURUSD_{tf}.csv")
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
        frames[tf] = frame.sort_values("time").reset_index(drop=True)
    return frames


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "UNKNOWN"


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _diff_keys(left: Any, right: Any, prefix: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left) | set(right))
        out: list[str] = []
        for key in keys:
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                out.append(path)
            else:
                out.extend(_diff_keys(left[key], right[key], path))
        return out
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [prefix + ".length"]
        out: list[str] = []
        for index, (a, b) in enumerate(zip(left, right)):
            out.extend(_diff_keys(a, b, f"{prefix}[{index}]"))
        return out
    return [] if _jsonable(left) == _jsonable(right) else [prefix]


def main() -> int:
    started = time.time()
    frames = _load_frames()
    h1 = frames["H1"]
    if len(h1) <= WARMUP_H1:
        raise RuntimeError(f"H1 dataset too short for warmup={WARMUP_H1}")

    indices = np.linspace(WARMUP_H1, len(h1) - 1, DECISIONS, dtype=int)
    decisions = [h1.iloc[int(i)]["time"] for i in indices]
    config = NavigatorConfig(precompute_sequences=False)
    full = MTFNavigator(frames, config)
    violations: list[dict[str, Any]] = []

    for ordinal, (index, decision_time) in enumerate(zip(indices, decisions), start=1):
        # The boundary is inclusive: a bar timestamp equal to the decision is
        # visible.  This prevents a formation/confirmation off-by-one in the gate.
        prefix = {
            tf: frame.loc[frame["time"] <= decision_time]
            .copy()
            .reset_index(drop=True)
            for tf, frame in frames.items()
        }
        pref = MTFNavigator(prefix, config)
        full_state = _jsonable(full.navigate(decision_time, exec_tf="H1").to_dict())
        prefix_state = _jsonable(pref.navigate(decision_time, exec_tf="H1").to_dict())
        if full_state != prefix_state:
            violations.append(
                {
                    "ordinal": ordinal,
                    "h1_index": int(index),
                    "decision_time": _jsonable(decision_time),
                    "diff_keys": _diff_keys(full_state, prefix_state),
                    "full": full_state,
                    "prefix": prefix_state,
                }
            )
        if ordinal == 1 or ordinal % 10 == 0 or ordinal == DECISIONS:
            print(
                f"[gate] {ordinal}/{DECISIONS} decisions; violations={len(violations)}",
                flush=True,
            )

    report = {
        "experiment": "EXP-SEQ-CTX-01",
        "gate": "FULL_VS_PREFIX_CAUSAL",
        "status": "PASS" if not violations else "INVALIDATED",
        "usable_for_inference": not violations,
        "decision_count": DECISIONS,
        "warmup_h1": WARMUP_H1,
        "time_boundary": "inclusive time <= decision_time",
        "navigator_config": {"precompute_sequences": False, "swing_left": config.swing_left},
        "dataset": {
            "root": "datasets/eurusd_dukascopy_20y",
            "timeframes": list(TIMEFRAMES),
            "rows": {tf: len(frame) for tf, frame in frames.items()},
        },
        "commit": _git_commit(),
        "violations": violations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.time() - started, 3),
        "policy": "AUDIT_ONLY; no outcomes, PnL or entries",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "violations": len(violations), "out": str(OUTPUT)}), flush=True)
    return 0 if not violations else 2


if __name__ == "__main__":
    raise SystemExit(main())
