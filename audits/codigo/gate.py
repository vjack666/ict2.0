"""Contratos de resultado y Gate para el subsistema de auditorías."""
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
        return self.accepted_count / self.input_count if self.input_count else 1.0


def gate_from_findings(
    audit_id: str,
    input_count: int,
    accepted_count: int,
    rejected_count: int,
    findings: Iterable[Finding],
    metrics: dict[str, float] | None = None,
) -> AuditResult:
    items = tuple(findings)
    critical = any(f.severity.upper() == "CRITICAL" for f in items)
    high = any(f.severity.upper() == "HIGH" for f in items)
    medium = any(f.severity.upper() == "MEDIUM" for f in items)
    status = GateStatus.FAIL if critical or high else GateStatus.WARN if medium else GateStatus.PASS
    return AuditResult(
        audit_id=audit_id,
        status=status,
        input_count=input_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        findings=items,
        metrics=metrics or {},
    )


def medianamente_bueno(result: AuditResult, min_score: float = 0.80) -> bool:
    """Define el umbral mínimo para permitir que Hermes continúe.

    Cualquier CRITICAL/HIGH bloquea. ``audit_score`` debe existir y alcanzar
    ``min_score``. La política nunca convierte WARNs en PASS silenciosamente.
    """
    severities = {f.severity.upper() for f in result.findings}
    score = float(result.metrics.get("audit_score", 0.0))
    return not ({"CRITICAL", "HIGH"} & severities) and score >= min_score
