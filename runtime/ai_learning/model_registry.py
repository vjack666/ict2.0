"""Registro persistente e inmutable de modelos y checkpoints de INF-3.

El registry vive fuera de las rutas del laboratorio. Solo acepta snapshots
certificados de INF-2, conserva el lineage completo y escribe un índice JSON
que nunca reemplaza un registro o un checkpoint existente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid
from typing import Any, Mapping, Sequence

from .certified_artifacts import CertifiedArtifactError, validate_certified_manifest
from .dataset_snapshots import (
    DatasetSnapshot,
    DatasetSnapshotError,
    hash_dataset,
    load_dataset_snapshot,
)


MODEL_REGISTRY_SCHEMA_VERSION = "1.0"
_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PROTECTED_PREFIXES = (
    ("scripts", "lab"),
    ("data", "learning", "pipeline"),
    ("reports", "audits", "experiments"),
)
_PROTECTED_PARTS = frozenset({"datasets", "runners", "lab", "pipeline"})


class ModelRegistryError(ValueError):
    """Error de contrato, persistencia o recuperación del registry."""


class ModelLineageError(ModelRegistryError):
    """El modelo no tiene lineage certificado y reproducible."""


class ModelCompatibilityError(ModelRegistryError):
    """Features/labels no son compatibles con el snapshot registrado."""


class DuplicateModelError(ModelRegistryError):
    """Ya existe el par model_id/version y no puede sobrescribirse."""


class DuplicateCheckpointError(ModelRegistryError):
    """Ya existe el checkpoint y no puede sobrescribirse."""


@dataclass(frozen=True)
class ModelRecord:
    model_id: str
    version: str
    git_commit: str
    snapshot_id: str
    dataset_hash: str
    schema_hash: str
    experiment_id: str
    features: tuple[str, ...]
    labels: tuple[str, ...]
    seed: int
    config: Mapping[str, Any]
    created_at: str

    @property
    def key(self) -> str:
        return f"{self.model_id}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "git_commit": self.git_commit,
            "snapshot_id": self.snapshot_id,
            "dataset_hash": self.dataset_hash,
            "schema_hash": self.schema_hash,
            "experiment_id": self.experiment_id,
            "features": list(self.features),
            "labels": list(self.labels),
            "seed": self.seed,
            "config": _json_safe(self.config),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CheckpointRecord:
    checkpoint_id: str
    model_id: str
    version: str
    checkpoint_hash: str
    checkpoint_path: Path
    created_at: str
    metadata: Mapping[str, Any]

    @property
    def model_key(self) -> str:
        return f"{self.model_id}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "model_id": self.model_id,
            "version": self.version,
            "checkpoint_hash": self.checkpoint_hash,
            "checkpoint_path": self.checkpoint_path.name,
            "created_at": self.created_at,
            "metadata": _json_safe(self.metadata),
        }


@dataclass(frozen=True)
class _SnapshotLineage:
    snapshot_id: str
    dataset_hash: str
    schema_hash: str
    columns: frozenset[str]
    experiment_id: str


class ModelRegistry:
    """Registry JSON con registros y checkpoints append-only por identidad."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        _assert_registry_destination(self.root)
        self.registry_path = self.root / "registry.json"
        self.checkpoints_dir = self.root / "checkpoints"
        self._models: dict[str, ModelRecord] = {}
        self._checkpoints: dict[str, CheckpointRecord] = {}
        if self.registry_path.exists():
            self._load()

    def register_model(
        self,
        model_id: str,
        version: str,
        *,
        git_commit: str,
        snapshot: DatasetSnapshot | Mapping[str, Any] | str | Path | None = None,
        dataset_snapshot: DatasetSnapshot | Mapping[str, Any] | str | Path | None = None,
        snapshot_id: str | None = None,
        dataset_hash: str | None = None,
        features: Sequence[str],
        labels: Sequence[str],
        seed: int,
        config: Mapping[str, Any],
        created_at: str | None = None,
    ) -> ModelRecord:
        """Registra un modelo una sola vez y valida su snapshot de origen."""

        model_id = _safe_id(model_id, "model_id")
        version = _safe_id(version, "version")
        key = f"{model_id}@{version}"
        if key in self._models:
            raise DuplicateModelError(f"model_id/version ya registrado: {key}")

        if snapshot is not None and dataset_snapshot is not None:
            raise ModelLineageError("use snapshot o dataset_snapshot, no ambos")
        source_snapshot = snapshot if snapshot is not None else dataset_snapshot
        lineage = _validate_lineage(
            source_snapshot,
            expected_snapshot_id=snapshot_id,
            expected_dataset_hash=dataset_hash,
        )
        git_commit = _validate_commit(git_commit, "git_commit")
        normalized_features = _validate_names(features, "features")
        normalized_labels = _validate_names(labels, "labels")
        overlap = sorted(set(normalized_features).intersection(normalized_labels))
        if overlap:
            raise ModelCompatibilityError(
                "features y labels se solapan: " + ", ".join(overlap)
            )
        missing = sorted(set(normalized_features + normalized_labels) - lineage.columns)
        if missing:
            raise ModelCompatibilityError(
                "features/labels ausentes en el snapshot: " + ", ".join(missing)
            )
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ModelLineageError("seed debe ser entero")
        normalized_config = _validated_mapping(config, "config")
        timestamp = _validated_timestamp(created_at or _now_utc())
        record = ModelRecord(
            model_id=model_id,
            version=version,
            git_commit=git_commit,
            snapshot_id=lineage.snapshot_id,
            dataset_hash=lineage.dataset_hash,
            schema_hash=lineage.schema_hash,
            experiment_id=lineage.experiment_id,
            features=normalized_features,
            labels=normalized_labels,
            seed=seed,
            config=normalized_config,
            created_at=timestamp,
        )
        self._models[key] = record
        self._persist()
        return record

    def register_checkpoint(
        self,
        model_id: str,
        version: str,
        checkpoint_id: str,
        data: bytes | bytearray | str | Path | None = None,
        *,
        checkpoint_path: str | Path | None = None,
        metadata: Mapping[str, Any] | None = None,
        created_at: str | None = None,
    ) -> CheckpointRecord:
        """Guarda un checkpoint sin reemplazar el archivo ni su metadata."""

        model_key = f"{_safe_id(model_id, 'model_id')}@{_safe_id(version, 'version')}"
        if model_key not in self._models:
            raise ModelRegistryError(f"modelo no registrado: {model_key}")
        checkpoint_id = _safe_id(checkpoint_id, "checkpoint_id")
        key = f"{model_key}#{checkpoint_id}"
        if key in self._checkpoints:
            raise DuplicateCheckpointError(f"checkpoint ya registrado: {key}")
        if data is not None and checkpoint_path is not None:
            raise ModelRegistryError("use data o checkpoint_path, no ambos")
        source = checkpoint_path if checkpoint_path is not None else data
        payload = _read_checkpoint_data(source)
        model = self._models[model_key]
        normalized_metadata = _validated_mapping(metadata or {}, "metadata", allow_empty=True)
        required_metadata = {
            "model_id": model.model_id,
            "model_version": model.version,
            "dataset_hash": model.dataset_hash,
            "features": list(model.features),
            "labels": list(model.labels),
            "seed": model.seed,
        }
        for field, expected in required_metadata.items():
            if field in normalized_metadata and normalized_metadata[field] != expected:
                raise ModelCompatibilityError(
                    f"metadata de checkpoint incompatible en {field}"
                )
            normalized_metadata.setdefault(field, expected)
        timestamp = _validated_timestamp(created_at or _now_utc())
        checkpoint_hash = hashlib.sha256(payload).hexdigest()
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        storage_name = hashlib.sha256(key.encode("utf-8")).hexdigest() + ".bin"
        destination = self.checkpoints_dir / storage_name
        if destination.exists():
            raise DuplicateCheckpointError(
                f"archivo de checkpoint ya existe; no se sobrescribe: {destination}"
            )
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(payload)
            temporary.replace(destination)
        except OSError as exc:
            if destination.exists():
                raise DuplicateCheckpointError(
                    f"archivo de checkpoint ya existe; no se sobrescribe: {destination}"
                ) from exc
            raise ModelRegistryError("no se pudo publicar checkpoint") from exc
        finally:
            if temporary.exists():
                temporary.unlink()
        record = CheckpointRecord(
            checkpoint_id=checkpoint_id,
            model_id=model_id,
            version=version,
            checkpoint_hash=checkpoint_hash,
            checkpoint_path=destination,
            created_at=timestamp,
            metadata=normalized_metadata,
        )
        self._checkpoints[key] = record
        try:
            self._persist()
        except Exception:
            # El archivo se conserva: la política de INF-3 prohíbe borrar o
            # reemplazar checkpoints aunque falle la escritura del índice.
            raise
        return record

    def get_model(self, model_id: str, version: str) -> ModelRecord:
        key = f"{_safe_id(model_id, 'model_id')}@{_safe_id(version, 'version')}"
        try:
            return self._models[key]
        except KeyError as exc:
            raise ModelRegistryError(f"modelo no registrado: {key}") from exc

    def get(self, model_id: str, version: str) -> ModelRecord:
        """Alias breve para lectura de un registro inmutable."""

        return self.get_model(model_id, version)

    def get_checkpoint(
        self, model_id: str, version: str, checkpoint_id: str
    ) -> CheckpointRecord:
        key = f"{_safe_id(model_id, 'model_id')}@{_safe_id(version, 'version')}#{_safe_id(checkpoint_id, 'checkpoint_id')}"
        try:
            return self._checkpoints[key]
        except KeyError as exc:
            raise ModelRegistryError(f"checkpoint no registrado: {key}") from exc

    def list_models(self) -> tuple[ModelRecord, ...]:
        return tuple(self._models[key] for key in sorted(self._models))

    def load_checkpoint(
        self, model_id: str, version: str, checkpoint_id: str
    ) -> bytes:
        record = self.get_checkpoint(model_id, version, checkpoint_id)
        try:
            payload = record.checkpoint_path.read_bytes()
        except OSError as exc:
            raise ModelRegistryError("no se pudo recuperar el checkpoint") from exc
        if hashlib.sha256(payload).hexdigest() != record.checkpoint_hash:
            raise ModelRegistryError("checkpoint alterado: hash no coincide")
        return payload

    def recover_checkpoint(
        self, model_id: str, version: str, checkpoint_id: str
    ) -> bytes:
        """Recuperación exacta y verificable del checkpoint solicitado."""

        return self.load_checkpoint(model_id, version, checkpoint_id)

    def rollback(self, model_id: str, version: str, checkpoint_id: str) -> bytes:
        """Alias explícito de recuperación para rollback determinista."""

        return self.recover_checkpoint(model_id, version, checkpoint_id)

    def recover_model(
        self, model_id: str, version: str, checkpoint_id: str
    ) -> tuple[ModelRecord, bytes]:
        return self.get_model(model_id, version), self.recover_checkpoint(
            model_id, version, checkpoint_id
        )

    def recover(
        self, model_id: str, version: str, checkpoint_id: str | None = None
    ) -> tuple[ModelRecord, bytes]:
        """Recupera el checkpoint solicitado o el último por orden estable."""

        if checkpoint_id is None:
            model_key = f"{_safe_id(model_id, 'model_id')}@{_safe_id(version, 'version')}"
            candidates = [
                record
                for key, record in self._checkpoints.items()
                if key.startswith(model_key + "#")
            ]
            if not candidates:
                raise ModelRegistryError(f"modelo sin checkpoints: {model_key}")
            checkpoint_id = sorted(
                candidates, key=lambda item: item.checkpoint_id
            )[-1].checkpoint_id
        return self.recover_model(model_id, version, checkpoint_id)

    def _load(self) -> None:
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"registry JSON inválido: {self.registry_path}") from exc
        if not isinstance(payload, Mapping) or payload.get("schema_version") != MODEL_REGISTRY_SCHEMA_VERSION:
            raise ModelRegistryError("schema_version de registry no soportada")
        models = payload.get("models")
        checkpoints = payload.get("checkpoints")
        if not isinstance(models, list) or not isinstance(checkpoints, list):
            raise ModelRegistryError("registry debe contener listas models y checkpoints")
        for item in models:
            record = _model_from_dict(item)
            if record.key in self._models:
                raise ModelRegistryError("registry contiene modelos duplicados")
            self._models[record.key] = record
        for item in checkpoints:
            record = _checkpoint_from_dict(item, self.checkpoints_dir)
            key = f"{record.model_key}#{record.checkpoint_id}"
            if key in self._checkpoints:
                raise ModelRegistryError("registry contiene checkpoints duplicados")
            if record.model_key not in self._models:
                raise ModelRegistryError("checkpoint referencia modelo inexistente")
            if not record.checkpoint_path.is_file():
                raise ModelRegistryError("checkpoint registrado no existe")
            if hashlib.sha256(record.checkpoint_path.read_bytes()).hexdigest() != record.checkpoint_hash:
                raise ModelRegistryError("checkpoint registrado alterado")
            model = self._models[record.model_key]
            expected_metadata = {
                "model_id": model.model_id,
                "model_version": model.version,
                "dataset_hash": model.dataset_hash,
                "features": list(model.features),
                "labels": list(model.labels),
                "seed": model.seed,
            }
            if any(record.metadata.get(field) != expected for field, expected in expected_metadata.items()):
                raise ModelRegistryError("metadata de checkpoint incompatible con modelo")
            self._checkpoints[key] = record

    def _persist(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": MODEL_REGISTRY_SCHEMA_VERSION,
            "models": [self._models[key].to_dict() for key in sorted(self._models)],
            "checkpoints": [
                self._checkpoints[key].to_dict() for key in sorted(self._checkpoints)
            ],
        }
        temporary = self.registry_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.registry_path)


