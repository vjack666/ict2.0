"""Deterministic, point-in-time validation of the A7 funnel population.

The runner owns dataset/provenance and FULL/PREFIX materialisation.  This
module owns the contract of each funnel record and the aggregate result.  It
is deliberately fail-closed: a record which cannot be interpreted is a
finding, never an implicitly valid event.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Iterable, Mapping

from .gate import AuditResult, Finding, GateStatus


# RAW_BARS and VALID_BARS may be reported as runner-level counts, so their
# absence from an event projection is not itself a violation. An entirely
# empty audit input is still unverifiable and therefore fails closed.
STAGES = (
    "RAW_BARS", "VALID_BARS", "STRUCTURE", "BOS_CHOCH", "DISPLACEMENT",
    "FVG", "OB", "CONFLUENCE", "LINEAGE", "SEQUENCE", "MTF_NAVIGATION", "SETUP",
)
# Sequence emits these atomic substages in the real A7 runner. They are
# contract-valid projections even though the public StageSummary keeps the
# twelve canonical funnel buckets for backwards-compatible report shape.
EXTRA_STAGES = ("LIQUIDITY_POOL", "SWEEP", "RETEST")
KNOWN_STAGES = frozenset(STAGES + EXTRA_STAGES)

REJECTION_REASONS = {
    "INVALID_DATA", "DUPLICATE_EVENT", "TEMPORAL_VIOLATION",
    "MISSING_PARENT", "INVALID_PARENT", "CONTRACT_VIOLATION",
    "INVALID_GEOMETRY", "INVALID_DIRECTION", "UNEXPLAINED_REJECTION",
    "UNCONFIRMED_EVENT", "LEGACY_AMBIGUITY", "OUTSIDE_AUDIT_WINDOW",
    "NO_OB_CAUSAL", "INVALIDATED_IN_CONTEXT",
}

_TIME_FIELDS = ("observation_time", "candidate_time", "confirmation_time", "tradable_time")
# A LINEAGE row is an edge projection, not a second domain object; its own
# observation plus the parent's auditable time are the applicable timestamps.
_REQUIRED_TIME_FIELDS = {
    stage: ("observation_time",) if stage == "LINEAGE" else _TIME_FIELDS
    for stage in STAGES
}


def _as_time(value: Any) -> datetime | None:
    """Return a UTC-aware datetime, or ``None`` for an invalid value."""
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                from pandas import to_datetime
                parsed = to_datetime(value, utc=True, errors="coerce")
                if parsed is None or str(parsed) == "NaT":
                    return None
                dt = parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed
            except Exception:
                text = str(value).strip()
                if not text:
                    return None
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None


def _time_label(value: Any) -> str:
    dt = _as_time(value)
    return dt.isoformat() if dt is not None else repr(value)


def _canonical(value: Any) -> str:
    """Stable representation used to remove dependence on input order."""
    try:
        return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(value)


def _record_sort_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record.get("stage", "")),
        str(record.get("id", "")),
        _time_label(record.get("observation_time")),
        _canonical(record),
    )


@dataclass(frozen=True)
class StageSummary:
    stage: str
    input_count: int
    accepted_count: int
    rejected_count: int
    duplicate_count: int = 0
    orphan_count: int = 0
    temporal_violation_count: int = 0

    @property
    def pass_rate(self) -> float:
        return self.accepted_count / self.input_count if self.input_count else 1.0


def _finding(code: str, severity: str, message: str, stage: Any = "", record_id: Any = None) -> Finding:
    return Finding(code, severity, message, str(stage), None if record_id is None else str(record_id))


class FunnelAudit:
    def __init__(self, audit_id: str = "A7_FUNNEL") -> None:
        self.audit_id = audit_id

    def run(
        self,
        records: Iterable[dict],
        *,
        audit_window: tuple[Any, Any] | None = None,
        expected_stages: Iterable[str] | None = None,
        prefix_records: Iterable[dict] | None = None,
        prefix_time: Any | None = None,
    ) -> tuple[AuditResult, tuple[StageSummary, ...]]:
        """Audit records and return an aggregate result plus stage summaries.

        Accepted records require all four event times and a direction. A
        rejected record requires a canonical reason; optional times are still
        parsed and checked when supplied. ``expected_stages`` lets a caller
        provide a declared stage manifest: a missing declared stage is then a
        failure, instead of being silently treated as verified.

        ``prefix_records``/``prefix_time`` provide a pure FULL/PREFIX check at
        atomic-event level for callers that materialise both populations.
        """
        materialized = list(records)
        findings: list[Finding] = []
        if not materialized:
            findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "A7 population is empty; no contractual stage was verified", "A7"))
        valid_records: list[dict[str, Any]] = []
        for index, record in enumerate(materialized):
            if not isinstance(record, Mapping):
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"record {index} is not a mapping", "", str(index)))
                continue
            valid_records.append(dict(record))
        ordered = sorted(valid_records, key=_record_sort_key)

        grouped: dict[str, list[dict[str, Any]]] = {stage: [] for stage in KNOWN_STAGES}
        known_ids: set[str] = set()
        records_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        unique_keys: set[tuple[str, str]] = set()
        unique_records: list[dict[str, Any]] = []
        parent_edges: dict[str, str] = {}

        # First pass establishes the ID universe before validating parent links.
        for record in ordered:
            stage = str(record.get("stage", ""))
            rid = str(record.get("id", ""))
            if stage and rid:
                known_ids.add(rid)
                records_by_id[rid].append(record)

        window = None
        if audit_window is not None:
            try:
                bounds = tuple(audit_window)
            except TypeError:
                bounds = ()
            if len(bounds) != 2:
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "audit_window must contain exactly two bounds", "A7"))
            else:
                window = (_as_time(bounds[0]), _as_time(bounds[1]))
                if window[0] is None or window[1] is None or window[0] > window[1]:
                    findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "audit_window is invalid", "A7"))
                    window = None

        for record in ordered:
            stage = record.get("stage")
            stage_name = str(stage) if stage is not None else ""
            rid_value = record.get("id")
            rid = str(rid_value) if rid_value is not None else ""
            key = (stage_name, rid)

            if not stage_name or stage_name not in KNOWN_STAGES:
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"unknown or missing stage: {stage_name!r}", stage_name, rid))
            if not rid:
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "event has no logical id", stage_name, rid))
            duplicate_key = key in unique_keys
            if duplicate_key:
                findings.append(_finding("DUPLICATE_EVENT", "CRITICAL", f"duplicate event: {key}", stage_name, rid))
            else:
                unique_keys.add(key)
                unique_records.append(record)
            if stage_name in KNOWN_STAGES:
                grouped[stage_name].append(record)

            if rid and len(records_by_id.get(rid, [])) > 1:
                findings.append(_finding("DUPLICATE_EVENT", "CRITICAL", f"id duplicated across stages: {rid}", stage_name, rid))

            accepted_value = record.get("accepted", True)
            if "accepted" not in record:
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "event has no accepted/rejected status", stage_name, rid))
            if not isinstance(accepted_value, bool):
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "accepted must be boolean", stage_name, rid))
                accepted = False
            else:
                accepted = accepted_value

            parsed: dict[str, datetime | None] = {}
            for field in _TIME_FIELDS:
                raw = record.get(field)
                parsed[field] = _as_time(raw)
                if raw is not None and parsed[field] is None:
                    findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"{field} is not parseable: {raw!r}", stage_name, rid))

            if accepted:
                for field in _REQUIRED_TIME_FIELDS.get(stage_name, _TIME_FIELDS):
                    if record.get(field) is None:
                        findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"accepted event missing {field}", stage_name, rid))
                if record.get("direction") is None:
                    findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "accepted event missing direction", stage_name, rid))
                if record.get("rejection_reason") is not None:
                    findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "accepted event cannot carry rejection_reason", stage_name, rid))
            else:
                reason = record.get("rejection_reason")
                if not isinstance(reason, str) or not reason:
                    findings.append(_finding("UNEXPLAINED_REJECTION", "CRITICAL", "rejected record has no reason", stage_name, rid))
                elif reason not in REJECTION_REASONS:
                    findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"rejection_reason outside canonical set: {reason}", stage_name, rid))

            direction = record.get("direction")
            if direction is not None and (isinstance(direction, bool) or direction not in (-1, 0, 1)):
                findings.append(_finding("INVALID_DIRECTION", "HIGH", f"invalid direction: {direction!r}", stage_name, rid))

            if accepted and all(parsed[field] is not None for field in _TIME_FIELDS):
                causal_pairs = (
                    ("candidate_time", parsed["candidate_time"], "confirmation_time", parsed["confirmation_time"]),
                    ("confirmation_time", parsed["confirmation_time"], "tradable_time", parsed["tradable_time"]),
                    ("tradable_time", parsed["tradable_time"], "observation_time", parsed["observation_time"]),
                )
                for left_name, left, right_name, right in causal_pairs:
                    if left > right:  # type: ignore[operator]
                        findings.append(_finding("TEMPORAL_VIOLATION", "CRITICAL", f"{left_name} > {right_name}: {_time_label(left)} > {_time_label(right)}", stage_name, rid))

            if window is not None and parsed["observation_time"] is not None:
                if parsed["observation_time"] < window[0] or parsed["observation_time"] > window[1]:  # type: ignore[operator]
                    findings.append(_finding("OUTSIDE_AUDIT_WINDOW", "MEDIUM", f"observation_time outside audit window: {_time_label(parsed['observation_time'])}", stage_name, rid))

            requires_parent = record.get("requires_parent", False)
            if not isinstance(requires_parent, bool):
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "requires_parent must be boolean", stage_name, rid))
                requires_parent = bool(requires_parent)
            parent_id = record.get("parent_id")
            parent = str(parent_id) if parent_id is not None and str(parent_id) else None
            explicit_parent_time = record.get("parent_time")
            parent_time = _as_time(explicit_parent_time)
            if explicit_parent_time is not None and parent_time is None:
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"parent_time is not parseable: {explicit_parent_time!r}", stage_name, rid))

            if requires_parent:
                if parent is None:
                    findings.append(_finding("MISSING_PARENT", "HIGH", "accepted event requires parent_id", stage_name, rid))
                elif parent == rid:
                    parent_edges[rid] = parent
                    findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"lineage cycle: parent_id == id ({rid})", stage_name, rid))
                else:
                    parent_edges[rid] = parent
                    if parent not in known_ids:
                        findings.append(_finding("MISSING_PARENT", "HIGH", f"parent {parent} does not exist in run (orphan)", stage_name, rid))
                    elif len(records_by_id[parent]) != 1:
                        findings.append(_finding("INVALID_PARENT", "HIGH", f"parent {parent} is not unique", stage_name, rid))
                    else:
                        parent_record = records_by_id[parent][0]
                        if parent_record.get("accepted", True) is not True:
                            findings.append(_finding("INVALID_PARENT", "HIGH", f"parent {parent} is rejected", stage_name, rid))
                        if record.get("lineage_valid") is not True:
                            findings.append(_finding("INVALID_PARENT", "HIGH", f"accepted event has invalid lineage: {key}", stage_name, rid))
                        if parent_time is None:
                            parent_time = _as_time(parent_record.get("observation_time"))
                            if parent_time is None:
                                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"parent {parent} has no auditable parent_time", stage_name, rid))
            elif parent is not None or explicit_parent_time is not None or record.get("lineage_valid") is not None:
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "lineage fields supplied for event that does not require a parent", stage_name, rid))

            if parent_time is not None and accepted:
                child_time = parsed["candidate_time"] or parsed["observation_time"]
                if child_time is not None and parent_time > child_time:
                    findings.append(_finding("TEMPORAL_VIOLATION", "CRITICAL", f"parent_time > candidate/observation_time: {_time_label(parent_time)} > {_time_label(child_time)}", stage_name, rid))

        # Detect every multi-node lineage cycle independently of input order.
        for start in sorted(parent_edges):
            path: list[str] = []
            seen_at: dict[str, int] = {}
            node: str | None = start
            while node is not None and node in parent_edges:
                if node in seen_at:
                    cycle = path[seen_at[node]:]
                    cycle_key = ",".join(sorted(cycle))
                    message = f"lineage cycle detected: {cycle_key}"
                    if not any(f.code == "CONTRACT_VIOLATION" and f.message == message for f in findings):
                        for member in sorted(set(cycle)):
                            findings.append(_finding("CONTRACT_VIOLATION", "HIGH", message, "LINEAGE", member))
                    break
                seen_at[node] = len(path)
                path.append(node)
                node = parent_edges.get(node)

        expected = set(expected_stages or ())
        for stage in sorted(expected - KNOWN_STAGES):
            findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"unknown expected stage: {stage}", "A7"))
        observed_stages = {stage for stage, items in grouped.items() if items}
        for stage in sorted(expected - observed_stages):
            findings.append(_finding("CONTRACT_VIOLATION", "HIGH", f"contractual stage was not verified: {stage}", stage))

        if prefix_records is not None:
            if prefix_time is None:
                findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "prefix_time is required with prefix_records", "PREFIX"))
            else:
                cutoff = _as_time(prefix_time)
                if cutoff is None:
                    findings.append(_finding("CONTRACT_VIOLATION", "HIGH", "prefix_time is not parseable", "PREFIX"))
                else:
                    full_events = self._atomic_events(materialized, cutoff)
                    prefix_events = self._atomic_events(list(prefix_records), None)
                    missing = sorted(full_events - prefix_events)
                    if missing:
                        findings.append(_finding("TEMPORAL_VIOLATION", "CRITICAL", f"FULL/PREFIX missing atomic events: {missing[:5]} (total={len(missing)})", "PREFIX"))

        summaries: list[StageSummary] = []
        for stage in STAGES:
            items = grouped[stage]
            unique_items: list[dict[str, Any]] = []
            seen_stage: set[tuple[str, str]] = set()
            for item in items:
                item_key = (stage, str(item.get("id", "")))
                if item_key not in seen_stage:
                    seen_stage.add(item_key)
                    unique_items.append(item)
            accepted_count = sum(1 for item in unique_items if item.get("accepted", True) is True)
            rejected_count = len(items) - accepted_count
            duplicate_count = sum(1 for f in findings if f.code == "DUPLICATE_EVENT" and f.stage == stage)
            orphan_count = sum(1 for f in findings if f.code == "MISSING_PARENT" and f.stage == stage)
            temporal_count = sum(1 for f in findings if f.code == "TEMPORAL_VIOLATION" and f.stage == stage)
            summaries.append(StageSummary(stage, len(items), accepted_count, rejected_count, duplicate_count, orphan_count, temporal_count))

        findings.sort(key=lambda f: (f.code, f.severity, f.stage, str(f.record_id), f.message))
        critical = sum(1 for f in findings if f.severity.upper() == "CRITICAL")
        high = sum(1 for f in findings if f.severity.upper() == "HIGH")
        medium = sum(1 for f in findings if f.severity.upper() == "MEDIUM")
        stage_rates = [summary.pass_rate for summary in summaries if summary.input_count]
        accepted_unique = sum(1 for record in unique_records if record.get("accepted", True) is True)
        rejected_unique = len(unique_records) - accepted_unique
        directions = Counter(str(record.get("direction")) for record in unique_records if record.get("direction") is not None)
        timeframes = Counter(str(record.get("timeframe")) for record in unique_records if record.get("timeframe") is not None)
        reasons = Counter(str(record.get("rejection_reason")) for record in unique_records if record.get("accepted", True) is False and record.get("rejection_reason"))
        extra_stages = Counter(str(record.get("stage")) for record in unique_records if str(record.get("stage")) in EXTRA_STAGES)
        metrics: dict[str, Any] = {
            "audit_score": sum(stage_rates) / len(stage_rates) if stage_rates else (0.0 if materialized else 1.0),
            "n_critical": critical, "n_high": high, "n_medium": medium,
            "unique_event_count": len(unique_records),
            "duplicate_event_count": sum(1 for f in findings if f.code == "DUPLICATE_EVENT"),
            "verified_stage_count": sum(1 for summary in summaries if summary.input_count),
            "direction_counts": dict(sorted(directions.items())),
            "timeframe_counts": dict(sorted(timeframes.items())),
            "rejection_reason_counts": dict(sorted(reasons.items())),
            "extra_stage_counts": dict(sorted(extra_stages.items())),
            "deterministic": True,
            **{f"{summary.stage.lower()}_pass_rate": summary.pass_rate for summary in summaries},
        }
        status = GateStatus.FAIL if critical or high else GateStatus.WARN if medium else GateStatus.PASS
        result = AuditResult(
            self.audit_id, status, len(materialized), accepted_unique, rejected_unique,
            tuple(findings), metrics,  # type: ignore[arg-type]
        )
        return result, tuple(summaries)

    @staticmethod
    def _atomic_events(records: Iterable[dict], cutoff: datetime | None) -> set[tuple[str, str]]:
        events: set[tuple[str, str]] = set()
        for record in records:
            if not isinstance(record, Mapping):
                continue
            observation = _as_time(record.get("observation_time"))
            if cutoff is None or (observation is not None and observation <= cutoff):
                events.add((str(record.get("stage", "")), str(record.get("id", ""))))
        return events


def aggregate_a7_status(
    result: AuditResult,
    *,
    provenance_ok: bool = True,
    prefix_invariant: bool = True,
    idempotent: bool = True,
) -> GateStatus:
    """Aggregate FunnelAudit with external A7 gates without hiding failures."""
    if result.status is GateStatus.FAIL or not provenance_ok or not prefix_invariant or not idempotent:
        return GateStatus.FAIL
    return GateStatus.WARN if result.status is GateStatus.WARN else GateStatus.PASS
