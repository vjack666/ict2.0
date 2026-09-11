"""Fail-closed Phase 2B publication gate for EURUSD mechanical signals.

The gate does not train, score, infer, or authorize. It validates a frozen
certificate from calibration, provenance, and edge workflows, so a diagnostic
candidate cannot become tradable merely because a field is present.
"""
from __future__ import annotations

from typing import Any, Mapping


REQUIRED_GATES = (
    "direction_rule", "confirmation", "calibration", "abstention_ood",
    "costs_fill", "causality", "provenance", "edge", "production_authorization",
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _blocked(code: str, detail: str, *, failed_gates: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "MECHANICAL_SIGNAL_PUBLICATION_GATE_V2B", "status": "BLOCKED", "code": code,
        "detail": detail, "failed_gates": failed_gates or [], "publication_authorized": False, "can_trade": False,
    }


def evaluate_publication_gate(candidate: Mapping[str, Any] | None, certificate: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a publishable contract only after every independent gate passes.

    The only directional rule maps the Phase 2A closed-candle contextual
    direction BULLISH->BUY and BEARISH->SELL. The certificate must freeze that
    exact rule. ``confirmed`` means the Phase 2A chain is complete at its
    decision time; it never includes the bot's final stochastic cross.
    """
    candidate, certificate = _mapping(candidate), _mapping(certificate)
    if candidate.get("status") != "CANDIDATE_SETUP":
        return {
            "schema_version": "MECHANICAL_SIGNAL_PUBLICATION_GATE_V2B", "status": "NO_SIGNAL",
            "code": "CANDIDATE_REQUIRED", "detail": "La publicación requiere CANDIDATE_SETUP del evaluador causal.",
            "publication_authorized": False, "can_trade": False,
        }
    direction = {"BULLISH": "BUY", "BEARISH": "SELL"}.get(candidate.get("context_direction"))
    if direction is None:
        return _blocked("DIRECTION_RULE_INVALID", "El candidato no contiene dirección contextual congelada.", failed_gates=["direction_rule"])
    failed = [gate for gate in REQUIRED_GATES if _mapping(certificate.get("gates")).get(gate) != "PASS"]
    if failed:
        return _blocked("PUBLICATION_GATES_BLOCKED", "Faltan gates independientes PASS; no se publica señal.", failed_gates=failed)
    if certificate.get("direction_rule") != "CANDIDATE_CONTEXT_DIRECTION_V1":
        return _blocked("DIRECTION_RULE_INVALID", "El certificado no congela la regla direccional requerida.", failed_gates=["direction_rule"])
    if certificate.get("confirmed_definition") != "PHASE2A_CHAIN_COMPLETE_CLOSED_M15_V1":
        return _blocked("CONFIRMATION_RULE_INVALID", "confirmed debe provenir de la cadena cerrada, no del estocástico.", failed_gates=["confirmation"])
    calibration = _mapping(certificate.get("calibration"))
    probability = calibration.get("probability")
    valid_calibration = (
        isinstance(probability, (int, float)) and not isinstance(probability, bool) and 0.0 <= probability <= 1.0
        and calibration.get("fit_partition") == "VALIDATION_ONLY"
        and calibration.get("oos_partition") == "HOLDOUT_NEVER_USED_FOR_FIT"
        and isinstance(calibration.get("brier"), (int, float))
        and isinstance(calibration.get("reliability_curve_hash"), str) and bool(calibration.get("reliability_curve_hash"))
    )
    if not valid_calibration:
        return _blocked("CALIBRATION_EVIDENCE_INVALID", "La probabilidad no trae evidencia válida de calibración/OOS.", failed_gates=["calibration"])
    if candidate.get("symbol") != "EURUSD" or not isinstance(candidate.get("decision_time"), str):
        return _blocked("CANDIDATE_IDENTITY_INVALID", "El candidato debe ser EURUSD y conservar decision_time.")
    return {
        "schema_version": "MECHANICAL_SIGNAL_PUBLICATION_GATE_V2B", "status": "VALIDATED_MECHANICAL_SIGNAL",
        "code": "ALL_PUBLICATION_GATES_PASS", "symbol": "EURUSD", "direction": direction,
        "probability": float(probability), "confirmed": True, "asof_time": candidate["decision_time"],
        "publication_authorized": True, "can_trade": False,
        "bot_rechecks_required": ["snapshot_freshness", "execution_enabled", "entry_session", "m15_stochastic_cross"],
    }


__all__ = ["REQUIRED_GATES", "evaluate_publication_gate"]
