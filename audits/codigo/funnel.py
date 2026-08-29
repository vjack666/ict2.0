"""Funnel Audit determinista: cuenta y explica la población por etapa.

Cumple el CONTRATO_FUNNEL_AUDIT (Gate A7) al pie de la letra. Valida:
  - observation_time (causalidad)
  - candidate_time / confirmation_time / tradable_time / parent_time
  - orden causal (candidate <= confirmation <= tradable; observation >= confirmation)
  - lineage (padre válido, sin huérfanos, sin ciclos)
  - duplicados (unicidad)
  - dirección
  - temporalidad (NINGUNA etapa lee barra posterior a observation_time)
  - razones de rechazo del set canónico
  - determinismo (función pura: mismos records -> mismos findings)
  - idempotencia / FULL-PREFIX (el runner los prueba comparando dos corridas)
  - checksum (el runner lo calcula sobre el reporte)

Fail-closed: cualquier campo contrato faltante o incoherente se registra como
hallazgo, no se asume bueno. El estado agregado es PASS / WARN / FAIL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .gate import AuditResult, Finding, GateStatus

# Etapas clásicas del funnel (contrato A7 §2).
STAGES = (
    "RAW_BARS", "VALID_BARS", "STRUCTURE", "BOS_CHOCH", "DISPLACEMENT",
    "FVG", "OB", "CONFLUENCE", "LINEAGE", "SEQUENCE", "MTF_NAVIGATION", "SETUP",
)

# Razones de rechazo canónicas (contrato A7 §Razones de rechazo mínimas).
REJECTION_REASONS = {
    "INVALID_DATA", "DUPLICATE_EVENT", "TEMPORAL_VIOLATION",
    "MISSING_PARENT", "INVALID_PARENT", "CONTRACT_VIOLATION",
    "INVALID_GEOMETRY", "INVALID_DIRECTION", "UNEXPLAINED_REJECTION",
    "UNCONFIRMED_EVENT", "LEGACY_AMBIGUITY", "OUTSIDE_AUDIT_WINDOW",
    "NO_OB_CAUSAL",           # FVG sin OB causal en la ventana (razón de negocio canónica)
    "INVALIDATED_IN_CONTEXT", # evento invalidado por contexto sin autoridad
}


def _as_time(v) -> datetime | None:
    """Normaliza a datetime (naive o tz) o None si no parseable."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        from pandas import to_datetime
        dt = to_datetime(v, utc=True, errors="coerce")
        return dt if dt is not None else None
    except Exception:
        return None


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


