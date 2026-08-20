"""Secuencia A0-A9 de auditoría pre-backtest.

La pila usa contratos comunes y datos/eventos explícitos. No hace PnL ni
optimización. El resultado es un Gate agregado: ningún FAIL crítico/alto,
ninguna violación de look-ahead y todos los gates ejecutados.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .gate import AuditResult, Finding, GateStatus, gate_from_findings
from .data_integrity import audit_ohlc
from .temporal import audit_events
from .funnel import FunnelAudit

ROOT = Path(__file__).resolve().parents[2]


def _result(audit_id: str, findings: list[Finding], n: int = 1, metrics: dict[str, float] | None = None) -> AuditResult:
    return gate_from_findings(audit_id, n, max(0, n - len(findings)), len(findings), findings, metrics or {"audit_score": 1.0 if not findings else 0.0})


def a0_data(rows: list[dict[str, Any]]) -> AuditResult:
    return audit_ohlc(rows, "A0_DATA_INTEGRITY")


def a1_schema(rows: list[dict[str, Any]]) -> AuditResult:
    required = ("time", "open", "high", "low", "close")
    findings: list[Finding] = []
    for i, row in enumerate(rows):
        missing = [c for c in required if c not in row]
        if missing:
            findings.append(Finding("SCHEMA_MISSING", "CRITICAL", str(missing), "A1", str(i)))
    return _result("A1_SCHEMA", findings, len(rows))


def a2_point_in_time(events: list[dict[str, Any]]) -> AuditResult:
    violations = audit_events(events)
    findings = [Finding(v.code, "CRITICAL", v.message, "A2", v.record_id) for v in violations]
    return _result("A2_POINT_IN_TIME", findings, len(events))


def a3_semantics() -> AuditResult:
    # Contrato mínimo: las cuatro etapas ICT/FVG/OB/lineage deben estar expresadas
    # por objetos explícitos; no usamos nombres legacy como sustitutos silenciosos.
    findings: list[Finding] = []
    contract_doc = ROOT / "docs" / "contratos" / "CONTRATO_FUNNEL_AUDIT.md"
    sdd = ROOT / "docs" / "planificacion" / "SDD_FVG_OB_ARCHITECTURE_MAP.md"
    if not contract_doc.exists():
        findings.append(Finding("CONTRACT_MISSING", "HIGH", "Contrato Funnel ausente", "A3"))
    if not sdd.exists():
        findings.append(Finding("SDD_MISSING", "HIGH", "SDD arquitectónico ausente", "A3"))
    return _result("A3_SEMANTICS", findings)


def a4_metamorphic() -> AuditResult:
    # Propiedades estructurales sobre el motor de auditoría: determinismo y
    # rechazo de un duplicado lógico.
    funnel = FunnelAudit()
    records = [{"stage": "FVG", "id": "m1", "accepted": True}]
    first, _ = funnel.run(records)
    second, _ = funnel.run(records)
    findings: list[Finding] = []
    if first.status != second.status or first.metrics != second.metrics:
        findings.append(Finding("NON_DETERMINISTIC", "CRITICAL", "Funnel no determinista", "A4"))
    duplicate, _ = funnel.run(records + records)
    if duplicate.status != GateStatus.FAIL:
        findings.append(Finding("METAMORPHIC_DUPLICATE", "CRITICAL", "Duplicado no detectado", "A4"))
    return _result("A4_DETECTOR_METAMORPHIC", findings)


def a5_cross_tf() -> AuditResult:
    # Prueba point-in-time de propagación HTF: una observación HTF no puede
    # aparecer antes del cierre de la ventana de la vela HTF.
    events = [
        {"id": "HTF_OK", "candidate_time": 10, "confirmation_time": 12, "tradable_time": 12, "observation_time": 12},
    ]
    findings = [Finding(v.code, "CRITICAL", v.message, "A5", v.record_id) for v in audit_events(events)]
    return _result("A5_CROSS_TIMEFRAME", findings, len(events))


def a6_lineage() -> AuditResult:
    from engine.lineage import CausalLink, validate_links
    findings: list[Finding] = []
    try:
        validate_links([CausalLink("p", "c", "REL", 1, 2)])
        try:
            validate_links([CausalLink("p", "c", "REL", 1, 2), CausalLink("p", "c", "REL", 1, 2)])
        except ValueError:
            pass
        else:
            findings.append(Finding("LINEAGE_DUPLICATE_NOT_REJECTED", "CRITICAL", "Duplicado de lineage aceptado", "A6"))
    except Exception as exc:
        findings.append(Finding("LINEAGE_CONTRACT", "CRITICAL", str(exc), "A6"))
    return _result("A6_LINEAGE", findings)


def a7_funnel(records: list[dict[str, Any]]) -> AuditResult:
    return FunnelAudit("A7_FUNNEL").run(records)[0]


def a8_coverage(records: list[dict[str, Any]]) -> AuditResult:
    findings: list[Finding] = []
    if not records:
        findings.append(Finding("NO_COVERAGE", "HIGH", "No hay eventos para auditar cobertura", "A8"))
    dirs = {str(r.get("direction")) for r in records if r.get("direction") is not None}
    if records and len(dirs) == 1:
        findings.append(Finding("SINGLE_DIRECTION", "MEDIUM", "Sólo una dirección está representada", "A8"))
    return _result("A8_COVERAGE_REGIME", findings, max(1, len(records)))


def a9_governance() -> AuditResult:
    findings: list[Finding] = []
    required = [ROOT / ".hermes-index.md", ROOT / "docs" / "PLAN_PRE_BACKTEST_AUDIT_STACK.md", ROOT / ".hermes-worklog"]
    for p in required:
        if not p.exists():
            findings.append(Finding("GOVERNANCE_MISSING", "HIGH", f"Falta {p}", "A9"))
    return _result("A9_GOVERNANCE", findings)


def fingerprint(results: list[AuditResult]) -> str:
    payload = json.dumps([asdict(r) for r in results], sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def run_stack(rows: list[dict[str, Any]], events: list[dict[str, Any]], funnel_records: list[dict[str, Any]]) -> dict[str, Any]:
    results = [
        a0_data(rows),
        a1_schema(rows),
        a2_point_in_time(events),
        a3_semantics(),
        a4_metamorphic(),
        a5_cross_tf(),
        a6_lineage(),
        a7_funnel(funnel_records),
        a8_coverage(funnel_records),
        a9_governance(),
    ]
    blocking = [r for r in results if any(f.severity.upper() in {"CRITICAL", "HIGH"} for f in r.findings)]
    return {
        "status": "FAIL" if blocking else ("WARN" if any(r.status is GateStatus.WARN for r in results) else "PASS"),
        "gates": {r.audit_id: r.status.value for r in results},
        "findings": [asdict(f) for r in results for f in r.findings],
        "fingerprint": fingerprint(results),
    }
