"""Contrato seguro y reproducible del pipeline de entrenamiento INF-4.

Este módulo no entrena modelos. Materializa el contrato que un entrenador
futuro deberá respetar: consume únicamente un :class:`DatasetSnapshot`
certificado, separa los datos por tiempo, limita la selección a TRAIN y
VALIDATION, y guarda un estado JSON reanudable en :class:`CheckpointStore`.

No importa ``runtime.ai_learning.__init__`` para mantener este archivo
utilizable sin modificar la API pública existente de INF-0..INF-3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .checkpoint_store import (
    Checkpoint,
    CheckpointIntegrityError,
    CheckpointStore,
    CheckpointStoreError,
)
from .dataset_snapshots import (
    CertifiedDatasetReader,
    DatasetSnapshot,
    DatasetSnapshotError,
    load_dataset_snapshot,
)
from .model_registry import (
    ModelCompatibilityError,
    ModelLineageError,
    ModelRecord,
    ModelRegistry,
    ModelRegistryError,
    validate_model_dataset_compatibility,
)


TRAINING_PIPELINE_SCHEMA_VERSION = "1.0"


class TrainingPipelineError(ValueError):
    """Error de contrato, datos o persistencia del pipeline INF-4."""


class DatasetCertificationError(TrainingPipelineError):
    """El dataset no tiene un snapshot certificado e íntegro."""


class TemporalSplitError(TrainingPipelineError):
    """No se puede construir una partición temporal sin ambigüedad."""


class TrainingRegistryError(TrainingPipelineError):
    """El modelo registrado no coincide con el contrato de entrenamiento."""


class TrainingResumeError(TrainingPipelineError):
    """El checkpoint no pertenece exactamente a este contrato."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _json_value(value: Any, field: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise TrainingPipelineError(f"{field} debe ser JSON serializable") from exc


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrainingPipelineError(f"{field} debe ser texto no vacío")
    return value.strip()


