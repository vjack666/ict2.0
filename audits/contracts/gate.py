"""Shared audit result and Gate contract types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class GateStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    stage: str
    record_id: str | None = None


@dataclass(frozen=True)
class AuditResult:
    audit_id: str
    status: GateStatus
    input_count: int
    accepted_count: int
    rejected_count: int
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.input_count == 0:
            return 1.0
        return self.accepted_count / self.input_count

    def with_findings(self, findings: Iterable[Finding]) -> "AuditResult":
        return AuditResult(
            audit_id=self.audit_id,
            status=self.status,
            input_count=self.input_count,
            accepted_count=self.accepted_count,
            rejected_count=self.rejected_count,
            findings=tuple(findings),
            metrics=self.metrics,
        )


def gate_from_findings(
    audit_id: str,
    input_count: int,
    accepted_count: int,
    rejected_count: int,
    findings: Iterable[Finding],
    metrics: dict[str, float] | None = None,
) -> AuditResult:
    items = tuple(findings)
    if any(f.severity.upper() == "CRITICAL" for f in items):
        status = GateStatus.FAIL
    elif any(f.severity.upper() in {"HIGH", "MEDIUM"} for f in items):
        status = GateStatus.WARN
    else:
        status = GateStatus.PASS
    return AuditResult(
        audit_id=audit_id,
        status=status,
        input_count=input_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        findings=items,
        metrics=metrics or {},
    )
