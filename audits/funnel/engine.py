"""Deterministic Funnel Audit engine.

Consumes already-emitted stage records; it does not detect trading events.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from audits.contracts.gate import AuditResult, Finding, GateStatus

STAGES = (
    "VALID_BARS",
    "STRUCTURE",
    "BOS_CHOCH",
    "DISPLACEMENT",
    "FVG",
    "OB",
    "CONFLUENCE",
    "LINEAGE",
    "SETUP",
)


@dataclass(frozen=True)
class StageSummary:
    stage: str
    input_count: int
    accepted_count: int
    rejected_count: int

    @property
    def pass_rate(self) -> float:
        return self.accepted_count / self.input_count if self.input_count else 1.0


class FunnelAudit:
    """Build a funnel report from explicit stage records.

    Records require: stage, id, accepted, and optional rejection_reason.
    This class deliberately performs no strategy optimization or PnL logic.
    """

    def __init__(self, audit_id: str = "A7_FUNNEL") -> None:
        self.audit_id = audit_id

    def run(self, records: Iterable[dict]) -> tuple[AuditResult, tuple[StageSummary, ...]]:
        summaries: list[StageSummary] = []
        findings: list[Finding] = []
        seen: set[tuple[str, str]] = set()
        grouped: dict[str, list[dict]] = {stage: [] for stage in STAGES}
        for record in records:
            stage = str(record.get("stage", ""))
            rid = str(record.get("id", ""))
            key = (stage, rid)
            if key in seen:
                findings.append(Finding("DUPLICATE_EVENT", "CRITICAL", f"duplicate event: {key}", stage, rid))
                continue
            seen.add(key)
            grouped.setdefault(stage, []).append(record)
            if not record.get("accepted", True) and not record.get("rejection_reason"):
                findings.append(Finding("UNEXPLAINED_REJECTION", "CRITICAL", "rejected record has no reason", stage, rid))
        total_input = 0
        total_accepted = 0
        total_rejected = 0
        for stage in STAGES:
            items = grouped.get(stage, [])
            accepted = sum(1 for x in items if x.get("accepted", True))
            rejected = len(items) - accepted
            total_input += len(items)
            total_accepted += accepted
            total_rejected += rejected
            summaries.append(StageSummary(stage, len(items), accepted, rejected))
        status = GateStatus.FAIL if any(f.severity == "CRITICAL" for f in findings) else GateStatus.PASS
        result = AuditResult(
            self.audit_id,
            status,
            total_input,
            total_accepted,
            total_rejected,
            tuple(findings),
            {f"{s.stage.lower()}_pass_rate": s.pass_rate for s in summaries},
        )
        return result, tuple(summaries)