def _names(value: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise TrainingPipelineError(f"{field} debe ser una secuencia no vacía")
    result = tuple(_non_empty_text(item, field) for item in value)
    if len(set(result)) != len(result):
        raise TrainingPipelineError(f"{field} no puede contener duplicados")
    return result


def _seed(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TrainingPipelineError("seed debe ser entero")
    return value


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TemporalSplitError(f"{field} debe ser numérico")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 < normalized < 1.0:
        raise TemporalSplitError(f"{field} debe estar entre 0 y 1")
    return normalized


def _time_key(value: Any, field: str) -> tuple[int, float | str]:
    """Normaliza fechas ISO-8601 y timestamps numéricos para orden temporal."""

    if isinstance(value, bool):
        raise TemporalSplitError(f"{field} no puede ser booleano")
    if isinstance(value, (int, float)):
        normalized = float(value)
        if not math.isfinite(normalized):
            raise TemporalSplitError(f"{field} debe ser finito")
        return (0, normalized)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TemporalSplitError(
                f"{field} debe ser timestamp numérico o ISO-8601"
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (1, parsed.astimezone(timezone.utc).timestamp())
    raise TemporalSplitError(f"{field} no puede estar vacío")


@dataclass(frozen=True)
class TemporalSplit:
    """Partición temporal inmutable para selección y evaluación."""

    train: tuple[Mapping[str, Any], ...]
    validation: tuple[Mapping[str, Any], ...]
    test: tuple[Mapping[str, Any], ...]
    time_column: str
    train_end: Any
    validation_end: Any

    @property
    def selection(self) -> tuple[Mapping[str, Any], ...]:
        """Datos permitidos para seleccionar parámetros (TRAIN + VALIDATION)."""

        return self.train + self.validation

    @property
    def oos_test(self) -> tuple[Mapping[str, Any], ...]:
        """Datos reservados para evaluación final fuera de muestra."""

        return self.test

    @property
    def train_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.train

    @property
    def validation_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.validation

    @property
    def test_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.test

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_column": self.time_column,
            "train_rows": len(self.train),
            "validation_rows": len(self.validation),
            "test_rows": len(self.test),
            "selection_rows": len(self.selection),
            "oos_test_rows": len(self.oos_test),
            "train_end": self.train_end,
            "validation_end": self.validation_end,
            "selection_scope": "train+validation",
            "oos_scope": "test",
        }


@dataclass(frozen=True)
class TrainingPlan:
    """Plan reproducible; contiene contrato y no contiene pesos de modelo."""

    pipeline_schema_version: str
    run_id: str
    snapshot_id: str
    dataset_hash: str
    schema_hash: str
    model_id: str
    model_version: str
    features: tuple[str, ...]
    labels: tuple[str, ...]
    seed: int
    config: Mapping[str, Any]
    split: TemporalSplit
    metrics: Mapping[str, Any]

    @property
    def selection_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.split.selection

    @property
    def oos_test_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.split.oos_test

    def state(self) -> dict[str, Any]:
        return {
            "pipeline_schema_version": self.pipeline_schema_version,
            "run_id": self.run_id,
            "snapshot_id": self.snapshot_id,
            "dataset_hash": self.dataset_hash,
            "schema_hash": self.schema_hash,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "features": list(self.features),
            "labels": list(self.labels),
            "seed": self.seed,
            "config": _json_value(self.config, "config"),
            "split": self.split.to_dict(),
            "metrics": _json_value(self.metrics, "metrics"),
            "model_training": {"executed": False, "kind": "contract-skeleton"},
        }


@dataclass(frozen=True)
class TrainingResult:
    """Resultado del skeleton y checkpoint validado."""

    plan: TrainingPlan
    checkpoint: Checkpoint
    resumed: bool

    @property
    def metrics(self) -> Mapping[str, Any]:
        return self.plan.metrics

    @property
    def split(self) -> TemporalSplit:
        return self.plan.split

    @property
    def selection_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.plan.selection_rows

    @property
    def oos_test_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.plan.oos_test_rows

    @property
    def run_id(self) -> str:
        return self.plan.run_id


def _certified_snapshot(
    snapshot: DatasetSnapshot | str | Path | Mapping[str, Any],
) -> tuple[DatasetSnapshot, tuple[dict[str, Any], ...]]:
    """Recarga, valida y rehashea siempre el snapshot antes de consumirlo."""

    if isinstance(snapshot, DatasetSnapshot):
        root = snapshot.snapshot_path
    elif isinstance(snapshot, (str, Path)):
        root = snapshot
    elif isinstance(snapshot, Mapping):
        raw_path = snapshot.get("snapshot_path")
        if not isinstance(raw_path, (str, Path)):
            raise DatasetCertificationError(
                "se requiere la ruta del snapshot para validar su contenido"
            )
        root = raw_path
    else:
        raise DatasetCertificationError("snapshot certificado requerido")

    try:
        loaded = load_dataset_snapshot(root)
        reader = CertifiedDatasetReader(loaded.snapshot_path.parent)
        rows = reader.read_snapshot(loaded.snapshot_path)
    except (DatasetSnapshotError, OSError) as exc:
        raise DatasetCertificationError(f"snapshot no certificado o íntegro: {exc}") from exc

    if loaded.certified_manifest.verdict != "PASS":
        raise DatasetCertificationError("solo se aceptan manifests certificados PASS")
    if isinstance(snapshot, DatasetSnapshot) and snapshot.snapshot_id != loaded.snapshot_id:
        raise DatasetCertificationError("snapshot object y metadata no coinciden")
    return loaded, rows


def _build_split(
    rows: Sequence[Mapping[str, Any]],
    *,
    time_column: str,
    train_fraction: float,
    validation_fraction: float,
) -> TemporalSplit:
    if len(rows) < 3:
        raise TemporalSplitError("se requieren al menos 3 filas para train/validation/test")
    indexed: list[tuple[tuple[int, float | str], str, dict[str, Any]]] = []
    key_kinds: set[int] = set()
    for row in rows:
        if time_column not in row:
            raise TemporalSplitError(f"falta la columna temporal: {time_column}")
        key = _time_key(row[time_column], f"{time_column} de la fila")
        key_kinds.add(key[0])
        normalized = dict(row)
        indexed.append((key, _canonical_json(normalized).decode("utf-8"), normalized))
    if len(key_kinds) != 1:
        raise TemporalSplitError("la columna temporal mezcla timestamps numéricos e ISO-8601")
    indexed.sort(key=lambda item: (item[0], item[1]))

    train_count = max(1, int(math.floor(len(indexed) * train_fraction)))
    validation_count = max(1, int(math.floor(len(indexed) * validation_fraction)))
    test_count = len(indexed) - train_count - validation_count
    if test_count < 1:
        raise TemporalSplitError("las proporciones deben dejar al menos una fila OOS")

    train_items = indexed[:train_count]
    validation_items = indexed[train_count : train_count + validation_count]
    test_items = indexed[train_count + validation_count :]
    if not train_items or not validation_items or not test_items:
        raise TemporalSplitError("cada partición temporal debe tener filas")
    if train_items[-1][0] >= validation_items[0][0] or validation_items[-1][0] >= test_items[0][0]:
        raise TemporalSplitError(
            "una frontera temporal divide timestamps iguales; se rechaza para evitar leakage"
        )

    return TemporalSplit(
        train=tuple(item[2] for item in train_items),
        validation=tuple(item[2] for item in validation_items),
        test=tuple(item[2] for item in test_items),
        time_column=time_column,
        train_end=train_items[-1][2][time_column],
        validation_end=validation_items[-1][2][time_column],
    )


def _validate_registered_model(
    registry: ModelRegistry,
    snapshot: DatasetSnapshot,
    *,
    model_id: str,
    model_version: str,
    features: tuple[str, ...],
    labels: tuple[str, ...],
    seed: int,
    config: Mapping[str, Any],
) -> ModelRecord:
    try:
        record = registry.get_model(model_id, model_version)
        validate_model_dataset_compatibility(
            snapshot, features=features, labels=labels
        )
    except (ModelRegistryError, ModelCompatibilityError) as exc:
        raise TrainingRegistryError(f"modelo no es compatible: {exc}") from exc
    expected = {
        "snapshot_id": snapshot.snapshot_id,
        "dataset_hash": snapshot.dataset_hash,
        "schema_hash": snapshot.schema_hash,
        "features": features,
        "labels": labels,
        "seed": seed,
        "config": _json_value(config, "config"),
    }
    actual = {
        "snapshot_id": record.snapshot_id,
        "dataset_hash": record.dataset_hash,
        "schema_hash": record.schema_hash,
        "features": record.features,
        "labels": record.labels,
        "seed": record.seed,
        "config": _json_value(record.config, "registry.config"),
    }
    if actual != expected:
        mismatches = [field for field in expected if actual[field] != expected[field]]
        raise TrainingRegistryError(
            "registro incompatible en: " + ", ".join(mismatches)
        )
    return record


class TrainingPipeline:
    """Construye y persiste un plan INF-4 sin ejecutar entrenamiento real."""

    def __init__(
        self,
        *,
        snapshot: DatasetSnapshot | str | Path | Mapping[str, Any],
        registry: ModelRegistry,
        checkpoint_store: CheckpointStore,
        model_id: str,
        model_version: str,
        features: Sequence[str],
        labels: Sequence[str],
        seed: int,
        config: Mapping[str, Any],
        time_column: str = "timestamp",
        train_fraction: float = 0.6,
        validation_fraction: float = 0.2,
    ):
        self.snapshot_input = snapshot
        self.registry = registry
        self.checkpoint_store = checkpoint_store
        self.model_id = _non_empty_text(model_id, "model_id")
        self.model_version = _non_empty_text(model_version, "model_version")
        self.features = _names(features, "features")
        self.labels = _names(labels, "labels")
        if set(self.features).intersection(self.labels):
            raise TrainingPipelineError("features y labels se solapan")
        self.seed = _seed(seed)
        self.config = _json_value(config, "config")
        if not isinstance(self.config, Mapping):
            raise TrainingPipelineError("config debe ser un objeto")
        self.time_column = _non_empty_text(time_column, "time_column")
        self.train_fraction = _ratio(train_fraction, "train_fraction")
        self.validation_fraction = _ratio(validation_fraction, "validation_fraction")
        if self.train_fraction + self.validation_fraction >= 1.0:
            raise TemporalSplitError("train_fraction + validation_fraction debe ser menor que 1")

    def plan(self) -> TrainingPlan:
        snapshot, rows = _certified_snapshot(self.snapshot_input)
        _validate_registered_model(
            self.registry,
            snapshot,
            model_id=self.model_id,
            model_version=self.model_version,
            features=self.features,
            labels=self.labels,
            seed=self.seed,
            config=self.config,
        )
        split = _build_split(
            rows,
            time_column=self.time_column,
            train_fraction=self.train_fraction,
            validation_fraction=self.validation_fraction,
        )
        data_digest = hashlib.sha256(_canonical_json(rows)).hexdigest()
        metrics = {
            "pipeline_schema_version": TRAINING_PIPELINE_SCHEMA_VERSION,
            "train_rows": len(split.train),
            "validation_rows": len(split.validation),
            "test_rows": len(split.test),
            "selection_rows": len(split.selection),
            "oos_test_rows": len(split.oos_test),
            "selection_scope": "train+validation",
            "oos_scope": "test",
            "data_digest": data_digest,
            "model_training_executed": False,
        }
        identity = {
            "pipeline_schema_version": TRAINING_PIPELINE_SCHEMA_VERSION,
            "snapshot_id": snapshot.snapshot_id,
            "dataset_hash": snapshot.dataset_hash,
            "schema_hash": snapshot.schema_hash,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "features": list(self.features),
            "labels": list(self.labels),
            "seed": self.seed,
            "config": self.config,
            "time_column": self.time_column,
            "train_fraction": self.train_fraction,
            "validation_fraction": self.validation_fraction,
            "data_digest": data_digest,
        }
        run_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
        return TrainingPlan(
            pipeline_schema_version=TRAINING_PIPELINE_SCHEMA_VERSION,
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            dataset_hash=snapshot.dataset_hash,
            schema_hash=snapshot.schema_hash,
            model_id=self.model_id,
            model_version=self.model_version,
            features=self.features,
            labels=self.labels,
            seed=self.seed,
            config=self.config,
            split=split,
            metrics=metrics,
        )

    def run(
        self,
        *,
        resume_from: str | None = None,
        checkpoint_id: str | None = None,
    ) -> TrainingResult:
        plan = self.plan()
        expected_state = plan.state()
        identifier = resume_from or checkpoint_id or f"{self.model_id}-{self.model_version}-{plan.run_id[:16]}"
        if resume_from is not None:
            checkpoint = self._load_and_validate_checkpoint(resume_from, expected_state)
            return TrainingResult(plan=plan, checkpoint=checkpoint, resumed=True)
        try:
            checkpoint = self.checkpoint_store.load(identifier)
        except CheckpointIntegrityError as exc:
            raise TrainingResumeError(
                f"checkpoint existente no es íntegro: {exc}"
            ) from exc
        except CheckpointStoreError:
            checkpoint = self.checkpoint_store.save(
                expected_state,
                model_id=self.model_id,
                model_version=self.model_version,
                dataset_hash=plan.dataset_hash,
                features=plan.features,
                labels=plan.labels,
                seed=plan.seed,
                checkpoint_id=identifier,
            )
            return TrainingResult(plan=plan, checkpoint=checkpoint, resumed=False)
        checkpoint = self._validate_checkpoint(checkpoint, expected_state)
        return TrainingResult(plan=plan, checkpoint=checkpoint, resumed=True)

    @staticmethod
    def _validate_checkpoint(checkpoint: Checkpoint, expected_state: Mapping[str, Any]) -> Checkpoint:
        if dict(checkpoint.state) != dict(expected_state):
            raise TrainingResumeError("checkpoint no coincide con el contrato reproducible")
        return checkpoint

    def _load_and_validate_checkpoint(
        self, checkpoint_id: str, expected_state: Mapping[str, Any]
    ) -> Checkpoint:
        try:
            checkpoint = self.checkpoint_store.load(checkpoint_id)
        except CheckpointStoreError as exc:
            raise TrainingResumeError(f"no se puede reanudar checkpoint: {exc}") from exc
        return self._validate_checkpoint(checkpoint, expected_state)


def create_training_plan(**kwargs: Any) -> TrainingPlan:
    """Atajo de contrato para consumidores que aún no desean persistir estado."""

    return TrainingPipeline(**kwargs).plan()


def run_training_pipeline(**kwargs: Any) -> TrainingResult:
    """Atajo de contrato para ejecutar únicamente el skeleton INF-4."""

    return TrainingPipeline(**kwargs).run()


__all__ = [
    "TRAINING_PIPELINE_SCHEMA_VERSION",
    "DatasetCertificationError",
    "TemporalSplit",
    "TemporalSplitError",
    "TrainingPipeline",
    "TrainingPipelineError",
    "TrainingPlan",
    "TrainingRegistryError",
    "TrainingResumeError",
    "TrainingResult",
    "create_training_plan",
    "run_training_pipeline",
]
