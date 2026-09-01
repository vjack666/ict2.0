"""Intent-based routing from a user request to the department registry.

This module only plans a route. It never starts an experiment, changes a dataset,
opens a provider session, or promotes a model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import RouteDecision


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "governance" / "DEPARTMENT_REGISTRY.json"


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _has(text: str, *terms: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _department_name(registry: dict, department_id: str) -> str:
    for department in registry["departments"]:
        if department["id"] == department_id:
            return department["name"]
    raise ValueError(f"unknown department: {department_id}")


def route_request(objective: str) -> RouteDecision:
    """Classify a natural-language objective without performing the work.

    Specific safety-sensitive intents are evaluated before generic engineering
    terms so that, for example, a request to change a model's drift policy routes
    to AI plus independent assurance rather than directly to the daily motor.
    """
    if not objective or not objective.strip():
        raise ValueError("objective must not be empty")

    text = objective.casefold()
    registry = _registry()
    controls = {"context_discovery", "single_owner", "no_unapproved_promotion"}
    reviews: set[str] = set()

    if _has(text, "commit", "push", "release", "tag", "despliegue", "deploy"):
        department_id, role, kind, reason = (
            "D7", "Release Manager", "RELEASE", "la solicitud afecta entrega o historial Git"
        )
        agent_key = "conductor"
        reviews.update(("client_authority", "independent_verification"))
    elif _has(text, "riesgo", "leakage", "look-ahead", "pit", "gate", "auditor", "auditoría", "reproduc"):
        department_id, role, kind, reason = (
            "D5", "Independent Auditor", "REVIEW", "la solicitud contiene riesgo, gate o verificación independiente"
        )
        agent_key = "auditor"
        controls.add("independent_verification")
        reviews.add("client_authority_if_blocking")
    elif _has(text, "dataset", "datos", "manifest", "hash", "lineage", "procedencia"):
        department_id, role, kind, reason = (
            "D4", "Data Engineer", "INVESTIGATE", "la solicitud afecta datos, procedencia o lineage"
        )
        agent_key = "discoverer"
        controls.update(("independent_verification", "protected_data_check"))
        reviews.update(("CRO", "Compliance"))
    elif _has(text, "drift", "ood", "out of domain", "calibr", "abstain", "abstención", "modelo", "training", "entrenamiento", "ia"):
        department_id = "D3"
        role = "Model Evaluator" if _has(text, "drift", "ood", "out of domain", "calibr", "abstain", "abstención") else "ML Scientist"
        kind = "REVIEW" if role == "Model Evaluator" else "IMPLEMENT"
        reason = "la solicitud afecta la infraestructura IA y sus controles de seguridad"
        agent_key = "auditor" if role == "Model Evaluator" else "researcher"
        controls.add("independent_verification")
        reviews.update(("CRO", "Reproducibility Auditor"))
    elif _has(text, "experimento", "experiment", "hipótesis", "hipotesis", "backtest", "lab", "laboratorio", "investig"):
        department_id = "D6"
        role = "Research Engineer" if _has(text, "runner", "implement", "código", "codigo") else "Scientist"
        kind = "IMPLEMENT" if role == "Research Engineer" else "INVESTIGATE"
        reason = "la solicitud pertenece a investigación o laboratorio"
        agent_key = "implementer" if role == "Research Engineer" else "researcher"
        controls.update(("independent_verification", "pre_registered_protocol", "lab_boundary"))
        reviews.update(("Compliance", "Independent Auditor"))
    elif _has(text, "document", "docs", "bitácora", "bitacora", "orden", "limpieza", "carpeta", "roadmap", "plan"):
        department_id = "D1"
        role = "Repository Steward" if _has(text, "orden", "limpieza", "carpeta") else "Knowledge Manager"
        kind = "DOCUMENT"
        reason = "la solicitud afecta documentación, organización o memoria operativa"
        agent_key = "scout" if role == "Repository Steward" else "documenter"
        reviews.add("Hygiene Auditor")
    elif _has(text, "motor", "daily", "lectura", "bug", "refactor", "api", "engine", "código", "codigo"):
        department_id, role, kind, reason = (
            "D2", "Engineer", "IMPLEMENT", "la solicitud afecta el motor diario o una API técnica"
        )
        agent_key = "implementer"
        controls.add("architecture_guard")
        reviews.update(("QA", "Compliance"))
    else:
        department_id, role, kind, reason = (
            "D0", "COO", "PLAN", "la intención no es suficientemente específica y requiere planificación ejecutiva"
        )
        agent_key = "conductor"
        reviews.add("CEO_scope_check")

    return RouteDecision(
        department_id=department_id,
        department_name=_department_name(registry, department_id),
        assigned_role=role,
        agent_key=agent_key,
        task_kind=kind,
        reason=reason,
        required_controls=tuple(sorted(controls)),
        required_reviews=tuple(sorted(reviews)),
    )
