"""Funnel Audit determinista: cuenta y explica la población por etapa."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .gate import AuditResult, Finding, GateStatus

STAGES = (
    "VALID_BARS", "STRUCTURE", "BOS_CHOCH", "DISPLACEMENT",
    "FVG", "OB", "CONFLUENCE", "LINEAGE", "SETUP"
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
    def __init__(self, audit_id: str = "A7_FUNNEL") -> None:
        self.audit_id = audit_id

    def run(self, records: Iterable[dict]) -> tuple[AuditResult, tuple[StageSummary, ...]]:
        findings: list[Finding] = []
        grouped: dict[str, list[dict]] = {stage: [] for stage in STAGES}
        seen: set[tuple[str, str]] = set()
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

        summaries: list[StageSummary] = []
        total_input = total_accepted = total_rejected = 0
        for stage in STAGES:
            items = grouped.get(stage, [])
            accepted = sum(1 for item in items if item.get("accepted", True))
            rejected = len(items) - accepted
            summaries.append(StageSummary(stage, len(items), accepted, rejected))
            total_input += len(items)
            total_accepted += accepted
            total_rejected += rejected

        stage_rates = [s.pass_rate for s in summaries if s.input_count]
        audit_score = sum(stage_rates) / len(stage_rates) if stage_rates else 1.0
        status = GateStatus.FAIL if findings else GateStatus.PASS
        result = AuditResult(
            self.audit_id,
            status,
            total_input,
            total_accepted,
            total_rejected,
            tuple(findings),
            {"audit_score": audit_score, **{f"{s.stage.lower()}_pass_rate": s.pass_rate for s in summaries}},
        )
        return result, tuple(summaries)
