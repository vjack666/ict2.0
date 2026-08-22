"""Contrato read-only Hermes -> infraestructura de IA.

Este módulo no ejecuta experimentos, no modifica sus archivos y no resuelve
alias de manifests incompletos. Un resultado solo cruza la frontera cuando
cumple el contrato versionado y tiene ``verdict == PASS``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


CERTIFIED_MANIFEST_SCHEMA_VERSION = "1.0"
REJECTED_VERDICTS = frozenset({"FAIL", "BLOCKED", "INCONCLUSIVE", "MEASURED"})
REQUIRED_FIELDS = (
    "experiment_id",
    "verdict",
    "gate",
    "dataset_hash",
    "code_commit",
    "scope",
    "metrics",
    "artifact_paths",
    "produced_at",
    "certifier",
)
_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")


class CertifiedArtifactError(ValueError):
    """El manifest no es elegible para cruzar la frontera del laboratorio."""


@dataclass(frozen=True)
class CertifiedExperimentManifest:
    """Representación inmutable de un resultado certificado."""

    experiment_id: str
    verdict: str
    gate: str | Mapping[str, Any]
    dataset_hash: str
    code_commit: str
    scope: Mapping[str, Any]
    metrics: Mapping[str, Any]
    artifact_paths: tuple[str, ...]
    produced_at: str
    certifier: str
    schema_version: str = CERTIFIED_MANIFEST_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CertifiedExperimentManifest":
        """Valida un mapping sin normalizar campos alternativos ni escribir disco."""

        if not isinstance(payload, Mapping):
            raise CertifiedArtifactError("El manifest debe ser un objeto JSON")

        missing = [field for field in REQUIRED_FIELDS if field not in payload]
        if missing:
            raise CertifiedArtifactError(
                "Manifest incompleto; faltan: " + ", ".join(missing)
            )

        schema_version = payload.get("schema_version")
        if schema_version != CERTIFIED_MANIFEST_SCHEMA_VERSION:
            raise CertifiedArtifactError(
                f"schema_version no soportada: {schema_version!r}"
            )

        experiment_id = _non_empty_string(payload["experiment_id"], "experiment_id")
        verdict = _non_empty_string(payload["verdict"], "verdict").upper()
        if verdict in REJECTED_VERDICTS or verdict != "PASS":
            raise CertifiedArtifactError(
                f"verdict no elegible para infraestructura: {verdict}"
            )

        gate = payload["gate"]
        if not isinstance(gate, (str, Mapping)) or not gate:
            raise CertifiedArtifactError("gate debe ser un texto u objeto no vacío")
        if isinstance(gate, str) and not gate.strip():
            raise CertifiedArtifactError("gate no puede estar vacío")

        dataset_hash = _non_empty_string(payload["dataset_hash"], "dataset_hash")
        if not _HEX_SHA256.fullmatch(dataset_hash):
            raise CertifiedArtifactError("dataset_hash debe ser SHA-256 hexadecimal")

        code_commit = _non_empty_string(payload["code_commit"], "code_commit")
        if not _HEX_COMMIT.fullmatch(code_commit):
            raise CertifiedArtifactError("code_commit debe ser un hash Git hexadecimal")

        scope = payload["scope"]
        if not isinstance(scope, Mapping) or not scope:
            raise CertifiedArtifactError("scope debe ser un objeto no vacío")

        metrics = payload["metrics"]
        if not isinstance(metrics, Mapping) or not metrics:
            raise CertifiedArtifactError("metrics debe ser un objeto no vacío")

        artifact_paths = _relative_artifact_paths(payload["artifact_paths"])
        produced_at = _non_empty_string(payload["produced_at"], "produced_at")
        _parse_timestamp(produced_at)
        certifier = _non_empty_string(payload["certifier"], "certifier")

        return cls(
            experiment_id=experiment_id,
            verdict=verdict,
            gate=gate,
            dataset_hash=dataset_hash,
            code_commit=code_commit,
            scope=dict(scope),
            metrics=dict(metrics),
            artifact_paths=artifact_paths,
            produced_at=produced_at,
            certifier=certifier,
            schema_version=schema_version,
        )


def validate_certified_manifest(
    payload: Mapping[str, Any],
) -> CertifiedExperimentManifest:
    """Valida y devuelve un manifest inmutable, sin modificar el payload."""

    return CertifiedExperimentManifest.from_mapping(payload)


def load_certified_manifest(path: str | Path) -> CertifiedExperimentManifest:
    """Lee un JSON existente en modo lectura y aplica el contrato estricto."""

    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CertifiedArtifactError(
            f"No se pudo leer manifest JSON: {manifest_path}"
        ) from exc
    return validate_certified_manifest(payload)


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CertifiedArtifactError(f"{field} debe ser texto no vacío")
    return value.strip()


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CertifiedArtifactError("produced_at debe ser ISO-8601") from exc


def _relative_artifact_paths(value: Any) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise CertifiedArtifactError("artifact_paths debe ser una lista no vacía")

    paths: list[str] = []
    for raw_path in value:
        path = _non_empty_string(raw_path, "artifact_paths")
        normalized = path.replace("\\", "/")
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
            raise CertifiedArtifactError("artifact_paths debe usar rutas relativas")
        if ".." in Path(normalized).parts:
            raise CertifiedArtifactError("artifact_paths no puede escapar del workspace")
        paths.append(normalized)
    return tuple(paths)
