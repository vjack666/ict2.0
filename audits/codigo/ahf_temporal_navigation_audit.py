"""Audit AHF temporal navigation plus descriptive FVG/OB magnitude.

This is not a trading/PnL audit. It measures state navigation, dwell,
rollback/revisits and, when object records are supplied, FVG/OB size and
post-object favorable/adverse price excursion in pips.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class TemporalAuditConfig:
    stuck_pctl: float = 0.95
    default_pip_size: float = 0.0001
    object_windows: tuple[int, ...] = (1, 3, 6, 12, 24, 48)


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def _stats(values: Iterable[float]) -> dict[str, float | int | None]:
    xs = [float(v) for v in values]
    if not xs:
        return {"n": 0, "min": None, "median": None, "mean": None, "p75": None, "p90": None, "p95": None, "max": None}
    return {
        "n": len(xs),
        "min": min(xs),
        "median": median(xs),
        "mean": mean(xs),
        "p75": _percentile(xs, 0.75),
        "p90": _percentile(xs, 0.90),
        "p95": _percentile(xs, 0.95),
        "max": max(xs),
    }


def _pip_size_for_object(obj: Mapping[str, Any], default: float) -> float:
    value = obj.get("pip_size")
    return float(value) if value is not None else float(default)


def audit_object_excursions(
    objects: Iterable[Mapping[str, Any]],
    price_frames: Mapping[str, Any],
    config: TemporalAuditConfig | None = None,
) -> dict[str, Any]:
    """Measure FVG/OB size and future-only excursion in pips.

    Object schema requires at least:
      object_id, object_type (FVG|OB), tf, birth_bar, direction,
      zone_low, zone_high, reference_price.

    ``price_frames[tf]`` must expose a ``high`` and ``low`` sequence. Only
    bars strictly after ``birth_bar`` are inspected. This function is
    descriptive: it does not define TP, SL, entry, R, or PnL.
    """
    cfg = config or TemporalAuditConfig()
    rows: list[dict[str, Any]] = []
    by_group: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for obj in objects:
        tf = str(obj["tf"]).upper()
        kind = str(obj["object_type"]).upper()
        direction = str(obj["direction"]).lower()
        if kind not in {"FVG", "OB"}:
            continue
        if tf not in price_frames:
            continue
        df = price_frames[tf]
        birth = int(obj["birth_bar"])
        ref = float(obj["reference_price"])
        low = float(obj["zone_low"])
        high = float(obj["zone_high"])
        pip = _pip_size_for_object(obj, cfg.default_pip_size)
        if pip <= 0:
            raise ValueError("pip_size must be positive")

        highs = list(df["high"])
        lows = list(df["low"])
        size_pips = abs(high - low) / pip
        row: dict[str, Any] = {
            "object_id": obj.get("object_id"),
            "object_type": kind,
            "tf": tf,
            "direction": direction,
            "birth_bar": birth,
            "reference_price": ref,
            "reference_rule": obj.get("reference_rule", "close_at_object_confirmation"),
            "size_pips": size_pips,
            "windows": {},
        }

        for h in cfg.object_windows:
            start = birth + 1
            end = min(len(highs), birth + h + 1)
            if start >= end:
                row["windows"][str(h)] = None
                continue
            fh = max(float(x) for x in highs[start:end])
            fl = min(float(x) for x in lows[start:end])
            if direction in {"bullish", "bull", "long", "+1", "1"}:
                fav = (fh - ref) / pip
                adv = (ref - fl) / pip
            elif direction in {"bearish", "bear", "short", "-1"}:
                fav = (ref - fl) / pip
                adv = (fh - ref) / pip
            else:
                raise ValueError(f"unknown object direction: {direction}")
            end_close = float(df["close"].iloc[end - 1])
            signed_end = ((end_close - ref) / pip) if direction in {"bullish", "bull", "long", "+1", "1"} else ((ref - end_close) / pip)
            row["windows"][str(h)] = {
                "max_favorable_pips": fav,
                "max_adverse_pips": adv,
                "end_move_pips": signed_end,
                "bars_to_max_favorable": None,
                "bars_to_max_adverse": None,
            }

        rows.append(row)
        by_group[(tf, kind, direction)].append(row)

    aggregated: dict[str, Any] = {}
    for (tf, kind, direction), group in by_group.items():
        key = f"{tf}|{kind}|{direction}"
        aggregated[key] = {
            "object_count": len(group),
            "size_pips": _stats([float(r["size_pips"]) for r in group]),
            "windows": {},
        }
        for h in cfg.object_windows:
            vals = [r["windows"][str(h)] for r in group if r["windows"].get(str(h)) is not None]
            aggregated[key]["windows"][str(h)] = {
                "favorable_pips": _stats([float(v["max_favorable_pips"]) for v in vals]),
                "adverse_pips": _stats([float(v["max_adverse_pips"]) for v in vals]),
                "end_move_pips": _stats([float(v["end_move_pips"]) for v in vals]),
            }

    return {
        "policy": "DESCRIPTIVE_OBJECT_MAGNITUDE_NOT_TP_SL",
        "object_count": len(rows),
        "pip_size_default": cfg.default_pip_size,
        "windows": list(cfg.object_windows),
        "objects": rows,
        "aggregated": aggregated,
    }


def audit_snapshots(
    snapshots: list[Mapping[str, Any]],
    decision_bars: list[int] | None = None,
    config: TemporalAuditConfig | None = None,
    objects: Iterable[Mapping[str, Any]] | None = None,
    price_frames: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit AHF run_timeline()/serialized snapshots plus optional FVG/OB metrics."""
    cfg = config or TemporalAuditConfig()
    if not snapshots:
        return {"status": "NO_TRACE", "trace_count": 0}
    bars = decision_bars or list(range(len(snapshots)))
    if len(bars) != len(snapshots):
        raise ValueError("decision_bars debe tener la misma longitud que snapshots")

    transitions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    bar_by_time = {str(s.get("decision_time")): bars[i] for i, s in enumerate(snapshots)}
    for s in snapshots:
        for tr in s.get("history", []) or []:
            key = (str(tr.get("state")), str(tr.get("active_tf")), str(tr.get("transition_event")), str(tr.get("transition_time")))
            if key in seen:
                continue
            seen.add(key)
            tr2 = dict(tr)
            tr2["transition_bar"] = bar_by_time.get(str(tr2.get("transition_time")))
            transitions.append(tr2)

    transitions.sort(key=lambda x: (x.get("transition_bar") is None, x.get("transition_bar", 10**18), str(x.get("transition_time"))))
    state_durations: dict[str, list[float]] = defaultdict(list)
    transition_counts: Counter[tuple[str | None, str, str]] = Counter()
    transition_latencies: dict[tuple[str | None, str], list[float]] = defaultdict(list)
    rollback_depths: list[float] = []
    rollback_bars: list[float] = []
    revisit_counts: Counter[str] = Counter()
    tf_visits: Counter[str] = Counter()
    downward = upward = invalidations = 0

    for i, tr in enumerate(transitions):
        state = str(tr.get("state"))
        tf = str(tr.get("active_tf"))
        tf_visits[tf] += 1
        start = tr.get("transition_bar")
        next_tr = transitions[i + 1] if i + 1 < len(transitions) else None
        end = next_tr.get("transition_bar") if next_tr else (bars[-1] if bars else None)
        if start is not None and end is not None and end >= start:
            state_durations[state].append(float(end - start))
        parent = tr.get("parent_state")
        event = str(tr.get("transition_event"))
        transition_counts[(str(parent) if parent is not None else None, state, event)] += 1
        if next_tr and start is not None and next_tr.get("transition_bar") is not None:
            transition_latencies[(state, str(next_tr.get("state")))].append(float(next_tr["transition_bar"] - start))
        if "INVALIDATED" in event:
            invalidations += 1
            order = {"D1": 0, "H4": 1, "H1": 2, "M15": 3, "M5": 4}
            parent_tf = str(parent) if parent else ""
            target_tf = {"D1_INVALIDATED": "D1", "H4_INVALIDATED": "H4", "H1_INVALIDATED": "H1"}.get(event, tf)
            prev_level = order.get(parent_tf.replace("_LOCKED", ""), order.get(parent_tf, 0))
            target_level = order.get(target_tf, prev_level)
            rollback_depths.append(float(max(0, prev_level - target_level)))
            if start is not None and next_tr and next_tr.get("transition_bar") is not None:
                rollback_bars.append(float(max(0, next_tr["transition_bar"] - start)))
        if i > 0 and transitions[i - 1].get("active_tf") == tf:
            revisit_counts[tf] += 1

    order = {"D1": 0, "H4": 1, "H1": 2, "M15": 3, "M5": 4}
    for a, b in zip(transitions, transitions[1:]):
        la, lb = order.get(str(a.get("active_tf"))), order.get(str(b.get("active_tf")))
        if la is None or lb is None:
            continue
        if lb > la:
            downward += 1
        elif lb < la:
            upward += 1

    max_depth = max((order.get(str(t.get("active_tf")), -1) for t in transitions), default=-1)
    final_state = str(snapshots[-1].get("state"))
    dwell_values = [d for values in state_durations.values() for d in values]
    p95_dwell = _percentile(dwell_values, cfg.stuck_pctl) or 0.0
    stuck = [{"state": state, "duration_bars": v} for state, values in state_durations.items() for v in values if v > p95_dwell and v > 0]

    result: dict[str, Any] = {
        "status": "PASS_TRACE_INTEGRITY",
        "policy": "AHF_STATE_NOT_ENTRY",
        "trace_count": len(snapshots),
        "transition_count": len(transitions),
        "final_state": final_state,
        "max_tf_depth": max_depth,
        "downward_switches": downward,
        "upward_switches": upward,
        "invalidations": invalidations,
        "state_durations_bars": {k: _stats(v) for k, v in state_durations.items()},
        "transition_latency_bars": {f"{k[0]}->{k[1]}": _stats(v) for k, v in transition_latencies.items()},
        "transition_counts": {f"{k[0]}->{k[1]}::{k[2]}": v for k, v in transition_counts.items()},
        "rollback_depth_bars": _stats(rollback_depths),
        "rollback_duration_bars": _stats(rollback_bars),
        "revisit_counts_by_tf": dict(revisit_counts),
        "tf_visits": dict(tf_visits),
        "stuck_state_count": len(stuck),
        "stuck_states": stuck,
        "causal_checks": {
            "transition_order_reconstructable": all(t.get("transition_bar") is not None for t in transitions),
            "history_monotone": all(transitions[i].get("transition_bar", -1) <= transitions[i + 1].get("transition_bar", -1) for i in range(len(transitions) - 1)) if transitions else True,
        },
    }

    if objects is not None and price_frames is not None:
        result["object_magnitude"] = audit_object_excursions(objects, price_frames, cfg)
    else:
        result["object_magnitude"] = {"status": "NOT_SUPPLIED", "policy": "DESCRIPTIVE_OBJECT_MAGNITUDE_NOT_TP_SL"}

    return result
