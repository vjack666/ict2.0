"""Forensic helpers for six-TF Episode backtests.

This module is an isolated backtest-side consumer.  It audits already-produced
Episodes, classifies London/New York sessions, summarizes weekly frequency, and
builds a shadow-analysis dataset.  It does not create signals, train models,
connect MT5, or authorize trading.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd

CORE_ROLES: tuple[str, ...] = ("refinement", "confirmation", "trigger")
LABEL_FIELDS: set[str] = {
    "exit_status",
    "exit_time",
    "exit_price",
    "exit_r",
    "net_R",
    "gross_pnl_cash",
    "initial_risk_cash",
    "cost_cash",
    "economic_status",
}
UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start: datetime
    end: datetime


def _utc(value: Any) -> pd.Timestamp:
    result = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(result):
        raise ValueError(f"invalid timestamp: {value!r}")
    return result


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return _utc(value).isoformat()


def session_windows(trading_day: date) -> tuple[SessionWindow, SessionWindow]:
    """Canonical 08:00-12:00 London and New York local windows."""

    def window(name: str, zone: ZoneInfo) -> SessionWindow:
        start = datetime.combine(trading_day, time(8), tzinfo=zone).astimezone(UTC)
        end = datetime.combine(trading_day, time(12), tzinfo=zone).astimezone(UTC)
        return SessionWindow(name, start, end)

    return window("LONDON", LONDON), window("NEW_YORK", NEW_YORK)


def classify_session(decision_time: Any) -> dict[str, Any]:
    stamp = _utc(decision_time).to_pydatetime()
    london, new_york = session_windows(stamp.date())
    in_london = london.start <= stamp < london.end
    in_new_york = new_york.start <= stamp < new_york.end
    if in_london and in_new_york:
        name = "OVERLAP"
    elif in_london:
        name = "LONDON"
    elif in_new_york:
        name = "NEW_YORK"
    else:
        name = "OFF_SESSION"
    return {
        "session": name,
        "in_london": in_london,
        "in_new_york": in_new_york,
        "london_window_utc": {"start": london.start.isoformat(), "end": london.end.isoformat()},
        "new_york_window_utc": {"start": new_york.start.isoformat(), "end": new_york.end.isoformat()},
    }


def _component_meta(episode: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return dict((episode.get("meta") or {}).get("component_audit") or {})


def _component_time(component: Mapping[str, Any], key: str) -> pd.Timestamp | None:
    value = component.get(key)
    if value in {None, "NONE", ""}:
        return None
    return _utc(value)


def audit_episode_sequence(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Audit temporal evidence for one Episode.

    ``PASS`` means no hard defect was found.  ``REVIEW`` means evidence is
    incomplete or suspicious but not mechanically impossible.  ``BLOCKED``
    means the episode should not enter calibration/AI as valid evidence.
    """

    decision_time = _utc(episode["decision_time"])
    components = _component_meta(episode)
    reasons: list[str] = []
    review: list[str] = []
    role_times: dict[str, str | None] = {}
    role_bars: dict[str, Any] = {}

    if not components:
        review.append("MISSING_COMPONENT_AUDIT")

    prior: pd.Timestamp | None = None
    for role in ("context_htf", "poi", "refinement", "confirmation", "trigger"):
        component = components.get(role) or {}
        candidate = _component_time(component, "candidate_time") or _component_time(component, "creation_time")
        confirmation = _component_time(component, "confirmation_time")
        tradable = _component_time(component, "tradable_time")
        role_times[role] = _iso(candidate) if candidate is not None else None
        role_bars[role] = component.get("bar_index")
        for label, stamp in (("candidate_time", candidate), ("confirmation_time", confirmation), ("tradable_time", tradable)):
            if stamp is not None and stamp > decision_time:
                reasons.append("FUTURE_CONTEXT")
        if confirmation is not None and tradable is not None and confirmation > tradable:
            reasons.append("TEMPORAL_ORDER")
        if tradable is not None and tradable > decision_time:
            reasons.append("TEMPORAL_ORDER")
        if component and component.get("closed_bar_only") is not True:
            reasons.append("HTF_NOT_CLOSED")
        if candidate is not None:
            if prior is not None and candidate < prior:
                reasons.append("TEMPORAL_ORDER")
            prior = candidate

    core_times = [
        _component_time(components.get(role) or {}, "candidate_time")
        or _component_time(components.get(role) or {}, "creation_time")
        for role in CORE_ROLES
    ]
    core_bars = [role_bars.get(role) for role in CORE_ROLES]
    if all(ts is not None for ts in core_times) and len({ts for ts in core_times if ts is not None}) == 1:
        reasons.append("SAME_TIMESTAMP_STAGE")
    if all(bar is not None for bar in core_bars) and len(set(core_bars)) == 1:
        reasons.append("SAME_BAR_CORE_STAGE")

    # The current six-TF connector emits synthetic objects with candidate,
    # confirmation and tradable times equal per component.  That is not a hard
    # causal violation, but it is exactly the compression risk this mission
    # needs to expose before AI calibration.
    compressed_roles = []
    for role, component in components.items():
        times = {
            component.get("candidate_time"),
            component.get("confirmation_time"),
            component.get("tradable_time"),
        }
        if len({t for t in times if t}) == 1 and times != {None}:
            compressed_roles.append(role)
    if compressed_roles:
        review.append("SYNTHETIC_STAGE_COMPRESSION")

    unique_reasons = sorted(set(reasons))
    unique_review = sorted(set(review))
    status = "BLOCKED" if unique_reasons else ("REVIEW" if unique_review else "PASS")
    return {
        "episode_id": episode.get("episode_id"),
        "decision_time": decision_time.isoformat(),
        "sequence_audit_status": status,
        "reasons": unique_reasons,
        "review_flags": unique_review,
        "role_times": role_times,
        "role_bars": role_bars,
    }


