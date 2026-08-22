"""Almacenamiento local e inmutable de checkpoints de modelos.

Los checkpoints son artefactos de la infraestructura de aprendizaje. Cada
checkpoint vive en su propio directorio y contiene metadata, estado e
integridad verificable. El puntero de rollback es mutable, pero nunca se
modifica un checkpoint ya publicado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
from typing import Any, Mapping, Sequence


CHECKPOINT_SCHEMA_VERSION = "1.0"
_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_SAFE_CHECKPOINT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PROTECTED_PARTS = frozenset({"datasets", "runners", "lab", "pipeline"})
_PROTECTED_PREFIXES = (
    ("scripts", "lab"),
    ("data", "learning", "pipeline"),
    ("reports", "audits", "experiments"),
)


class CheckpointStoreError(ValueError):
    """El checkpoint no cumple el contrato de almacenamiento."""


class CheckpointExistsError(CheckpointStoreError):
    """El identificador ya está ocupado y no puede sobrescribirse."""


class CheckpointIntegrityError(CheckpointStoreError):
    """El checkpoint fue alterado o su manifest es inconsistente."""


@dataclass(frozen=True)
class Checkpoint:
    """Checkpoint cargado y validado desde disco."""

    checkpoint_id: str
    checkpoint_path: Path
    metadata: Mapping[str, Any]
    state: Mapping[str, Any]
    created_at: str

    @property
    def model_id(self) -> str:
        return self.metadata["model_id"]

    @property
    def model_version(self) -> str:
        return self.metadata["model_version"]

    @property
    def dataset_hash(self) -> str:
        return self.metadata["dataset_hash"]

    @property
    def features(self) -> Any:
        return self.metadata["features"]

    @property
    def labels(self) -> Any:
        return self.metadata["labels"]

    @property
    def seed(self) -> Any:
        return self.metadata["seed"]


class CheckpointStore:
    """Persiste checkpoints sin depender de estado en memoria."""

    def __init__(self, root_dir: str | Path, *, workspace_root: str | Path | None = None):
        self.root_dir = Path(root_dir).resolve()
        self.workspace_root = (
            Path(workspace_root).resolve() if workspace_root is not None else None
        )
        _assert_safe_destination(self.root_dir, self.workspace_root)
        self._active_path = self.root_dir / "active.json"

    def save(
        self,
        state: Mapping[str, Any],
        *,
        model_id: str,
        model_version: str,
        dataset_hash: str,
        features: Any,
        labels: Any,
        seed: Any,
        checkpoint_id: str | None = None,
    ) -> Checkpoint:
        """Publica un checkpoint nuevo sin sobrescribir uno existente."""

        normalized_state = _json_object(state, "state")
        metadata = {
            "model_id": _safe_model_value(model_id, "model_id"),
            "model_version": _safe_model_value(model_version, "model_version"),
            "dataset_hash": _validate_hash(dataset_hash, "dataset_hash"),
            "features": _metadata_sequence(features, "features"),
            "labels": _metadata_sequence(labels, "labels"),
            "seed": _validate_seed(seed),
        }
        identifier = checkpoint_id or uuid.uuid4().hex
        _validate_checkpoint_id(identifier)
        created_at = _now_utc()
        metadata_payload = {
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_id": identifier,
            "created_at": created_at,
            **metadata,
        }
        state_payload = {"state": normalized_state}
        metadata_hash = _sha256_json(metadata_payload)
        state_hash = _sha256_json(state_payload)
        manifest_payload = {
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_id": identifier,
            "metadata_hash": metadata_hash,
            "state_hash": state_hash,
            "checkpoint_hash": _sha256_json(
                {
                    "checkpoint_id": identifier,
                    "metadata_hash": metadata_hash,
                    "state_hash": state_hash,
                }
            ),
        }

        self.root_dir.mkdir(parents=True, exist_ok=True)
        destination = self.root_dir / identifier
        if destination.exists():
            raise CheckpointExistsError(
                f"checkpoint_id ya existe y no se sobrescribe: {identifier}"
            )
        temporary = self.root_dir / f".{identifier}.{uuid.uuid4().hex}.tmp"
        try:
            temporary.mkdir()
            _write_json(temporary / "metadata.json", metadata_payload)
            _write_json(temporary / "state.json", state_payload)
            _write_json(temporary / "manifest.json", manifest_payload)
            # Renombrar el directorio completo evita publicar un checkpoint
            # parcialmente escrito y falla si otro proceso ganó la colisión.
            temporary.replace(destination)
        except CheckpointExistsError:
            raise
        except OSError as exc:
            if destination.exists():
                raise CheckpointExistsError(
                    f"checkpoint_id ya existe y no se sobrescribe: {identifier}"
                ) from exc
            raise CheckpointStoreError(f"no se pudo publicar checkpoint: {identifier}") from exc
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

        return self.load(identifier)

    def load(self, checkpoint_id: str | None = None) -> Checkpoint:
        """Carga y verifica un checkpoint; sin ID usa el activo o el más reciente."""

        identifier = checkpoint_id or self._active_checkpoint_id() or self._latest_checkpoint_id()
        if identifier is None:
            raise CheckpointStoreError("no hay checkpoints almacenados")
        _validate_checkpoint_id(identifier)
        root = self.root_dir / identifier
        return _load_checkpoint(root, expected_id=identifier)

    def rollback(self, checkpoint_id: str) -> Checkpoint:
        """Selecciona un checkpoint existente sin alterar su contenido."""

        checkpoint = self.load(checkpoint_id)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.root_dir / f".active.{uuid.uuid4().hex}.tmp"
        try:
            _write_json(
                temporary,
                {
                    "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
                    "checkpoint_id": checkpoint.checkpoint_id,
                },
            )
            temporary.replace(self._active_path)
        except OSError as exc:
            raise CheckpointStoreError("no se pudo registrar el rollback") from exc
        finally:
            if temporary.exists():
                temporary.unlink()
        return checkpoint

    def list_checkpoints(self) -> tuple[str, ...]:
        """Enumera checkpoints válidos por fecha de creación, sin usar índice mutable."""

        if not self.root_dir.is_dir():
            return ()
        records: list[tuple[str, str]] = []
        for child in self.root_dir.iterdir():
            if child.is_dir() and _SAFE_CHECKPOINT_ID.fullmatch(child.name):
                checkpoint = _load_checkpoint(child, expected_id=child.name)
                records.append((checkpoint.created_at, checkpoint.checkpoint_id))
        return tuple(identifier for _, identifier in sorted(records))

    def save_checkpoint(self, *args: Any, **kwargs: Any) -> Checkpoint:
        """Alias explícito para integraciones que usan el nombre de operación."""

        return self.save(*args, **kwargs)

    def load_checkpoint(self, checkpoint_id: str | None = None) -> Checkpoint:
        """Alias explícito para integraciones que usan el nombre de operación."""

        return self.load(checkpoint_id)

    def rollback_to(self, checkpoint_id: str) -> Checkpoint:
        """Alias explícito para rollback."""

        return self.rollback(checkpoint_id)

    def _active_checkpoint_id(self) -> str | None:
        if not self._active_path.is_file():
            return None
        try:
            payload = json.loads(self._active_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointIntegrityError("active.json inválido") from exc
        if not isinstance(payload, Mapping) or payload.get("checkpoint_schema_version") != CHECKPOINT_SCHEMA_VERSION:
            raise CheckpointIntegrityError("active.json inválido")
        identifier = payload.get("checkpoint_id")
        _validate_checkpoint_id(identifier)
        return identifier

    def _latest_checkpoint_id(self) -> str | None:
        identifiers = self.list_checkpoints()
        return identifiers[-1] if identifiers else None


def load_checkpoint(path: str | Path) -> Checkpoint:
    """Carga un checkpoint directamente desde su directorio."""

    root = Path(path).resolve()
    return _load_checkpoint(root, expected_id=root.name)


def _load_checkpoint(root: Path, *, expected_id: str) -> Checkpoint:
    if not root.is_dir():
        raise CheckpointStoreError(f"checkpoint inexistente: {root}")
    try:
        metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
        state_payload = json.loads((root / "state.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointIntegrityError(f"checkpoint ilegible: {root}") from exc
    if not isinstance(metadata, Mapping) or not isinstance(state_payload, Mapping) or not isinstance(manifest, Mapping):
        raise CheckpointIntegrityError("archivos del checkpoint deben ser objetos JSON")
    if metadata.get("checkpoint_schema_version") != CHECKPOINT_SCHEMA_VERSION or manifest.get("checkpoint_schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointIntegrityError("checkpoint_schema_version no soportada")
    if metadata.get("checkpoint_id") != expected_id or manifest.get("checkpoint_id") != expected_id:
        raise CheckpointIntegrityError("checkpoint_id inconsistente")
    if not isinstance(state_payload.get("state"), Mapping):
        raise CheckpointIntegrityError("state.json debe contener un objeto state")
    metadata_hash = _sha256_json(metadata)
    state_hash = _sha256_json(state_payload)
    if manifest.get("metadata_hash") != metadata_hash or manifest.get("state_hash") != state_hash:
        raise CheckpointIntegrityError("integridad del checkpoint no válida")
    expected_checkpoint_hash = _sha256_json(
        {
            "checkpoint_id": expected_id,
            "metadata_hash": metadata_hash,
            "state_hash": state_hash,
        }
    )
    if manifest.get("checkpoint_hash") != expected_checkpoint_hash:
        raise CheckpointIntegrityError("checkpoint_hash no coincide")
    _validate_metadata(metadata)
    created_at = _validated_timestamp(metadata["created_at"])
    return Checkpoint(
        checkpoint_id=expected_id,
        checkpoint_path=root,
        metadata=dict(metadata),
        state=dict(state_payload["state"]),
        created_at=created_at,
    )


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    for field in ("model_id", "model_version"):
        value = _non_empty(metadata.get(field), field)
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise CheckpointIntegrityError(f"{field} contiene una ruta inválida")
    _validate_hash(metadata.get("dataset_hash"), "dataset_hash")
    for field in ("features", "labels"):
        if field not in metadata:
            raise CheckpointIntegrityError(f"metadata incompleta; falta {field}")
        _metadata_sequence(metadata[field], field)
    _validate_seed(metadata.get("seed"))


def _assert_safe_destination(path: Path, workspace_root: Path | None) -> None:
    check = path
    if workspace_root is not None:
        try:
            relative = path.relative_to(workspace_root)
        except ValueError:
            relative = path
    else:
        relative = path
    parts = tuple(part.lower() for part in relative.parts)
    if any(_contains_parts(parts, prefix) for prefix in _PROTECTED_PREFIXES):
        raise CheckpointStoreError("root_dir está protegido por la frontera Hermes")
    if any(part in _PROTECTED_PARTS for part in parts):
        raise CheckpointStoreError("root_dir está dentro de una ruta protegida")


def _contains_parts(parts: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    width = len(sequence)
    return any(parts[index : index + width] == sequence for index in range(len(parts) - width + 1))


def _validate_checkpoint_id(value: Any) -> str:
    if not isinstance(value, str) or not _SAFE_CHECKPOINT_ID.fullmatch(value) or value in {"active", "metadata", "state", "manifest"}:
        raise CheckpointStoreError("checkpoint_id debe ser un nombre local seguro")
    return value


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_SHA256.fullmatch(value):
        raise CheckpointStoreError(f"{field} debe ser SHA-256 hexadecimal")
    return value.lower()


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckpointStoreError(f"{field} debe ser texto no vacío")
    return value.strip()


def _safe_model_value(value: Any, field: str) -> str:
    text = _non_empty(value, field)
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise CheckpointStoreError(f"{field} contiene una ruta inválida")
    return text


def _metadata_sequence(value: Any, field: str) -> list[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise CheckpointStoreError(f"{field} debe ser una lista no vacía")
    normalized = list(_json_value(value, field))
    if not normalized:
        raise CheckpointStoreError(f"{field} debe ser una lista no vacía")
    return normalized


def _validate_seed(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CheckpointStoreError("seed debe ser un entero")
    return value


def _json_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CheckpointStoreError(f"{field} debe ser un objeto")
    return dict(_json_value(value, field))


def _json_value(value: Any, field: str) -> Any:
    try:
        normalized = json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise CheckpointStoreError(f"{field} debe ser JSON serializable") from exc
    return normalized


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validated_timestamp(value: Any) -> str:
    text = _non_empty(value, "created_at")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckpointIntegrityError("created_at debe ser ISO-8601") from exc
    return text


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "Checkpoint",
    "CheckpointExistsError",
    "CheckpointIntegrityError",
    "CheckpointStore",
    "CheckpointStoreError",
    "load_checkpoint",
]
