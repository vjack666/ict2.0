"""Contrato puro de fusión de scores para INF-5.

El módulo define una interfaz común para fuentes ICT y Wyckoff, aprende una
combinación convexa únicamente con observaciones ``TRAIN`` y evalúa fuera de
muestra sin ajustar ningún parámetro. No lee ni escribe artefactos Hermes y
no ejecuta experimentos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence, runtime_checkable


SCORE_FUSION_SCHEMA_VERSION = "1.0"
TRAIN_SPLIT = "TRAIN"
OOS_SPLITS = frozenset({"VALIDATION", "TEST", "OOS", "OUT_OF_SAMPLE"})
_SCORE_NAMES = ("ICT", "WYCKOFF")


class ScoreFusionError(ValueError):
    """Error general del contrato de score fusion."""


class ScoreCompatibilityError(ScoreFusionError):
    """Features, labels o lineage incompatibles."""


class WeightValidationError(ScoreFusionError):
    """Pesos ausentes, no finitos, no registrados o incompatibles."""


class TrainingDataError(ScoreFusionError):
    """TRAIN no permite aprender pesos de forma determinista."""


class OOSContractError(ScoreFusionError):
    """La evaluación offline no cumple el contrato OOS."""


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoreFusionError(f"{field} debe ser numérico")
    result = float(value)
    if not math.isfinite(result):
        raise ScoreFusionError(f"{field} debe ser finito")
    return result


def _names(value: Sequence[str] | None, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise ScoreCompatibilityError(f"{field} debe ser una secuencia de nombres")
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ScoreCompatibilityError(f"{field} contiene nombres inválidos")
    if len(set(result)) != len(result):
        raise ScoreCompatibilityError(f"{field} contiene nombres duplicados")
    return result


def _optional_hash(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 64:
        raise ScoreCompatibilityError(f"{field} debe ser SHA-256 o None")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ScoreCompatibilityError(f"{field} debe ser SHA-256 o None") from exc
    return value.lower()


@runtime_checkable
class ScoreSource(Protocol):
    """Interfaz común que deben implementar ICT y Wyckoff."""

    name: str

    def score(self, features: Mapping[str, Any]) -> float:
        """Produce un score finito para las mismas features de entrada."""


@dataclass(frozen=True)
class CallableScoreSource:
    """Adaptador pequeño para una fuente ICT o Wyckoff pura."""

    name: str
    scorer: Callable[[Mapping[str, Any]], float]

    def __post_init__(self) -> None:
        if self.name.upper() not in _SCORE_NAMES:
            raise ScoreFusionError("name debe ser ICT o WYCKOFF")
        if not callable(self.scorer):
            raise ScoreFusionError("scorer debe ser invocable")

    def score(self, features: Mapping[str, Any]) -> float:
        return _finite_number(self.scorer(features), f"score {self.name}")


@dataclass(frozen=True)
class ScorePair:
    """Par de scores con semántica común para ICT y Wyckoff."""

    ict: float
    wyckoff: float

    def __post_init__(self) -> None:
        _finite_number(self.ict, "ict")
        _finite_number(self.wyckoff, "wyckoff")

    def to_dict(self) -> dict[str, float]:
        return {"ict": float(self.ict), "wyckoff": float(self.wyckoff)}


def score_pair(
    features: Mapping[str, Any],
    *,
    ict: ScoreSource,
    wyckoff: ScoreSource,
) -> ScorePair:
    """Obtiene ICT y Wyckoff a través de la misma interfaz, sin persistencia."""

    if not isinstance(features, Mapping):
        raise ScoreFusionError("features debe ser un mapping")
    if not isinstance(ict, ScoreSource) or not isinstance(wyckoff, ScoreSource):
        raise ScoreFusionError("ict y wyckoff deben implementar ScoreSource")
    if ict.name.upper() != "ICT" or wyckoff.name.upper() != "WYCKOFF":
        raise ScoreFusionError("las fuentes deben identificarse como ICT y WYCKOFF")
    return ScorePair(ict.score(features), wyckoff.score(features))


@dataclass(frozen=True)
class ScoreObservation:
    """Una observación ya puntuada y etiquetada, sin efectos secundarios."""

    sample_id: str
    split: str
    ict_score: float
    wyckoff_score: float
    label: float
    features: Mapping[str, Any] = field(default_factory=dict)
    feature_names: tuple[str, ...] = ()
    label_name: str = "label"
    snapshot_id: str | None = None
    dataset_hash: str | None = None
    schema_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id.strip():
            raise ScoreFusionError("sample_id debe ser texto no vacío")
        split = self.split.upper() if isinstance(self.split, str) else ""
        if split not in {TRAIN_SPLIT, *OOS_SPLITS}:
            raise ScoreFusionError(f"split no soportado: {self.split!r}")
        object.__setattr__(self, "split", split)
        _finite_number(self.ict_score, "ict_score")
        _finite_number(self.wyckoff_score, "wyckoff_score")
        _finite_number(self.label, "label")
        if not isinstance(self.features, Mapping):
            raise ScoreCompatibilityError("features debe ser un mapping")
        normalized_features = _names(self.feature_names, "feature_names")
        actual_features = tuple(self.features.keys())
        if normalized_features and normalized_features != actual_features:
            raise ScoreCompatibilityError("feature_names no coincide con el orden de features")
        if not normalized_features:
            object.__setattr__(self, "feature_names", actual_features)
        if not isinstance(self.label_name, str) or not self.label_name.strip():
            raise ScoreCompatibilityError("label_name debe ser texto no vacío")
        object.__setattr__(self, "snapshot_id", _optional_hash(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "dataset_hash", _optional_hash(self.dataset_hash, "dataset_hash"))
        object.__setattr__(self, "schema_hash", _optional_hash(self.schema_hash, "schema_hash"))


@dataclass(frozen=True)
class ScoreDataset:
    """Colección con contrato de features, labels y lineage opcional."""

    rows: tuple[ScoreObservation, ...]
    features: tuple[str, ...] = ()
    labels: tuple[str, ...] = ("label",)
    snapshot_id: str | None = None
    dataset_hash: str | None = None
    schema_hash: str | None = None

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        if not rows:
            raise ScoreFusionError("dataset vacío")
        if any(not isinstance(row, ScoreObservation) for row in rows):
            raise ScoreFusionError("rows debe contener ScoreObservation")
        object.__setattr__(self, "rows", rows)
        feature_names = _names(self.features, "features")
        if not feature_names:
            feature_names = rows[0].feature_names
        label_names = _names(self.labels, "labels")
        if not label_names:
            raise ScoreCompatibilityError("labels no puede estar vacío")
        object.__setattr__(self, "features", feature_names)
        object.__setattr__(self, "labels", label_names)
        object.__setattr__(self, "snapshot_id", _optional_hash(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "dataset_hash", _optional_hash(self.dataset_hash, "dataset_hash"))
        object.__setattr__(self, "schema_hash", _optional_hash(self.schema_hash, "schema_hash"))
        validate_feature_label_compatibility(
            rows, features=feature_names, labels=label_names
        )


def validate_feature_label_compatibility(
    rows: Iterable[ScoreObservation] | ScoreDataset,
    *,
    features: Sequence[str],
    labels: Sequence[str],
) -> None:
    """Exige igualdad exacta de nombres y orden de features/labels."""

    expected_features = _names(features, "features")
    expected_labels = _names(labels, "labels")
    if not expected_labels:
        raise ScoreCompatibilityError("labels no puede estar vacío")
    observations = rows.rows if isinstance(rows, ScoreDataset) else tuple(rows)
    for row in observations:
        if tuple(row.feature_names) != expected_features:
            raise ScoreCompatibilityError(
                f"features incompatibles en {row.sample_id}: "
                f"esperadas {expected_features}, recibidas {row.feature_names}"
            )
        if (row.label_name,) != expected_labels:
            raise ScoreCompatibilityError(
                f"labels incompatibles en {row.sample_id}: "
                f"esperadas {expected_labels}, recibidas {(row.label_name,)}"
            )


def _resolve_rows(
    data: ScoreDataset | Iterable[ScoreObservation],
    *,
    features: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> tuple[tuple[ScoreObservation, ...], tuple[str, ...], tuple[str, ...], str | None, str | None, str | None]:
    if isinstance(data, ScoreDataset):
        rows = data.rows
        actual_features, actual_labels = data.features, data.labels
        lineage = (data.snapshot_id, data.dataset_hash, data.schema_hash)
    else:
        rows = tuple(data)
        if not rows:
            raise ScoreFusionError("dataset vacío")
        if any(not isinstance(row, ScoreObservation) for row in rows):
            raise ScoreFusionError("data debe contener ScoreObservation")
        actual_features, actual_labels = rows[0].feature_names, (rows[0].label_name,)
        lineage = (None, None, None)
    expected_features = _names(features, "features") if features is not None else actual_features
    expected_labels = _names(labels, "labels") if labels is not None else actual_labels
    validate_feature_label_compatibility(
        rows, features=expected_features, labels=expected_labels
    )
    if isinstance(data, ScoreDataset):
        if expected_features != data.features or expected_labels != data.labels:
            raise ScoreCompatibilityError("contrato solicitado no coincide con ScoreDataset")
    return rows, expected_features, expected_labels, *lineage


def _validate_lineage_match(
    expected: tuple[str | None, str | None, str | None],
    actual: tuple[str | None, str | None, str | None],
) -> None:
    for field, left, right in zip(("snapshot_id", "dataset_hash", "schema_hash"), expected, actual):
        if left is not None and right is not None and left != right:
            raise ScoreCompatibilityError(f"{field} incompatible")


@dataclass(frozen=True)
class ScoreFusionWeights:
    """Pesos registrados; su procedencia TRAIN forma parte del contrato."""

    weight_ict: float
    weight_wyckoff: float
    trained_on_split: str
    train_sample_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    label_names: tuple[str, ...]
    train_snapshot_id: str | None = None
    train_dataset_hash: str | None = None
    train_schema_hash: str | None = None
    method: str = "least_squares_simplex_2"

    def __post_init__(self) -> None:
        ict = _finite_number(self.weight_ict, "weight_ict")
        wyckoff = _finite_number(self.weight_wyckoff, "weight_wyckoff")
        if ict < 0.0 or wyckoff < 0.0 or not math.isclose(ict + wyckoff, 1.0, abs_tol=1e-12):
            raise WeightValidationError("los pesos deben ser no negativos y sumar 1")
        if self.trained_on_split != TRAIN_SPLIT:
            raise WeightValidationError("los pesos deben estar aprendidos únicamente en TRAIN")
        if not self.train_sample_ids or len(set(self.train_sample_ids)) != len(self.train_sample_ids):
            raise WeightValidationError("train_sample_ids debe ser único y no vacío")
        object.__setattr__(self, "feature_names", _names(self.feature_names, "feature_names"))
        object.__setattr__(self, "label_names", _names(self.label_names, "label_names"))
        if not self.label_names:
            raise WeightValidationError("label_names no puede estar vacío")
        object.__setattr__(self, "train_snapshot_id", _optional_hash(self.train_snapshot_id, "train_snapshot_id"))
        object.__setattr__(self, "train_dataset_hash", _optional_hash(self.train_dataset_hash, "train_dataset_hash"))
        object.__setattr__(self, "train_schema_hash", _optional_hash(self.train_schema_hash, "train_schema_hash"))
        if self.method != "least_squares_simplex_2":
            raise WeightValidationError("method de pesos no soportado")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCORE_FUSION_SCHEMA_VERSION,
            "weight_ict": float(self.weight_ict),
            "weight_wyckoff": float(self.weight_wyckoff),
            "trained_on_split": self.trained_on_split,
            "train_sample_ids": list(self.train_sample_ids),
            "feature_names": list(self.feature_names),
            "label_names": list(self.label_names),
            "train_snapshot_id": self.train_snapshot_id,
            "train_dataset_hash": self.train_dataset_hash,
            "train_schema_hash": self.train_schema_hash,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ScoreFusionWeights":
        if not isinstance(payload, Mapping) or payload.get("schema_version") != SCORE_FUSION_SCHEMA_VERSION:
            raise WeightValidationError("schema_version de pesos no soportada")
        required = {
            "weight_ict", "weight_wyckoff", "trained_on_split", "train_sample_ids",
            "feature_names", "label_names", "method",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise WeightValidationError("pesos incompletos; faltan: " + ", ".join(missing))
        ids = payload["train_sample_ids"]
        if isinstance(ids, (str, bytes)) or not isinstance(ids, Sequence):
            raise WeightValidationError("train_sample_ids debe ser una lista")
        return cls(
            weight_ict=payload["weight_ict"],
            weight_wyckoff=payload["weight_wyckoff"],
            trained_on_split=payload["trained_on_split"],
            train_sample_ids=tuple(ids),
            feature_names=tuple(payload["feature_names"]),
            label_names=tuple(payload["label_names"]),
            train_snapshot_id=payload.get("train_snapshot_id"),
            train_dataset_hash=payload.get("train_dataset_hash"),
            train_schema_hash=payload.get("train_schema_hash"),
            method=payload["method"],
        )


def _train_rows(data: ScoreDataset | Iterable[ScoreObservation], **kwargs: Any) -> tuple[tuple[ScoreObservation, ...], tuple[str, ...], tuple[str, ...], tuple[str | None, str | None, str | None]]:
    rows, features, labels, snapshot_id, dataset_hash, schema_hash = _resolve_rows(data, **kwargs)
    train = tuple(row for row in rows if row.split == TRAIN_SPLIT)
    if not train:
        raise TrainingDataError("se requiere al menos una observación TRAIN")
    return train, features, labels, (snapshot_id, dataset_hash, schema_hash)


def learn_score_fusion_weights(
    data: ScoreDataset | Iterable[ScoreObservation],
    *,
    features: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> ScoreFusionWeights:
    """Aprende pesos convexos por mínimos cuadrados usando solo TRAIN.

    Para dos fuentes, la solución de la recta restringida a ``[0, 1]`` es
    cerrada y no necesita hiperparámetros, seeds ni pesos iniciales.
    """

    train, feature_names, label_names, lineage = _train_rows(
        data, features=features, labels=labels
    )
    if len(train) < 2:
        raise TrainingDataError("se requieren al menos dos observaciones TRAIN")
    delta = [row.ict_score - row.wyckoff_score for row in train]
    target = [row.label - row.wyckoff_score for row in train]
    denominator = sum(value * value for value in delta)
    if denominator <= 1e-24:
        raise TrainingDataError("TRAIN no identifica pesos: ICT y Wyckoff son constantes iguales")
    weight_ict = sum(left * right for left, right in zip(delta, target)) / denominator
    weight_ict = min(1.0, max(0.0, weight_ict))
    return ScoreFusionWeights(
        weight_ict=weight_ict,
        weight_wyckoff=1.0 - weight_ict,
        trained_on_split=TRAIN_SPLIT,
        train_sample_ids=tuple(row.sample_id for row in train),
        feature_names=feature_names,
        label_names=label_names,
        train_snapshot_id=lineage[0],
        train_dataset_hash=lineage[1],
        train_schema_hash=lineage[2],
    )


def register_score_fusion_weights(payload: Mapping[str, Any]) -> ScoreFusionWeights:
    """Valida pesos serializados sin aprenderlos ni modificarlos."""

    return ScoreFusionWeights.from_dict(payload)


@dataclass(frozen=True)
class ScoreFusionModel:
    weights: ScoreFusionWeights

    def __post_init__(self) -> None:
        if not isinstance(self.weights, ScoreFusionWeights):
            raise WeightValidationError("weights debe ser ScoreFusionWeights")

    def fuse(self, ict_score: float, wyckoff_score: float) -> float:
        ict = _finite_number(ict_score, "ict_score")
        wyckoff = _finite_number(wyckoff_score, "wyckoff_score")
        return self.weights.weight_ict * ict + self.weights.weight_wyckoff * wyckoff

    def predict(self, row: ScoreObservation) -> float:
        if not isinstance(row, ScoreObservation):
            raise ScoreFusionError("row debe ser ScoreObservation")
        validate_feature_label_compatibility(
            (row,), features=self.weights.feature_names, labels=self.weights.label_names
        )
        _validate_lineage_match(
            (
                self.weights.train_snapshot_id,
                self.weights.train_dataset_hash,
                self.weights.train_schema_hash,
            ),
            (row.snapshot_id, row.dataset_hash, row.schema_hash),
        )
        return self.fuse(row.ict_score, row.wyckoff_score)

    def to_dict(self) -> dict[str, Any]:
        return self.weights.to_dict()


ScoreFusion = ScoreFusionModel


def fit_score_fusion(
    data: ScoreDataset | Iterable[ScoreObservation],
    *,
    features: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> ScoreFusionModel:
    """Aprende y encapsula pesos; no toca el dataset ni persistencia."""

    return ScoreFusionModel(learn_score_fusion_weights(data, features=features, labels=labels))


@dataclass(frozen=True)
class BaselineModel:
    """Baseline separado: media de labels aprendida exclusivamente en TRAIN."""

    value: float
    trained_on_split: str
    train_sample_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    label_names: tuple[str, ...]

    def __post_init__(self) -> None:
        _finite_number(self.value, "baseline value")
        if self.trained_on_split != TRAIN_SPLIT or not self.train_sample_ids:
            raise WeightValidationError("baseline debe estar aprendido en TRAIN")
        if not self.label_names:
            raise ScoreCompatibilityError("baseline requiere labels")

    def predict(self, row: ScoreObservation) -> float:
        validate_feature_label_compatibility(
            (row,), features=self.feature_names, labels=self.label_names
        )
        return self.value


def fit_baseline(
    data: ScoreDataset | Iterable[ScoreObservation],
    *,
    features: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> BaselineModel:
    """Calcula el baseline sin usar ninguna fila OOS."""

    train, feature_names, label_names, _ = _train_rows(
        data, features=features, labels=labels
    )
    return BaselineModel(
        value=sum(row.label for row in train) / len(train),
        trained_on_split=TRAIN_SPLIT,
        train_sample_ids=tuple(row.sample_id for row in train),
        feature_names=feature_names,
        label_names=label_names,
    )


@dataclass(frozen=True)
class OfflineOOSResult:
    """Resultado inmutable de una evaluación offline ya concluida."""

    sample_ids: tuple[str, ...]
    splits: tuple[str, ...]
    labels: tuple[float, ...]
    fused_predictions: tuple[float, ...]
    fused_mae: float
    fused_mse: float
    baseline_predictions: tuple[float, ...] | None = None
    baseline_mae: float | None = None
    baseline_mse: float | None = None


def evaluate_offline_oos(
    model: ScoreFusionModel,
    data: ScoreDataset | Iterable[ScoreObservation],
    *,
    baseline: BaselineModel | None = None,
    features: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> OfflineOOSResult:
    """Evalúa solo filas OOS; no ajusta pesos, baseline ni lineage."""

    if not isinstance(model, ScoreFusionModel):
        raise OOSContractError("model debe ser ScoreFusionModel")
    rows, feature_names, label_names, snapshot_id, dataset_hash, schema_hash = _resolve_rows(
        data, features=features, labels=labels
    )
    if any(row.split == TRAIN_SPLIT for row in rows):
        raise OOSContractError("la evaluación OOS no puede contener filas TRAIN")
    if not all(row.split in OOS_SPLITS for row in rows):
        raise OOSContractError("la evaluación requiere splits OOS explícitos")
    validate_feature_label_compatibility(
        rows, features=model.weights.feature_names, labels=model.weights.label_names
    )
    _validate_lineage_match(
        (snapshot_id, dataset_hash, schema_hash),
        (
            model.weights.train_snapshot_id,
            model.weights.train_dataset_hash,
            model.weights.train_schema_hash,
        ),
    )
    if baseline is not None:
        if baseline.feature_names != feature_names or baseline.label_names != label_names:
            raise ScoreCompatibilityError("baseline incompatible con el dataset OOS")
    fused = tuple(model.predict(row) for row in rows)
    labels_values = tuple(float(row.label) for row in rows)
    fused_errors = tuple(prediction - label for prediction, label in zip(fused, labels_values))
    fused_mae = sum(abs(error) for error in fused_errors) / len(rows)
    fused_mse = sum(error * error for error in fused_errors) / len(rows)
    baseline_predictions: tuple[float, ...] | None = None
    baseline_mae: float | None = None
    baseline_mse: float | None = None
    if baseline is not None:
        baseline_predictions = tuple(baseline.predict(row) for row in rows)
        errors = tuple(prediction - label for prediction, label in zip(baseline_predictions, labels_values))
        baseline_mae = sum(abs(error) for error in errors) / len(rows)
        baseline_mse = sum(error * error for error in errors) / len(rows)
    return OfflineOOSResult(
        sample_ids=tuple(row.sample_id for row in rows),
        splits=tuple(row.split for row in rows),
        labels=labels_values,
        fused_predictions=fused,
        fused_mae=fused_mae,
        fused_mse=fused_mse,
        baseline_predictions=baseline_predictions,
        baseline_mae=baseline_mae,
        baseline_mse=baseline_mse,
    )


__all__ = [
    "SCORE_FUSION_SCHEMA_VERSION",
    "TRAIN_SPLIT",
    "OOS_SPLITS",
    "ScoreFusionError",
    "ScoreCompatibilityError",
    "WeightValidationError",
    "TrainingDataError",
    "OOSContractError",
    "ScoreSource",
    "CallableScoreSource",
    "ScorePair",
    "score_pair",
    "ScoreObservation",
    "ScoreDataset",
    "validate_feature_label_compatibility",
    "ScoreFusionWeights",
    "learn_score_fusion_weights",
    "register_score_fusion_weights",
    "ScoreFusionModel",
    "ScoreFusion",
    "fit_score_fusion",
    "BaselineModel",
    "fit_baseline",
    "OfflineOOSResult",
    "evaluate_offline_oos",
]