def validate_model_dataset_compatibility(
    snapshot: DatasetSnapshot | Mapping[str, Any] | str | Path,
    *,
    features: Sequence[str],
    labels: Sequence[str],
) -> None:
    """Valida compatibilidad sin registrar ni modificar ningún artefacto."""

    lineage = _validate_lineage(snapshot)
    normalized_features = _validate_names(features, "features")
    normalized_labels = _validate_names(labels, "labels")
    overlap = sorted(set(normalized_features).intersection(normalized_labels))
    if overlap:
        raise ModelCompatibilityError("features y labels se solapan: " + ", ".join(overlap))
    missing = sorted(set(normalized_features + normalized_labels) - lineage.columns)
    if missing:
        raise ModelCompatibilityError(
            "features/labels ausentes en el snapshot: " + ", ".join(missing)
        )


def _validate_lineage(
    snapshot: DatasetSnapshot | Mapping[str, Any] | str | Path | None,
    *,
    expected_snapshot_id: str | None = None,
    expected_dataset_hash: str | None = None,
) -> _SnapshotLineage:
    if snapshot is None:
        raise ModelLineageError("snapshot certificado requerido para lineage completo")
    snapshot_object: DatasetSnapshot | None = None
    if isinstance(snapshot, (str, Path)):
        try:
            snapshot = load_dataset_snapshot(snapshot)
        except DatasetSnapshotError as exc:
            raise ModelLineageError(f"snapshot inválido: {exc}") from exc
    if isinstance(snapshot, DatasetSnapshot):
        snapshot_object = snapshot
        payload = snapshot.to_dict()
    elif isinstance(snapshot, Mapping):
        payload = dict(snapshot)
    else:
        raise ModelLineageError("snapshot debe ser DatasetSnapshot, mapping o ruta")
    required = {
        "snapshot_id", "dataset_hash", "schema_hash", "schema", "experiment_id",
        "source_path", "source_code_commit", "consumer_code_commit", "certified_manifest",
        "config", "created_at",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ModelLineageError("snapshot incompleto; faltan: " + ", ".join(missing))
    snapshot_id = _validate_hash(payload["snapshot_id"], "snapshot_id")
    dataset_hash = _validate_hash(payload["dataset_hash"], "dataset_hash")
    schema_hash = _validate_hash(payload["schema_hash"], "schema_hash")
    if expected_snapshot_id is not None and snapshot_id != _validate_hash(expected_snapshot_id, "snapshot_id"):
        raise ModelLineageError("snapshot_id no coincide con el lineage")
    if expected_dataset_hash is not None and dataset_hash != _validate_hash(expected_dataset_hash, "dataset_hash"):
        raise ModelLineageError("dataset_hash no coincide con el lineage")
    _non_empty(payload["source_path"], "source_path")
    source_code_commit = _validate_commit(payload["source_code_commit"], "source_code_commit")
    consumer_code_commit = _validate_commit(payload["consumer_code_commit"], "consumer_code_commit")
    experiment_id = _non_empty(payload["experiment_id"], "experiment_id")
    snapshot_config = _validated_mapping(payload["config"], "config")
    _validated_timestamp(payload["created_at"])
    try:
        manifest = validate_certified_manifest(payload["certified_manifest"])
    except (CertifiedArtifactError, TypeError) as exc:
        raise ModelLineageError(f"certified_manifest inválido: {exc}") from exc
    if (
        manifest.experiment_id != experiment_id
        or manifest.dataset_hash.lower() != dataset_hash
        or manifest.code_commit.lower() != source_code_commit
        or str(payload["source_path"]).replace("\\", "/") not in manifest.artifact_paths
    ):
        raise ModelLineageError("snapshot y manifest no coinciden")
    stable_identity = {
        "dataset_hash": dataset_hash,
        "schema_hash": schema_hash,
        "experiment_id": experiment_id,
        "source_code_commit": source_code_commit,
        "consumer_code_commit": consumer_code_commit,
        "config": snapshot_config,
    }
    expected_identity = hashlib.sha256(_canonical_json(stable_identity)).hexdigest()
    if expected_identity != snapshot_id:
        raise ModelLineageError("snapshot_id no coincide con la identidad canónica")
    schema = payload["schema"]
    if not isinstance(schema, Mapping) or not isinstance(schema.get("columns"), list):
        raise ModelLineageError("schema del snapshot incompleto")
    columns = frozenset(
        column for column in schema["columns"] if isinstance(column, str) and column
    )
    if len(columns) != len(schema["columns"]):
        raise ModelLineageError("schema.columns inválido")
    computed_schema = _schema_hash(schema)
    if computed_schema != schema_hash:
        raise ModelLineageError("schema_hash no coincide con schema")
    if snapshot_object is not None:
        try:
            if hash_dataset(snapshot_object.data_path) != dataset_hash:
                raise ModelLineageError("contenido del snapshot no coincide con dataset_hash")
        except (OSError, DatasetSnapshotError) as exc:
            raise ModelLineageError("contenido del snapshot no es recuperable") from exc
    return _SnapshotLineage(snapshot_id, dataset_hash, schema_hash, columns, experiment_id)


def _model_from_dict(payload: Any) -> ModelRecord:
    if not isinstance(payload, Mapping):
        raise ModelRegistryError("registro de modelo inválido")
    required = {
        "model_id", "version", "git_commit", "snapshot_id", "dataset_hash",
        "schema_hash", "experiment_id", "features", "labels", "seed", "config", "created_at",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ModelRegistryError("registro de modelo incompleto; faltan: " + ", ".join(missing))
    model_id = _safe_id(payload["model_id"], "model_id")
    version = _safe_id(payload["version"], "version")
    features = _validate_names(payload["features"], "features")
    labels = _validate_names(payload["labels"], "labels")
    if set(features).intersection(labels):
        raise ModelRegistryError("registro de modelo con features/labels solapados")
    if isinstance(payload["seed"], bool) or not isinstance(payload["seed"], int):
        raise ModelRegistryError("seed de modelo inválido")
    return ModelRecord(
        model_id=model_id,
        version=version,
        git_commit=_validate_commit(payload["git_commit"], "git_commit"),
        snapshot_id=_validate_hash(payload["snapshot_id"], "snapshot_id"),
        dataset_hash=_validate_hash(payload["dataset_hash"], "dataset_hash"),
        schema_hash=_validate_hash(payload["schema_hash"], "schema_hash"),
        experiment_id=_non_empty(payload["experiment_id"], "experiment_id"),
        features=features,
        labels=labels,
        seed=payload["seed"],
        config=_validated_mapping(payload["config"], "config"),
        created_at=_validated_timestamp(payload["created_at"]),
    )


def _checkpoint_from_dict(payload: Any, root: Path) -> CheckpointRecord:
    if not isinstance(payload, Mapping):
        raise ModelRegistryError("registro de checkpoint inválido")
    required = {"checkpoint_id", "model_id", "version", "checkpoint_hash", "checkpoint_path", "created_at", "metadata"}
    missing = sorted(required.difference(payload))
    if missing:
        raise ModelRegistryError("registro de checkpoint incompleto; faltan: " + ", ".join(missing))
    checkpoint_id = _safe_id(payload["checkpoint_id"], "checkpoint_id")
    filename = payload["checkpoint_path"]
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ModelRegistryError("checkpoint_path inválido")
    path = (root / filename).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ModelRegistryError("checkpoint_path escapa del registry") from exc
    return CheckpointRecord(
        checkpoint_id=checkpoint_id,
        model_id=_safe_id(payload["model_id"], "model_id"),
        version=_safe_id(payload["version"], "version"),
        checkpoint_hash=_validate_hash(payload["checkpoint_hash"], "checkpoint_hash"),
        checkpoint_path=path,
        created_at=_validated_timestamp(payload["created_at"]),
        metadata=_validated_mapping(payload["metadata"], "metadata", allow_empty=True),
    )


def _read_checkpoint_data(source: bytes | bytearray | str | Path | None) -> bytes:
    if source is None:
        raise ModelRegistryError("checkpoint data requerido")
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, Path) or (isinstance(source, str) and Path(source).is_file()):
        try:
            return Path(source).read_bytes()
        except OSError as exc:
            raise ModelRegistryError("no se pudo leer checkpoint") from exc
    if isinstance(source, str):
        return source.encode("utf-8")
    raise ModelRegistryError("checkpoint data debe ser bytes, texto o ruta")


def _schema_hash(schema: Mapping[str, Any]) -> str:
    columns = schema.get("columns")
    types = schema.get("types")
    format_name = schema.get("format")
    if not isinstance(columns, list) or not isinstance(types, Mapping) or not isinstance(format_name, str):
        raise ModelLineageError("schema incompleto")
    base = {"format": format_name, "columns": columns, "types": types}
    return hashlib.sha256(_canonical_json(base)).hexdigest()


def _assert_registry_destination(root: Path) -> None:
    parts = tuple(part.lower() for part in root.parts)
    if any(_contains_parts(parts, prefix) for prefix in _PROTECTED_PREFIXES):
        raise ModelRegistryError("registry debe estar fuera de la frontera Hermes; ruta protegida")
    if any(part in _PROTECTED_PARTS for part in parts):
        raise ModelRegistryError("registry está dentro de una ruta protegida")


def _contains_parts(parts: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    width = len(sequence)
    return any(parts[index : index + width] == sequence for index in range(len(parts) - width + 1))


def _safe_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ModelRegistryError(f"{field} debe ser un identificador seguro no vacío")
    return value


def _validate_names(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise ModelCompatibilityError(f"{field} debe ser una lista no vacía")
    names = tuple(_non_empty(item, field) for item in value)
    if len(set(names)) != len(names):
        raise ModelCompatibilityError(f"{field} contiene duplicados")
    return names


def _validated_mapping(value: Any, field: str, *, allow_empty: bool = False) -> dict[str, Any]:
    if not isinstance(value, Mapping) or (not allow_empty and not value):
        raise ModelLineageError(f"{field} debe ser un objeto {'vacío o ' if allow_empty else ''}JSON")
    result = dict(_json_safe(dict(value)))
    return result


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ModelLineageError("valor no serializable a JSON") from exc
    return value


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_SHA256.fullmatch(value):
        raise ModelLineageError(f"{field} debe ser SHA-256 hexadecimal")
    return value.lower()


def _validate_commit(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_COMMIT.fullmatch(value):
        raise ModelLineageError(f"{field} debe ser hash Git hexadecimal")
    return value.lower()


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelLineageError(f"{field} debe ser texto no vacío")
    return value.strip()


def _validated_timestamp(value: Any) -> str:
    text = _non_empty(value, "created_at")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelLineageError("created_at debe ser ISO-8601") from exc
    return text


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


__all__ = [
    "MODEL_REGISTRY_SCHEMA_VERSION",
    "CheckpointRecord",
    "DuplicateCheckpointError",
    "DuplicateModelError",
    "ModelCompatibilityError",
    "ModelLineageError",
    "ModelRecord",
    "ModelRegistry",
    "ModelRegistryError",
    "validate_model_dataset_compatibility",
]
