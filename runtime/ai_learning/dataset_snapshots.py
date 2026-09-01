"""Lectura y snapshots reproducibles de datasets certificados.

Este módulo es el límite INF-2 entre los artefactos certificados de Hermes y
la infraestructura de aprendizaje. Solo lee el origen. Los snapshots se
materializan en un directorio propiedad de esta infraestructura y nunca en
las rutas del laboratorio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any, Mapping, Sequence

from .certified_artifacts import (
    CertifiedArtifactError,
    CertifiedExperimentManifest,
    validate_certified_manifest,
)


DATASET_SNAPSHOT_SCHEMA_VERSION = "1.0"
_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
_PROTECTED_PARTS = frozenset(
    {
        "datasets",
        "runners",
        "lab",
        "pipeline",
    }
)
_PROTECTED_PREFIXES = (
    ("scripts", "lab"),
    ("data", "learning", "pipeline"),
    ("reports", "audits", "experiments"),
)


class DatasetSnapshotError(ValueError):
    """El dataset no puede cruzar el límite reproducible de INF-2."""


class DatasetSchemaChangedError(DatasetSnapshotError):
    """El esquema actual no coincide con el esquema registrado."""


@dataclass(frozen=True)
class DatasetSchema:
    """Esquema determinista derivado del contenido del dataset."""

    format: str
    columns: tuple[str, ...]
    types: tuple[tuple[str, tuple[str, ...]], ...]
    schema_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "columns": list(self.columns),
            "types": {column: list(types) for column, types in self.types},
            "schema_hash": self.schema_hash,
        }


@dataclass(frozen=True)
class DatasetSnapshot:
    """Registro inmutable de un snapshot local y su lineage certificado."""

    snapshot_id: str
    snapshot_path: Path
    data_path: Path
    metadata_path: Path
    source_path: str
    dataset_hash: str
    schema_hash: str
    schema: DatasetSchema
    row_count: int
    experiment_id: str
    source_code_commit: str
    consumer_code_commit: str
    certified_manifest: CertifiedExperimentManifest
    config: Mapping[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_schema_version": DATASET_SNAPSHOT_SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "source_path": self.source_path,
            "dataset_hash": self.dataset_hash,
            "schema_hash": self.schema_hash,
            "schema": self.schema.to_dict(),
            "row_count": self.row_count,
            "experiment_id": self.experiment_id,
            "code_commit": self.source_code_commit,
            "source_code_commit": self.source_code_commit,
            "consumer_code_commit": self.consumer_code_commit,
            "certified_manifest": _manifest_to_dict(self.certified_manifest),
            "config": _json_safe(self.config),
            "created_at": self.created_at,
            "data_path": self.data_path.name,
        }


class CertifiedDatasetReader:
    """Lee datasets certificados sin mutar el workspace de Hermes."""

    def __init__(self, workspace_root: str | Path):
        self.workspace_root = Path(workspace_root).resolve()
        if not self.workspace_root.is_dir():
            raise DatasetSnapshotError(f"workspace_root no existe: {workspace_root}")

    def inspect(
        self,
        manifest: CertifiedExperimentManifest | Mapping[str, Any],
        dataset_path: str | Path,
    ) -> tuple[tuple[dict[str, Any], ...], DatasetSchema, str, str]:
        """Lee e inspecciona un dataset, verificando su manifest y hash."""

        certified = _as_manifest(manifest)
        source = self._resolve_source(dataset_path)
        _assert_manifest_references_source(certified, source, self.workspace_root)
        source_hash = hash_dataset(source)
        if source_hash.lower() != certified.dataset_hash.lower():
            raise DatasetSnapshotError(
                "dataset_hash del manifest no coincide con el contenido de origen"
            )
        rows, schema = _read_rows_and_schema(source)
        return rows, schema, source_hash, _workspace_relative(source, self.workspace_root)

    def create_snapshot(
        self,
        manifest: CertifiedExperimentManifest | Mapping[str, Any],
        dataset_path: str | Path,
        output_dir: str | Path,
        *,
        config: Mapping[str, Any],
        consumer_code_commit: str,
        created_at: str | None = None,
    ) -> DatasetSnapshot:
        """Crea o recupera un snapshot sin sobrescribir uno existente.

        El identificador no contiene ``created_at``: con el mismo origen,
        código consumidor y configuración, dos ejecuciones producen el mismo
        ``snapshot_id`` aunque sus timestamps de registro sean distintos.
        """

        certified = _as_manifest(manifest)
        _validate_commit(consumer_code_commit, "consumer_code_commit")
        normalized_config = _validated_config(config)
        rows, schema, source_hash, source_ref = self.inspect(certified, dataset_path)
        destination = Path(output_dir).resolve()
        _assert_writable_snapshot_destination(destination, self.workspace_root)
        timestamp = _validated_timestamp(created_at or _now_utc())
        destination.mkdir(parents=True, exist_ok=True)

        stable_identity = {
            "dataset_hash": source_hash.lower(),
            "schema_hash": schema.schema_hash,
            "experiment_id": certified.experiment_id,
            "source_code_commit": certified.code_commit.lower(),
            "consumer_code_commit": consumer_code_commit.lower(),
            "config": normalized_config,
        }
        snapshot_id = hashlib.sha256(_canonical_json(stable_identity)).hexdigest()
        snapshot_path = destination / snapshot_id
        metadata_path = snapshot_path / "snapshot.json"
        data_name = Path(source_ref).name or "dataset"
        if data_name.lower() == "snapshot.json":
            data_name = "dataset" + Path(data_name).suffix

        if snapshot_path.exists():
            if not metadata_path.is_file():
                raise DatasetSnapshotError(
                    f"snapshot existente sin metadata; no se sobrescribe: {snapshot_path}"
                )
            existing = load_dataset_snapshot(snapshot_path)
            if existing.snapshot_id != snapshot_id:
                raise DatasetSnapshotError("snapshot existente con identidad inconsistente")
            return existing

        snapshot_path.mkdir()
        data_path = snapshot_path / data_name
        _copy_read_only_source(self._resolve_source(dataset_path), data_path)
        snapshot = DatasetSnapshot(
            snapshot_id=snapshot_id,
            snapshot_path=snapshot_path,
            data_path=data_path,
            metadata_path=metadata_path,
            source_path=source_ref,
            dataset_hash=source_hash.lower(),
            schema_hash=schema.schema_hash,
            schema=schema,
            row_count=len(rows),
            experiment_id=certified.experiment_id,
            source_code_commit=certified.code_commit.lower(),
            consumer_code_commit=consumer_code_commit.lower(),
            certified_manifest=certified,
            config=normalized_config,
            created_at=timestamp,
        )
        metadata_path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return snapshot

    def read_snapshot(self, snapshot_path: str | Path) -> tuple[dict[str, Any], ...]:
        """Lee únicamente la copia local y comprueba su integridad."""

        snapshot = load_dataset_snapshot(snapshot_path)
        rows, schema = _read_rows_and_schema(snapshot.data_path)
        if schema.schema_hash != snapshot.schema_hash or len(rows) != snapshot.row_count:
            raise DatasetSnapshotError("snapshot alterado: schema o row_count no coincide")
        if hash_dataset(snapshot.data_path) != snapshot.dataset_hash:
            raise DatasetSnapshotError("snapshot alterado: dataset_hash no coincide")
        return rows

    def schema_changed(
        self,
        dataset_path: str | Path,
        expected: DatasetSchema | Mapping[str, Any] | str,
    ) -> bool:
        """Indica si el esquema actual difiere del esquema registrado."""

        _, current = _read_rows_and_schema(self._resolve_source(dataset_path))
        expected_hash = _schema_hash_from_expected(expected)
        return current.schema_hash != expected_hash

    def assert_schema_compatible(
        self,
        dataset_path: str | Path,
        expected: DatasetSchema | Mapping[str, Any] | str,
    ) -> DatasetSchema:
        _, current = _read_rows_and_schema(self._resolve_source(dataset_path))
        expected_hash = _schema_hash_from_expected(expected)
        if current.schema_hash != expected_hash:
            raise DatasetSchemaChangedError(
                f"schema_hash incompatible: esperado {expected_hash}, actual {current.schema_hash}"
            )
        return current

    def _resolve_source(self, dataset_path: str | Path) -> Path:
        source = Path(dataset_path)
        if not source.is_absolute():
            source = self.workspace_root / source
        source = source.resolve()
        try:
            source.relative_to(self.workspace_root)
        except ValueError as exc:
            raise DatasetSnapshotError("dataset_path debe estar dentro de workspace_root") from exc
        if not source.is_file() and not source.is_dir():
            raise DatasetSnapshotError(f"dataset_path no existe: {dataset_path}")
        return source


def load_dataset_snapshot(snapshot_path: str | Path) -> DatasetSnapshot:
    """Carga y valida el registro de un snapshot existente."""

    root = Path(snapshot_path).resolve()
    metadata_path = root / "snapshot.json"
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetSnapshotError(f"snapshot.json inválido: {metadata_path}") from exc
    if payload.get("snapshot_schema_version") != DATASET_SNAPSHOT_SCHEMA_VERSION:
        raise DatasetSnapshotError("snapshot_schema_version no soportada")
    required = {
        "snapshot_id", "source_path", "dataset_hash", "schema_hash", "schema",
        "row_count", "experiment_id", "code_commit", "source_code_commit",
        "consumer_code_commit", "certified_manifest", "config", "created_at", "data_path",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise DatasetSnapshotError("snapshot incompleto; faltan: " + ", ".join(missing))
    if not isinstance(payload["row_count"], int) or payload["row_count"] < 0:
        raise DatasetSnapshotError("row_count debe ser entero no negativo")
    dataset_hash = _validate_hash(payload["dataset_hash"], "dataset_hash")
    schema_hash = _validate_hash(payload["schema_hash"], "schema_hash")
    source_commit = _validate_commit(payload["source_code_commit"], "source_code_commit")
    registered_commit = _validate_commit(payload["code_commit"], "code_commit")
    if registered_commit != source_commit:
        raise DatasetSnapshotError("code_commit no coincide con source_code_commit")
    consumer_commit = _validate_commit(payload["consumer_code_commit"], "consumer_code_commit")
    try:
        certified_manifest = validate_certified_manifest(payload["certified_manifest"])
    except CertifiedArtifactError as exc:
        raise DatasetSnapshotError(f"certified_manifest inválido: {exc}") from exc
    config = _validated_config(payload["config"])
    created_at = _validated_timestamp(payload["created_at"])
    data_name = payload["data_path"]
    if not isinstance(data_name, str) or not data_name or Path(data_name).name != data_name:
        raise DatasetSnapshotError("data_path debe ser un nombre local seguro")
    data_path = (root / data_name).resolve()
    try:
        data_path.relative_to(root)
    except ValueError as exc:
        raise DatasetSnapshotError("data_path escapa del snapshot") from exc
    if not data_path.is_file() and not data_path.is_dir():
        raise DatasetSnapshotError(f"contenido del snapshot inexistente: {data_path}")
    schema = _schema_from_mapping(payload["schema"])
    if schema.schema_hash != schema_hash:
        raise DatasetSnapshotError("schema_hash no coincide con schema")
    snapshot_id = payload["snapshot_id"]
    if not isinstance(snapshot_id, str) or not _HEX_SHA256.fullmatch(snapshot_id):
        raise DatasetSnapshotError("snapshot_id debe ser SHA-256 hexadecimal")
    if (
        certified_manifest.experiment_id != payload["experiment_id"]
        or certified_manifest.dataset_hash.lower() != dataset_hash
        or certified_manifest.code_commit.lower() != source_commit
        or _workspace_artifact_reference_missing(certified_manifest, payload["source_path"])
    ):
        raise DatasetSnapshotError("certified_manifest no coincide con el lineage del snapshot")
    return DatasetSnapshot(
        snapshot_id=snapshot_id,
        snapshot_path=root,
        data_path=data_path,
        metadata_path=metadata_path,
        source_path=_non_empty(payload["source_path"], "source_path"),
        dataset_hash=dataset_hash,
        schema_hash=schema_hash,
        schema=schema,
        row_count=payload["row_count"],
        experiment_id=_non_empty(payload["experiment_id"], "experiment_id"),
        source_code_commit=source_commit,
        consumer_code_commit=consumer_commit,
        certified_manifest=certified_manifest,
        config=config,
        created_at=created_at,
    )


def hash_dataset(path: str | Path) -> str:
    """Calcula SHA-256 determinista de un archivo o árbol de archivos."""

    target = Path(path)
    if target.is_file():
        return _sha256_file(target)
    if target.is_dir():
        digest = hashlib.sha256()
        for child in sorted((p for p in target.rglob("*") if p.is_file()), key=lambda p: p.relative_to(target).as_posix()):
            relative = child.relative_to(target).as_posix().encode("utf-8")
            child_hash = _sha256_file(child).encode("ascii")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(child_hash)
        return digest.hexdigest()
    raise DatasetSnapshotError(f"path no existe: {path}")


def detect_schema_change(
    current: DatasetSchema | Mapping[str, Any] | str,
    expected: DatasetSchema | Mapping[str, Any] | str,
) -> bool:
    """Compara dos esquemas por su fingerprint, sin modificar ninguno."""

    return _schema_hash_from_expected(current) != _schema_hash_from_expected(expected)


def _read_rows_and_schema(path: Path) -> tuple[tuple[dict[str, Any], ...], DatasetSchema]:
    suffix = path.suffix.lower()
    if path.is_dir():
        raise DatasetSnapshotError("los snapshots de directorio requieren un archivo de datos")
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping) and isinstance(payload.get("rows"), list):
            raw_rows = payload["rows"]
        elif isinstance(payload, list):
            raw_rows = payload
        else:
            raise DatasetSnapshotError("JSON dataset debe ser lista de filas u objeto con rows")
        rows = _normalize_rows(raw_rows)
        return rows, _build_schema("json", rows)
    if suffix in {".jsonl", ".ndjson"}:
        rows = _normalize_rows(
            [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        )
        return rows, _build_schema("jsonl", rows)
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            fieldnames = reader.fieldnames
            rows = tuple(dict(row) for row in reader)
        if not fieldnames or any(not isinstance(field, str) or not field for field in fieldnames):
            raise DatasetSnapshotError("CSV dataset debe tener cabecera")
        return rows, _build_schema(
            "tsv" if suffix == ".tsv" else "csv", rows, columns=fieldnames
        )
    raise DatasetSnapshotError(f"formato de dataset no soportado: {suffix or '<sin extensión>'}")


def _normalize_rows(raw_rows: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_rows, list):
        raise DatasetSnapshotError("rows debe ser una lista")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows):
        if not isinstance(row, Mapping):
            raise DatasetSnapshotError(f"fila {index} no es un objeto")
        normalized.append(dict(row))
    return tuple(normalized)


def _build_schema(
    format_name: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    columns: Sequence[str] = (),
) -> DatasetSchema:
    type_map: dict[str, set[str]] = {}
    for column in columns:
        if not isinstance(column, str) or not column:
            raise DatasetSnapshotError("los nombres de columna deben ser texto no vacío")
        type_map.setdefault(column, set())
    for row in rows:
        for column, value in row.items():
            if not isinstance(column, str) or not column:
                raise DatasetSnapshotError("los nombres de columna deben ser texto no vacío")
            type_map.setdefault(column, set()).add(_value_type(value))
    columns = tuple(sorted(type_map))
    types = tuple((column, tuple(sorted(type_map[column]))) for column in columns)
    base = {"format": format_name, "columns": list(columns), "types": dict(types)}
    schema_hash = hashlib.sha256(_canonical_json(base)).hexdigest()
    return DatasetSchema(format_name, columns, types, schema_hash)


def _schema_from_mapping(value: Any) -> DatasetSchema:
    if not isinstance(value, Mapping):
        raise DatasetSnapshotError("schema debe ser objeto")
    format_name = _non_empty(value.get("format"), "schema.format")
    columns_value = value.get("columns")
    types_value = value.get("types")
    if not isinstance(columns_value, list) or not all(isinstance(c, str) for c in columns_value):
        raise DatasetSnapshotError("schema.columns inválido")
    if not isinstance(types_value, Mapping):
        raise DatasetSnapshotError("schema.types inválido")
    columns = tuple(columns_value)
    types = tuple(
        (column, tuple(sorted(types_value.get(column, [])))) for column in columns
    )
    base = {"format": format_name, "columns": list(columns), "types": dict(types)}
    computed = hashlib.sha256(_canonical_json(base)).hexdigest()
    supplied = value.get("schema_hash", computed)
    if supplied != computed:
        raise DatasetSnapshotError("schema.schema_hash no coincide")
    return DatasetSchema(format_name, columns, types, computed)


def _schema_hash_from_expected(expected: DatasetSchema | Mapping[str, Any] | str) -> str:
    if isinstance(expected, DatasetSchema):
        return expected.schema_hash
    if isinstance(expected, str):
        return _validate_hash(expected, "schema_hash")
    return _schema_from_mapping(expected).schema_hash


def _as_manifest(value: CertifiedExperimentManifest | Mapping[str, Any]) -> CertifiedExperimentManifest:
    if isinstance(value, CertifiedExperimentManifest):
        return value
    try:
        return validate_certified_manifest(value)
    except CertifiedArtifactError as exc:
        raise DatasetSnapshotError(f"manifest no certificado: {exc}") from exc


def _manifest_to_dict(manifest: CertifiedExperimentManifest) -> dict[str, Any]:
    return {
        "schema_version": manifest.schema_version,
        "experiment_id": manifest.experiment_id,
        "verdict": manifest.verdict,
        "gate": _json_safe(manifest.gate),
        "dataset_hash": manifest.dataset_hash,
        "code_commit": manifest.code_commit,
        "scope": _json_safe(manifest.scope),
        "metrics": _json_safe(manifest.metrics),
        "artifact_paths": list(manifest.artifact_paths),
        "produced_at": manifest.produced_at,
        "certifier": manifest.certifier,
    }


def _workspace_artifact_reference_missing(
    manifest: CertifiedExperimentManifest,
    source_path: Any,
) -> bool:
    if not isinstance(source_path, str):
        return True
    return source_path.replace("\\", "/") not in {
        path.replace("\\", "/") for path in manifest.artifact_paths
    }


def _assert_manifest_references_source(
    manifest: CertifiedExperimentManifest,
    source: Path,
    workspace_root: Path,
) -> None:
    source_ref = _workspace_relative(source, workspace_root)
    references = {path.replace("\\", "/") for path in manifest.artifact_paths}
    if source_ref not in references:
        raise DatasetSnapshotError(
            "dataset_path debe estar listado en artifact_paths del manifest"
        )


def _workspace_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise DatasetSnapshotError("path fuera de workspace_root") from exc


def _assert_writable_snapshot_destination(destination: Path, workspace_root: Path) -> None:
    try:
        relative = destination.relative_to(workspace_root)
    except ValueError:
        relative = destination
    parts = tuple(part.lower() for part in relative.parts)
    if any(parts[: len(prefix)] == prefix for prefix in _PROTECTED_PREFIXES):
        raise DatasetSnapshotError("output_dir está protegido por la frontera Hermes")
    if any(part in _PROTECTED_PARTS for part in parts):
        raise DatasetSnapshotError("output_dir está dentro de una ruta protegida")


def _copy_read_only_source(source: Path, destination: Path) -> None:
    if source.is_file():
        shutil.copyfile(source, destination)
        return
    raise DatasetSnapshotError("solo se admiten archivos de dataset como snapshot")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "array"
    return type(value).__name__


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise DatasetSnapshotError("config debe ser JSON serializable") from exc
    return value


def _validated_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(config, Mapping) or not config:
        raise DatasetSnapshotError("config debe ser un objeto no vacío")
    return dict(_json_safe(dict(config)))


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_SHA256.fullmatch(value):
        raise DatasetSnapshotError(f"{field} debe ser SHA-256 hexadecimal")
    return value.lower()


def _validate_commit(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_COMMIT.fullmatch(value):
        raise DatasetSnapshotError(f"{field} debe ser hash Git hexadecimal")
    return value.lower()


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetSnapshotError(f"{field} debe ser texto no vacío")
    return value.strip()


def _validated_timestamp(value: Any) -> str:
    text = _non_empty(value, "created_at")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetSnapshotError("created_at debe ser ISO-8601") from exc
    return text


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


__all__ = [
    "DATASET_SNAPSHOT_SCHEMA_VERSION",
    "CertifiedDatasetReader",
    "DatasetSchema",
    "DatasetSchemaChangedError",
    "DatasetSnapshot",
    "DatasetSnapshotError",
    "detect_schema_change",
    "hash_dataset",
    "load_dataset_snapshot",
]