def audit_episodes(episodes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [audit_episode_sequence(episode) for episode in episodes]
    statuses = Counter(row["sequence_audit_status"] for row in rows)
    reason_counts = Counter(reason for row in rows for reason in row["reasons"])
    review_counts = Counter(flag for row in rows for flag in row["review_flags"])
    return {
        "artifact_kind": "SIXTF_FORENSIC_AUDIT_V1",
        "sequence_audit_status": "BLOCKED"
        if statuses.get("BLOCKED", 0)
        else ("REVIEW" if statuses.get("REVIEW", 0) else "PASS"),
        "counts": dict(sorted(statuses.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "review_flag_counts": dict(sorted(review_counts.items())),
        "episodes": rows,
    }


def attach_sessions(trades: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        row.update(classify_session(row["decision_time"]))
        out.append(row)
    return out


def summarize_by_session(trades: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for trade in trades:
        buckets[str(trade.get("session", "UNKNOWN"))].append(trade)
    return {name: _summarize_bucket(rows) for name, rows in sorted(buckets.items())}


def weekly_frequency(trades: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for trade in trades:
        week = _utc(trade["decision_time"]).strftime("%G-W%V")
        buckets[week].append(trade)
    return {week: _summarize_bucket(rows) for week, rows in sorted(buckets.items())}


def _summarize_bucket(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    resolved = [row for row in rows if row.get("net_R") is not None]
    return {
        "trade_count": len(rows),
        "resolved_count": len(resolved),
        "tp_count": sum(1 for row in rows if row.get("exit_status") == "TP"),
        "sl_count": sum(1 for row in rows if row.get("exit_status") == "SL"),
        "horizon_count": sum(1 for row in rows if row.get("exit_status") == "HORIZON"),
        "sum_net_R": sum(float(row["net_R"]) for row in resolved),
        "mean_net_R": (
            sum(float(row["net_R"]) for row in resolved) / len(resolved)
            if resolved
            else None
        ),
    }


def classify_failure(trade: Mapping[str, Any], audit: Mapping[str, Any]) -> str:
    if audit.get("sequence_audit_status") == "BLOCKED":
        return "MOTOR_SEQUENCE"
    if audit.get("sequence_audit_status") == "REVIEW":
        return "MOTOR_REVIEW"
    if trade.get("session") == "OFF_SESSION":
        return "SESSION"
    if trade.get("exit_status") == "HORIZON":
        return "HORIZON"
    if trade.get("net_R") is not None and float(trade["net_R"]) <= 0:
        return "CALIBRATION_OR_CONTEXT"
    return "PASS_OR_UNCLASSIFIED"


def failure_taxonomy(trades: Iterable[Mapping[str, Any]], audit_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    audits = {row.get("episode_id"): row for row in audit_rows}
    counts: Counter[str] = Counter()
    for trade in trades:
        counts[classify_failure(trade, audits.get(trade.get("episode_id"), {}))] += 1
    return dict(sorted(counts.items()))


def build_ai_shadow_dataset(
    trades: Iterable[Mapping[str, Any]],
    audit_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    audits = {row.get("episode_id"): row for row in audit_rows}
    rows: list[dict[str, Any]] = []
    leakage: list[str] = []
    for trade in trades:
        audit = audits.get(trade.get("episode_id"), {})
        session = str(trade.get("session", "UNKNOWN"))
        features = {
            "episode_id": trade.get("episode_id"),
            "decision_time": trade.get("decision_time"),
            "direction": trade.get("direction"),
            "session": session,
            "in_london": bool(trade.get("in_london", False)),
            "in_new_york": bool(trade.get("in_new_york", False)),
            "risk_pips": trade.get("risk_pips"),
            "reward_r": trade.get("reward_r"),
            "horizon_m1_bars": trade.get("horizon_m1_bars"),
            "component_tfs": dict(trade.get("component_tfs", {})),
            "object_ref_count": len(trade.get("object_refs", [])),
            "sequence_audit_status": audit.get("sequence_audit_status", "MISSING"),
            "forensic_reason_count": len(audit.get("reasons", [])),
            "forensic_review_count": len(audit.get("review_flags", [])),
        }
        labels = {
            "exit_status": trade.get("exit_status"),
            "net_R": trade.get("net_R"),
            "economic_status": trade.get("economic_status"),
        }
        overlap = sorted(set(features) & LABEL_FIELDS)
        leakage.extend(overlap)
        if audit.get("sequence_audit_status") == "BLOCKED":
            decision = "RECHAZAR_ANALISIS"
        elif audit.get("sequence_audit_status") == "REVIEW" or session == "OFF_SESSION":
            decision = "ABSTENERSE"
        else:
            decision = "ACEPTAR_ANALISIS"
        rows.append({"features": features, "labels": labels, "ai_shadow_decision": decision})
    return {
        "artifact_kind": "SIXTF_AI_SHADOW_DATASET_V1",
        "policy": {
            "can_trade": False,
            "shadow_only": True,
            "orders_sent": False,
            "mt5_connected": False,
            "labels_are_post_hoc": True,
        },
        "feature_label_leakage_pass": not leakage,
        "leakage_fields": sorted(set(leakage)),
        "decision_counts": dict(sorted(Counter(row["ai_shadow_decision"] for row in rows).items())),
        "rows": rows,
    }


__all__ = [
    "audit_episode_sequence",
    "audit_episodes",
    "attach_sessions",
    "build_ai_shadow_dataset",
    "classify_session",
    "failure_taxonomy",
    "session_windows",
    "summarize_by_session",
    "weekly_frequency",
]
