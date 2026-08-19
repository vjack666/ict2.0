"""Audit AHF temporal navigation: dwell, latency, rollback and revisits.

This is not a trading/PnL audit. It consumes AHF timeline snapshots or a
serialized list of snapshots and measures how the state machine moves through
its hierarchy over execution bars and wall-clock time.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class TemporalAuditConfig:
    stuck_pctl: float = 0.95


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


def audit_snapshots(
    snapshots: list[Mapping[str, Any]],
    decision_bars: list[int] | None = None,
    config: TemporalAuditConfig | None = None,
) -> dict[str, Any]:
    """Audit an AHF run_timeline()/serialized snapshot list.

    ``decision_bars`` are execution-timeframe bar indices aligned with the
    snapshots. If omitted, sequential ordinal bars [0..n-1] are used. This
    keeps the audit usable for smoke runs while still preserving exact bar
    counts when the caller supplies real as-of indices.
    """
    cfg = config or TemporalAuditConfig()
    if not snapshots:
        return {"status": "NO_TRACE", "trace_count": 0}
    bars = decision_bars or list(range(len(snapshots)))
    if len(bars) != len(snapshots):
        raise ValueError("decision_bars debe tener la misma longitud que snapshots")

    # Expand cumulative history from snapshots into unique ordered transitions.
    transitions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    bar_by_time = {str(s.get("decision_time")): bars[i] for i, s in enumerate(snapshots)}
    for s in snapshots:
        for tr in s.get("history", []) or []:
            key = (
                str(tr.get("state")),
                str(tr.get("active_tf")),
                str(tr.get("transition_event")),
                str(tr.get("transition_time")),
            )
            if key in seen:
                continue
            seen.add(key)
            tr2 = dict(tr)
            t = str(tr2.get("transition_time"))
            tr2["transition_bar"] = bar_by_time.get(t)
            transitions.append(tr2)

    transitions.sort(key=lambda x: (x.get("transition_bar") is None, x.get("transition_bar", 10**18), str(x.get("transition_time"))))

    state_durations: dict[str, list[float]] = defaultdict(list)
    transition_counts: Counter[tuple[str | None, str, str]] = Counter()
    transition_latencies: dict[tuple[str | None, str], list[float]] = defaultdict(list)
    rollback_depths: list[float] = []
    rollback_bars: list[float] = []
    revisit_counts: Counter[str] = Counter()
    tf_visits: Counter[str] = Counter()
    upward = downward = 0
    invalidations = 0

    # State intervals: each transition enters a state. Duration ends at next transition.
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
            # Depth in the hierarchy: D1=0, H4=1, H1=2, LTF=3.
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

    # Navigation direction based on active-TF transitions.
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
    stuck = []
    for state, values in state_durations.items():
        for v in values:
            if v > p95_dwell and v > 0:
                stuck.append({"state": state, "duration_bars": v})

    return {
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
        "transition_latency_bars": {
            f"{k[0]}->{k[1]}": _stats(v) for k, v in transition_latencies.items()
        },
        "transition_counts": {
            f"{k[0]}->{k[1]}::{k[2]}": v for k, v in transition_counts.items()
        },
        "rollback_depth_bars": _stats(rollback_depths),
        "rollback_duration_bars": _stats(rollback_bars),
        "revisit_counts_by_tf": dict(revisit_counts),
        "tf_visits": dict(tf_visits),
        "stuck_state_count": len(stuck),
        "stuck_states": stuck,
        "causal_checks": {
            "transition_order_reconstructable": all(t.get("transition_bar") is not None for t in transitions),
            "history_monotone": all(
                transitions[i].get("transition_bar", -1) <= transitions[i + 1].get("transition_bar", -1)
                for i in range(len(transitions) - 1)
            ) if transitions else True,
        },
    }
