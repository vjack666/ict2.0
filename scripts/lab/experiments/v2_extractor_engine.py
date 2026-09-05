"""Build V2 rows from the canonical engine snapshot (diagnostic only).

This extractor deliberately refuses the old M15 heuristic path. It loads all
six local EURUSD timeframes, builds causal Context State with MTFNavigator and
the existing LTF helpers, and emits a bounded decision window. It does not
modify raw data, issue orders, or certify provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_feed import load_frames
from engine.mtf_navigation import MTFNavigator, NavigatorConfig
from engine.plan import ltf_confirms, ltf_structure_at

TIMEFRAMES = ("D1", "H4", "H1", "M15", "M5", "M1")
CLASSES = ("continuation", "reversal", "failure")
TARGET = "label_end_6"


def _enum(value: Any) -> Any:
    return getattr(value, "value", value)


def _json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return _enum(value)


def _label(rows: pd.DataFrame, index: int, horizon: int = 6):
    end = index + horizon
    if end >= len(rows):
        return None, None
    delta = float(rows.iloc[end].close) - float(rows.iloc[index].close)
    if delta > 0.00005:
        label = "continuation"
    elif delta < -0.00005:
        label = "reversal"
    else:
        label = "failure"
    return label, rows.iloc[end].time.isoformat()


def _features(state: Any, stack: dict[str, Any], direction: int) -> dict[str, Any]:
    raw = state.to_dict()
    constraints = raw.get("constraints") or {}
    layers = raw.get("layers") or {}
    zones = [z for layer in layers.values() for z in (layer.get("zones") or [])]
    counts = {"poi_count": 0, "bsl_count": 0, "ssl_count": 0, "dealing_count": 0}
    for zone in zones:
        kind = str(zone.get("kind", "")).upper()
        if kind == "BSL":
            counts["bsl_count"] += 1
        elif kind == "SSL":
            counts["ssl_count"] += 1
        elif kind == "DEALING":
            counts["dealing_count"] += 1
        else:
            counts["poi_count"] += 1
    micro = {tf: stack.get(tf) or {} for tf in ("M5", "M1")}
    m5 = micro["M5"]
    m1 = micro["M1"]
    last_close = next((layer.get("last_close") for layer in layers.values() if layer.get("last_close") is not None), None)
    distances = [abs(float(last_close) - (float(z["low"]) + float(z["high"])) / 2.0) for z in zones if last_close is not None and z.get("low") is not None and z.get("high") is not None]
    proximity = min(distances) if distances else None
    regime_stack = {tf: layer.get("regime", "UNKNOWN") for tf, layer in layers.items() if tf in ("D1", "H4", "H1")}
    bos_htf = {tf: {"bullish": layer.get("last_bos_direction") == 1, "bearish": layer.get("last_bos_direction") == -1} for tf, layer in layers.items() if tf in ("D1", "H4", "H1")}
    return {
        "schema_group": "engine_v2",
        "direction": direction,
        "sequence_depth": 0,
        "context_state": {
            "status": raw.get("status"),
            "direction_hint": _enum(constraints.get("direction_hint")),
            "layer_status": {tf: "OK" for tf in layers},
            "layers": layers,
            "regime_stack": regime_stack,
            "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
        },
        "zones": {
            "poi": {"count": counts["poi_count"]},
            "bsl": {"count": counts["bsl_count"]},
            "ssl": {"count": counts["ssl_count"]},
            "dealing": {"count": counts["dealing_count"]},
            "proximity": proximity,
            **counts,
        },
        "bos_htf": bos_htf,
        "context_inputs": {"sequence_direction": direction},
        "intraday": {
            "ict_m15": {
                "bos_bullish": bool((layers.get("M15", {}).get("last_bos_direction") == 1)),
                "bos_bearish": bool((layers.get("M15", {}).get("last_bos_direction") == -1)),
                "choch_bullish": False, "choch_bearish": False,
                "displacement_bullish": bool(layers.get("M15", {}).get("displacement_recent") and direction == 1),
                "displacement_bearish": bool(layers.get("M15", {}).get("displacement_recent") and direction == -1),
                "fvg_bullish": False, "fvg_bearish": False, "sweep_up": False, "sweep_down": False,
            },
            "wyckoff": {
                tf: {"phase": {"TREND_BULL": "MARKUP", "TREND_BEAR": "MARKDOWN", "RANGE": "RANGE_UNCLASSIFIED", "COMPRESSION": "RANGE_UNCLASSIFIED"}.get(layers.get(tf, {}).get("regime"), "UNKNOWN"), "events": []}
                for tf in ("H1", "M15")
            },
        },
        "lifecycle": {"stage": "CONTEXT_OBSERVATION"},
        "M5": {
            "m5_bos": int(m5.get("bos_dir", 0) or 0) != 0 if m5.get("available") else None,
            "m5_displacement": bool(m5.get("momentum", 0)) if m5.get("available") else None,
            "m5_fvg": None,
        },
        "M1": {
            "m1_trigger": int(m1.get("bos_dir", 0) or 0) != 0 if m1.get("available") else None,
            "m1_retest": None,
        },
        "permissions": {
            "allow_long": constraints.get("allow_long"),
            "allow_short": constraints.get("allow_short"),
        },
        "lineage": {"available": False, "depth": None, "count": None},
        "reason_codes": list(constraints.get("notes") or []),
        "micro_confirmation": ltf_confirms(stack, direction),
    }


def _micro_stack(frames: dict[str, pd.DataFrame], t: pd.Timestamp) -> dict[str, Any]:
    """Compute M5/M1 from bounded closed prefixes, avoiding O(n²) scans."""
    stack: dict[str, Any] = {}
    for tf in ("M5", "M1"):
        frame = frames[tf]
        times = frame["time"]
        end = int(times.searchsorted(t, side="right"))
        bounded = frame.iloc[max(0, end - 120):end].reset_index(drop=True)
        stack[tf] = ltf_structure_at({tf: bounded}, tf, t)
    return stack


def extract(start: str, end: str, output: Path, data_dir: Path) -> dict[str, Any]:
    # Keep a bounded warmup for causal indicators; never precompute millions
    # of M1 rows outside the requested window.
    start_ts = pd.Timestamp(start, tz="UTC")
    warmup = (start_ts - pd.Timedelta(days=62)).isoformat()
    frames = load_frames("EURUSD", TIMEFRAMES, data_dir=data_dir, start=warmup, end=end)
    missing = [tf for tf in TIMEFRAMES if frames[tf].empty]
    if missing:
        raise RuntimeError(f"MISSING_CANONICAL_TIMEFRAMES:{','.join(missing)}")
    m15 = frames["M15"]
    window = m15[(m15.time >= start_ts) & (m15.time <= pd.Timestamp(end, tz="UTC"))].reset_index(drop=True)
    if window.empty:
        raise RuntimeError("EMPTY_DECISION_WINDOW")
    nav = MTFNavigator(frames, NavigatorConfig(precompute_sequences=False))
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for _, bar in window.iterrows():
        t = bar.time
        key = t.isoformat()
        try:
            state = nav.navigate(t, exec_tf="M15")
            stack = _micro_stack(frames, t)
            direction = _enum((state.to_dict().get("constraints") or {}).get("direction_hint"))
            direction = 1 if direction in (1, "1", "BULLISH") else -1 if direction in (-1, "-1", "BEARISH") else 0
            label, label_end_time = _label(m15, int(m15.index[m15.time == t][0]))
            if label is None:
                rejected.append({"decision_time": key, "reason": "no_label_window"})
                continue
            rows.append({
                "episode_id": f"EP-ENGINE-M15-{t.strftime('%Y%m%dT%H%M%SZ')}",
                "decision_time": key,
                "label_end_time": label_end_time,
                "label": label,
                TARGET: label,
                "features_at_t": _json(_features(state, stack, direction)),
                "engine_snapshot": _json(state.to_dict()),
                "can_trade": False,
                "shadow_mode": True,
                "diagnostic_only": True,
                "source_auth": "EURUSD_LOCAL_PARQUET_ENGINE",
                "target": TARGET,
                "direction": direction,
            })
        except Exception as exc:
            rejected.append({"decision_time": key, "reason": f"engine_error:{type(exc).__name__}"})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    source_files = {}
    for tf in TIMEFRAMES:
        path = data_dir / f"EURUSD_{tf}.parquet"
        source_files[tf] = {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "status": "BLOCKED_PROVENANCE_PENDING",
        "source": "EURUSD_LOCAL_PARQUET_ENGINE",
        "start": start,
        "end": end,
        "timeframes": TIMEFRAMES,
        "target": TARGET,
        "classes": CLASSES,
        "rows": len(rows),
        "rejected": len(rejected),
        "rejection_reasons": pd.Series([r["reason"] for r in rejected]).value_counts().to_dict() if rejected else {},
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "source_files": source_files,
        "can_trade": False,
        "training_eligible": False,
        "diagnostic_only": True,
        "note": "Engine features are causal; provenance/license and source acquisition remain unaudited.",
    }
    output.with_suffix(output.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    output.with_suffix(output.suffix + ".rejected.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rejected), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-02T00:00:00Z")
    parser.add_argument("--end", default="2022-03-31T23:59:59Z")
    parser.add_argument("--output", type=Path, default=Path("data/materialized/v2/v2_engine_2022_q1.jsonl"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/EURUSD"))
    args = parser.parse_args()
    print(json.dumps(extract(args.start, args.end, args.output, args.data_dir), indent=2, sort_keys=True))
