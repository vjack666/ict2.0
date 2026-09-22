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
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd

from engine.killzone import killzone_en
from engine.mtf_navigation import MTFNavigator
from engine.po3 import build_po3_state
from engine.silver_bullet import is_silver_bullet
from engine.sequential_events import SeqConfig, run_sequential, summarize_chains
from engine.turtle_soup import is_turtle_soup

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


def audit_episode_sequence(
    episode: Mapping[str, Any],
    sequence_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
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
    sequence_evidence = dict(sequence_evidence or {})
    real_sequence_pass = sequence_evidence.get("sequence_status") == "PASS"
    if real_sequence_pass:
        # Real multi-bar evidence from engine.sequential_events supersedes the
        # synthetic timestamp compression of the six-TF connector.  Keep the
        # compression flag as diagnostic context, but do not let it block AI
        # shadow analysis when a strict real chain exists before decision_time.
        unique_review = [flag for flag in unique_review if flag != "SYNTHETIC_STAGE_COMPRESSION"]
        unique_reasons = [
            reason
            for reason in unique_reasons
            if reason not in {"SAME_TIMESTAMP_STAGE", "SAME_BAR_CORE_STAGE"}
        ]
    status = "BLOCKED" if unique_reasons else ("REVIEW" if unique_review else "PASS")
    return {
        "episode_id": episode.get("episode_id"),
        "decision_time": decision_time.isoformat(),
        "sequence_audit_status": status,
        "reasons": unique_reasons,
        "review_flags": unique_review,
        "sequence_evidence": sequence_evidence,
        "role_times": role_times,
        "role_bars": role_bars,
    }


def audit_episodes(
    episodes: Iterable[Mapping[str, Any]],
    sequence_evidence_by_episode: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence = sequence_evidence_by_episode or {}
    rows = [
        audit_episode_sequence(episode, evidence.get(str(episode.get("episode_id")), {}))
        for episode in episodes
    ]
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


def _row_time(frame: pd.DataFrame, bar: int) -> str | None:
    if bar < 0 or bar >= len(frame) or "time" not in frame.columns:
        return None
    return _utc(frame.iloc[bar]["time"]).isoformat()


def build_sequence_evidence(
    episodes: Iterable[Mapping[str, Any]],
    ltf_frame: pd.DataFrame,
    *,
    timeframe: str = "M1",
    config: SeqConfig | None = None,
) -> dict[str, Any]:
    """Attach real sequential-event evidence to Episodes.

    The sequential engine is run once over the closed LTF frame.  For each
    episode, the latest COMPLETE chain with matching direction and last_bar at
    or before decision_time is selected.  This does not create a trade; it only
    proves whether a real multi-bar sequence existed before the episode.
    """
    cfg = config or SeqConfig(max_active_chains=128)
    frame = ltf_frame.copy().reset_index(drop=True)
    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    chains = run_sequential(frame, cfg, timeframe=timeframe)
    complete = [chain for chain in chains if chain.status == "COMPLETE"]
    evidence: dict[str, Mapping[str, Any]] = {}
    for episode in episodes:
        decision_time = _utc(episode["decision_time"])
        direction = int(episode.get("direction", 0))
        selected = None
        selected_time = None
        for chain in complete:
            if int(chain.direction) != direction:
                continue
            last_time = _row_time(frame, int(chain.last_bar))
            if last_time is None:
                continue
            stamp = _utc(last_time)
            if stamp <= decision_time and (selected_time is None or stamp > selected_time):
                selected = chain
                selected_time = stamp
        if selected is None:
            evidence[str(episode.get("episode_id"))] = {
                "sequence_status": "REVIEW",
                "reason": "NO_COMPLETE_REAL_SEQUENCE_BEFORE_DECISION",
                "timeframe": timeframe,
            }
            continue
        nodes = []
        for node in selected.nodes:
            node_dict = node.to_dict()
            node_dict["time"] = _row_time(frame, int(node.bar))
            nodes.append(node_dict)
        strict_bars = [int(node["bar"]) for node in nodes]
        evidence[str(episode.get("episode_id"))] = {
            "sequence_status": "PASS",
            "timeframe": timeframe,
            "chain_id": selected.chain_id,
            "chain_status": selected.status,
            "chain_direction": int(selected.direction),
            "last_bar_time": selected_time.isoformat() if selected_time is not None else None,
            "stage_count": len(nodes),
            "stages": [node["stage"] for node in nodes],
            "strictly_increasing_bars": all(b > a for a, b in zip(strict_bars, strict_bars[1:])),
            "nodes": nodes,
        }
    return {
        "artifact_kind": "SIXTF_REAL_SEQUENCE_EVIDENCE_V1",
        "timeframe": timeframe,
        "sequential_summary": summarize_chains(chains),
        "complete_chain_count": len(complete),
        "evidence_by_episode": evidence,
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


def _node_by_stage(sequence_evidence: Mapping[str, Any], stage: str) -> Mapping[str, Any] | None:
    for node in sequence_evidence.get("nodes", []) or []:
        if node.get("stage") == stage:
            return node
    return None


def classify_entry_protocols(
    episode: Mapping[str, Any],
    audit: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    *,
    ltf: str = "M1",
) -> dict[str, Any]:
    """Classify PO3, Turtle Soup and Silver Bullet for one audited episode."""
    seq = dict(audit.get("sequence_evidence") or {})
    direction = int(episode.get("direction", 0) or 0)
    bias = "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL"
    sweep = _node_by_stage(seq, "SWEEP")
    structure = _node_by_stage(seq, "STRUCTURE")
    ob = _node_by_stage(seq, "OB")
    fvg = _node_by_stage(seq, "FVG")
    retest = _node_by_stage(seq, "RETEST")
    sweep_time = sweep.get("time") if sweep else None
    retest_time = retest.get("time") if retest else None
    sweep_detail = str((sweep or {}).get("detail") or "")
    sweep_down = "EQL" in sweep_detail or direction > 0
    sweep_up = "EQH" in sweep_detail or direction < 0
    structure_dict = {
        "H4": {"trend": bias},
        ltf: {
            "sweep_up": sweep_up,
            "sweep_down": sweep_down,
            "bos_dir": direction if structure else 0,
            "bos_status": "active" if structure else "",
            "fvg_state": "active" if fvg else "none",
            "ob_dir": "bullish" if ob and direction > 0 else "bearish" if ob and direction < 0 else "none",
        },
    }
    po3_state = build_po3_state(structure_dict, bias=bias, exec_tf=ltf, htf="H4")
    turtle_ok, turtle_meta = is_turtle_soup(sweep_time, direction, dict(frames), ltf=ltf)
    silver_ok, silver_meta = is_silver_bullet(sweep_time, retest_time, direction, killzone_en)
    families = {
        "PO3": {
            "complete": bool(po3_state.complete),
            "phases": po3_state.phases_present(),
            "direction": po3_state.direction,
            "aligned": po3_state.aligned,
            "incomplete_reason": list(po3_state.incomplete_reason),
        },
        "TURTLE_SOUP": {
            "complete": bool(turtle_ok),
            **turtle_meta,
        },
        "SILVER_BULLET": {
            "complete": bool(silver_ok),
            **silver_meta,
        },
    }
    complete = [name for name, payload in families.items() if payload.get("complete")]
    return {
        "artifact_kind": "ICT_ENTRY_PROTOCOL_CLASSIFICATION_V1",
        "episode_id": episode.get("episode_id"),
        "decision_time": episode.get("decision_time"),
        "ltf": ltf,
        "sequence_status": seq.get("sequence_status"),
        "complete_families": complete,
        "primary_family": complete[0] if complete else "NONE",
        "families": families,
        "can_trade": False,
        "entry_authorized": False,
    }


def classify_entry_protocols_for_episodes(
    episodes: Iterable[Mapping[str, Any]],
    audit_rows: Iterable[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    *,
    ltf: str = "M1",
) -> dict[str, Any]:
    audits = {row.get("episode_id"): row for row in audit_rows}
    by_episode = {
        str(episode.get("episode_id")): classify_entry_protocols(
            episode,
            audits.get(episode.get("episode_id"), {}),
            frames,
            ltf=ltf,
        )
        for episode in episodes
    }
    counts = Counter()
    primary = Counter()
    for item in by_episode.values():
        complete = item.get("complete_families", [])
        if complete:
            for family in complete:
                counts[family] += 1
            primary[item.get("primary_family", "NONE")] += 1
        else:
            primary["NONE"] += 1
    return {
        "artifact_kind": "ICT_ENTRY_PROTOCOL_SUMMARY_V1",
        "counts_by_complete_family": dict(sorted(counts.items())),
        "counts_by_primary_family": dict(sorted(primary.items())),
        "by_episode": by_episode,
    }


def build_timeframe_worker_evidence(
    frames: Mapping[str, pd.DataFrame],
    decision_times: Iterable[Any],
    sequence_evidence_by_episode: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    max_decisions: int = 48,
) -> dict[str, Any]:
    """Summarize the existing logical workers by timeframe for the backtest.

    This is a backtest-side black-box view only.  D1/H4/H1/M15/M5 are read
    from the existing MTF navigator, while M1 is read from the real sequential
    evidence already attached to episodes.  No worker authorizes entries.
    """

    all_decisions = list(decision_times)
    decisions = all_decisions[:max(0, max_decisions)]
    navigator = MTFNavigator({tf: frame for tf, frame in frames.items() if tf != "M1"})
    layer_counts: dict[str, Counter[str]] = {tf: Counter() for tf in ("D1", "H4", "H1", "M15", "M5")}
    nav_status = Counter()
    samples: list[dict[str, Any]] = []
    for decision_time in decisions:
        state = navigator.navigate(decision_time, exec_tf="M5")
        nav_status[state.status] += 1
        state_dict = state.to_dict()
        for tf in layer_counts:
            payload = state_dict.get("layers", {}).get(tf)
            if payload:
                layer_counts[tf]["available"] += 1
                if payload.get("answers"):
                    layer_counts[tf]["answered"] += 1
            else:
                layer_counts[tf]["missing"] += 1
        if len(samples) < 5:
            samples.append(
                {
                    "decision_time": _iso(decision_time),
                    "navigation_status": state.status,
                    "layers_present": sorted(state_dict.get("layers", {})),
                    "path_steps": state_dict.get("path", {}).get("steps", []),
                    "policy": "WORKER_EVIDENCE_NOT_ENTRY_SIGNAL",
                }
            )

    m1_evidence = sequence_evidence_by_episode or {}
    m1_counts = Counter(str(row.get("sequence_status", "MISSING")) for row in m1_evidence.values())
    return {
        "artifact_kind": "SIXTF_TIMEFRAME_WORKER_EVIDENCE_V1",
        "worker_model": {
            "D1": "MTFNavigator context worker",
            "H4": "MTFNavigator location worker",
            "H1": "MTFNavigator structure/sequence-depth worker",
            "M15": "MTFNavigator refinement worker",
            "M5": "MTFNavigator confirmation worker",
            "M1": "sequential_events execution/evidence worker",
            "COORDINATOR": "backtest forensic runner; diagnostic only",
        },
        "decision_count": len(all_decisions),
        "sampled_decision_count": len(decisions),
        "sample_policy": f"FIRST_{max_decisions}_DECISIONS_FOR_MTF_WORKER_BLACKBOX",
        "navigation_status_counts": dict(sorted(nav_status.items())),
        "layer_counts": {tf: dict(sorted(counts.items())) for tf, counts in layer_counts.items()},
        "m1_sequence_status_counts": dict(sorted(m1_counts.items())),
        "samples": samples,
        "policy": {
            "can_trade": False,
            "entry_authorized": False,
            "orders_sent": False,
            "mt5_connected": False,
        },
    }


def write_blackbox_jsonl(
    *,
    path: Path,
    trades: Iterable[Mapping[str, Any]],
    audit_rows: Iterable[Mapping[str, Any]],
    ai_rows: Iterable[Mapping[str, Any]],
    protocol_by_episode: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    audits = {row.get("episode_id"): row for row in audit_rows}
    ai = {
        row.get("features", {}).get("episode_id"): row
        for row in ai_rows
    }
    protocols = protocol_by_episode or {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for trade in trades:
            episode_id = trade.get("episode_id")
            record = {
                "kind": "SIXTF_FORENSIC_BLACKBOX_V1",
                "episode_id": episode_id,
                "decision_time": trade.get("decision_time"),
                "exit_status": trade.get("exit_status"),
                "net_R": trade.get("net_R"),
                "session": trade.get("session"),
                "forensic": audits.get(episode_id, {}),
                "entry_protocols": protocols.get(str(episode_id), {}),
                "ai_shadow": ai.get(episode_id, {}),
                "policy": {
                    "can_trade": False,
                    "orders_sent": False,
                    "mt5_connected": False,
                    "diagnostic_only": True,
                },
            }
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def failure_taxonomy(trades: Iterable[Mapping[str, Any]], audit_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    audits = {row.get("episode_id"): row for row in audit_rows}
    counts: Counter[str] = Counter()
    for trade in trades:
        counts[classify_failure(trade, audits.get(trade.get("episode_id"), {}))] += 1
    return dict(sorted(counts.items()))


def build_ai_shadow_dataset(
    trades: Iterable[Mapping[str, Any]],
    audit_rows: Iterable[Mapping[str, Any]],
    protocol_by_episode: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    audits = {row.get("episode_id"): row for row in audit_rows}
    protocols = protocol_by_episode or {}
    rows: list[dict[str, Any]] = []
    leakage: list[str] = []
    for trade in trades:
        audit = audits.get(trade.get("episode_id"), {})
        protocol = protocols.get(str(trade.get("episode_id")), {})
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
            "entry_protocol_primary": protocol.get("primary_family", "NONE"),
            "entry_protocol_complete_count": len(protocol.get("complete_families", [])),
        }
        labels = {
            "exit_status": trade.get("exit_status"),
            "net_R": trade.get("net_R"),
            "economic_status": trade.get("economic_status"),
        }
        overlap = sorted(set(features) & LABEL_FIELDS)
        leakage.extend(overlap)
        has_protocol = bool(protocol.get("complete_families"))
        if audit.get("sequence_audit_status") == "BLOCKED":
            decision = "RECHAZAR_ANALISIS"
        elif audit.get("sequence_audit_status") == "REVIEW" or session == "OFF_SESSION" or not has_protocol:
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
    "build_sequence_evidence",
    "build_timeframe_worker_evidence",
    "build_ai_shadow_dataset",
    "classify_entry_protocols",
    "classify_entry_protocols_for_episodes",
    "classify_session",
    "failure_taxonomy",
    "session_windows",
    "summarize_by_session",
    "weekly_frequency",
    "write_blackbox_jsonl",
]
