"""Version and authority boundary between daily runtime and laboratory.

The registry is deliberately conservative: the daily engine is read-only and
research artifacts cannot replace it. Promotion is a governance operation,
not a side effect of running an experiment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


REGISTRY_PATH = Path(__file__).with_name("engine_registry.json")


class EngineRegistryError(ValueError):
    """Raised when the engine authority contract is invalid."""


def load_engine_registry(path: str | Path = REGISTRY_PATH) -> dict[str, Any]:
    """Load and validate the production/laboratory registry."""

    registry_path = Path(path)
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EngineRegistryError(f"No se pudo cargar el registro de motores: {registry_path}") from exc
    validate_engine_registry(data)
    return data


def validate_engine_registry(registry: Mapping[str, Any]) -> None:
    """Fail closed if the authority or read-only policy is incomplete."""

    if registry.get("schema_version") != "1.0":
        raise EngineRegistryError("schema_version del registro no soportado")

    active = registry.get("active_engine")
    research = registry.get("research_engine")
    policy = registry.get("promotion_policy")
    if not isinstance(active, Mapping) or not isinstance(research, Mapping) or not isinstance(policy, Mapping):
        raise EngineRegistryError("El registro requiere active_engine, research_engine y promotion_policy")

    required_active = {
        "id", "status", "mode", "entrypoint", "profile_id", "policy",
        "deployment_state", "promotion_locked",
    }
    missing = sorted(required_active - set(active))
    if missing:
        raise EngineRegistryError(f"Faltan campos del motor activo: {', '.join(missing)}")

    if active["status"] != "ACTIVE":
        raise EngineRegistryError("El motor activo debe permanecer en estado ACTIVE")
    if active["mode"] != "DAILY_READ_ONLY":
        raise EngineRegistryError("El motor activo diario debe ser DAILY_READ_ONLY")
    if active["policy"] != "OBSERVE_ONLY_NO_ORDER":
        raise EngineRegistryError("La lectura diaria debe permanecer OBSERVE_ONLY_NO_ORDER")
    if active["promotion_locked"] is not True:
        raise EngineRegistryError("La promoción no puede quedar abierta durante esta misión")
    if research.get("may_replace_active") is not False:
        raise EngineRegistryError("El laboratorio no puede reemplazar directamente al motor activo")
    if policy.get("active_engine_must_remain_unchanged_during_research") is not True:
        raise EngineRegistryError("La política debe congelar el motor activo durante la investigación")


def assert_daily_engine_safe(registry: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Validate the registry and return the active engine metadata.

    Daily entrypoints call this before reading data. An invalid registry stops
    the run instead of silently falling back to an ungoverned engine.
    """

    if registry is None:
        registry = load_engine_registry()
    validate_engine_registry(registry)
    return registry["active_engine"]


__all__ = [
    "EngineRegistryError",
    "REGISTRY_PATH",
    "assert_daily_engine_safe",
    "load_engine_registry",
    "validate_engine_registry",
]