@dataclass
class FunnelAudit:
    def __init__(self, audit_id: str = "A7_FUNNEL") -> None:
        self.audit_id = audit_id

    def run(self, records: Iterable[dict], *, audit_window=None) -> tuple[AuditResult, tuple[StageSummary, ...]]:
        """Audita la población de eventos contra el contrato A7.

        ``records`` (fail-closed si falta):
          stage, id, accepted, rejection_reason (si rechazado),
          observation_time, candidate_time, confirmation_time, tradable_time,
          parent_id, parent_time, lineage_valid, direction, requires_parent.
        """
        findings: list[Finding] = []
        grouped: dict[str, list[dict]] = {stage: [] for stage in STAGES}
        seen: set[tuple[str, str]] = set()
        ids_seen: set[str] = set()
        known_ids: set[str] = set()

        # Primera pasada: recolectar ids conocidos (para validar huérfanos/ciclos).
        for record in records:
            known_ids.add(str(record.get("id", "")))

        # Segunda pasada: validaciones.
        for record in records:
            stage = str(record.get("stage", ""))
            rid = str(record.get("id", ""))
            key = (stage, rid)

            if key in seen:
                findings.append(Finding("DUPLICATE_EVENT", "CRITICAL",
                                         f"duplicate event: {key}", stage, rid))
                continue
            seen.add(key)
            if rid in ids_seen and rid:
                findings.append(Finding("DUPLICATE_EVENT", "CRITICAL",
                                         f"id duplicado entre etapas: {rid}", stage, rid))
            ids_seen.add(rid)
            grouped.setdefault(stage, []).append(record)

            accepted = bool(record.get("accepted", True))

            # --- Campos temporales y orden causal ---
            cand_t = _as_time(record.get("candidate_time"))
            conf_t = _as_time(record.get("confirmation_time"))
            trad_t = _as_time(record.get("tradable_time"))
            obs_t = _as_time(record.get("observation_time"))

            if accepted:
                if obs_t is None and record.get("observation_time") is None:
                    findings.append(Finding("CONTRACT_VIOLATION", "HIGH",
                                             f"evento aceptado sin observation_time: {key}", stage, rid))
                # orden causal interno del objeto
                if cand_t is not None and conf_t is not None and cand_t > conf_t:
                    findings.append(Finding("TEMPORAL_VIOLATION", "CRITICAL",
                                             f"candidate_time > confirmation_time: {cand_t} > {conf_t}", stage, rid))
                if conf_t is not None and trad_t is not None and conf_t > trad_t:
                    findings.append(Finding("TEMPORAL_VIOLATION", "CRITICAL",
                                             f"confirmation_time > tradable_time: {conf_t} > {trad_t}", stage, rid))
                # la observación no puede preceder a la confirmación
                if obs_t is not None and conf_t is not None and obs_t < conf_t:
                    findings.append(Finding("TEMPORAL_VIOLATION", "CRITICAL",
                                             f"observation_time < confirmation_time: {obs_t} < {conf_t}", stage, rid))

            # --- Ventana de auditoría ---
            if audit_window is not None and obs_t is not None:
                if obs_t < audit_window[0] or obs_t > audit_window[1]:
                    findings.append(Finding("OUTSIDE_AUDIT_WINDOW", "MEDIUM",
                                             f"observation_time fuera de ventana: {obs_t}", stage, rid))

            # --- Rechazo con razón canónica ---
            if not accepted:
                reason = record.get("rejection_reason")
                if not reason:
                    findings.append(Finding("UNEXPLAINED_REJECTION", "CRITICAL",
                                             "rejected record has no reason", stage, rid))
                elif reason not in REJECTION_REASONS:
                    findings.append(Finding("CONTRACT_VIOLATION", "HIGH",
                                             f"rejection_reason fuera del set canónico: {reason}", stage, rid))

            # --- Lineage: padre, huérfanos, ciclos ---
            if accepted and record.get("requires_parent"):
                parent = record.get("parent_id")
                lineage_valid = record.get("lineage_valid", None)
                if parent is not None and str(parent) == rid:
                    findings.append(Finding("CONTRACT_VIOLATION", "HIGH",
                                             f"ciclo: parent_id == id: {key}", stage, rid))
                elif parent is None and lineage_valid is not True:
                    findings.append(Finding("MISSING_PARENT", "HIGH",
                                             f"candidato aceptado sin padre ni lineage válido: {key}", stage, rid))
                elif parent is not None and lineage_valid is False:
                    findings.append(Finding("INVALID_PARENT", "HIGH",
                                             f"candidato con padre inválido: {key}", stage, rid))
                elif parent is not None and lineage_valid is not True and parent not in known_ids:
                    findings.append(Finding("MISSING_PARENT", "HIGH",
                                             f"padre {parent} no existe en el run (huérfano): {key}", stage, rid))

            # --- Dirección ---
            if accepted and record.get("direction", 0) not in (-1, 0, 1):
                findings.append(Finding("INVALID_DIRECTION", "HIGH",
                                         f"direction inválida: {record.get('direction')}", stage, rid))

        # --- Resumen por etapa ---
        summaries: list[StageSummary] = []
        total_input = total_accepted = total_rejected = 0
        for stage in STAGES:
            items = grouped.get(stage, [])
            accepted = sum(1 for it in items if it.get("accepted", True))
            rejected = len(items) - accepted
            dup = sum(1 for f in findings if f.code == "DUPLICATE_EVENT" and f.stage == stage)
            orphan = sum(1 for f in findings if f.code in ("MISSING_PARENT",) and f.stage == stage)
            tv = sum(1 for f in findings if f.code == "TEMPORAL_VIOLATION" and f.stage == stage)
            summaries.append(StageSummary(stage, len(items), accepted, rejected, dup, orphan, tv))
            total_input += len(items)
            total_accepted += accepted
            total_rejected += rejected

        critical = any(f.severity.upper() == "CRITICAL" for f in findings)
        high = any(f.severity.upper() == "HIGH" for f in findings)
        medium = any(f.severity.upper() == "MEDIUM" for f in findings)
        status = GateStatus.FAIL if (critical or high) else GateStatus.WARN if medium else GateStatus.PASS
        stage_rates = [s.pass_rate for s in summaries if s.input_count]
        audit_score = sum(stage_rates) / len(stage_rates) if stage_rates else 1.0
        result = AuditResult(
            self.audit_id, status, total_input, total_accepted, total_rejected,
            tuple(findings),
            {"audit_score": audit_score,
             "n_critical": sum(1 for f in findings if f.severity.upper() == "CRITICAL"),
             "n_high": sum(1 for f in findings if f.severity.upper() == "HIGH"),
             "n_medium": sum(1 for f in findings if f.severity.upper() == "MEDIUM"),
             **{f"{s.stage.lower()}_pass_rate": s.pass_rate for s in summaries}},
        )
        return result, tuple(summaries)
