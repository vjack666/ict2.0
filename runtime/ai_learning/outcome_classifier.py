"""Clasificador supervisado de outcomes para la primera IA de ICT.

La implementación es un baseline multinomial determinista (softmax) que
consume el contrato ``TrainingPipeline`` y no conoce órdenes ni PnL. Solo puede
entrenar cuando el llamador presenta una autorización científica explícita:
``status=PASS`` y ``verdict=TRAINING_ELIGIBLE``. La predicción siempre sale en
Shadow Mode y pasa por la política de abstención INF-7.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .abstention import evaluate_abstention
from .training_pipeline import TrainingPipeline


OUTCOME_CLASSIFIER_SCHEMA_VERSION = "1.0"
OUTCOME_CLASSES = ("continuation", "reversal", "failure")
FEATURE_NAMES = (
    "direction",
    "sequence_depth",
    "context_bucket=ALIGNED",
    "context_bucket=NEUTRAL",
    "context_bucket=AGAINST",
    "h1_alignment=ALIGNED",
    "h1_alignment=NEUTRAL",
    "h1_alignment=AGAINST",
    "d1_bias=BULLISH",
    "d1_bias=BEARISH",
    "d1_bias=UNKNOWN",
    "d1_bias=MIXED",
    "h4_location=DISCOUNT",
    "h4_location=PREMIUM",
    "h4_location=EQUILIBRIUM",
    "h4_location=MID",
    "h4_location=UNKNOWN",
    "sequence_has=LIQUIDITY_POOL",
    "sequence_has=SWEEP",
    "sequence_has=DISPLACEMENT",
    "sequence_has=STRUCTURE",
    "sequence_has=OB",
    "sequence_has=FVG",
    "sequence_has=CONFLUENCE",
)
INTRADAY_PHASES = (
    "ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN",
    "RANGE_UNCLASSIFIED", "TRANSITION", "UNKNOWN",
)
INTRADAY_EVENTS = (
    "SPRING", "UPTHRUST", "UTAD", "SOS", "SOW", "LPS", "LPSY",
    "TEST", "FAILED_TEST", "RANGE_BREAK", "EFFORT_RESULT_DIVERGENCE",
)
# Same deterministic softmax trainer, with an explicit causal feature profile
# for the Wyckoff H1 -> M15 research line.  The original ICT profile remains
# byte-for-byte compatible for existing artifacts.
INTRADAY_FEATURE_NAMES = (
    "direction", "sequence_depth",
    "ict_m15_bos_bullish", "ict_m15_bos_bearish",
    "ict_m15_choch_bullish", "ict_m15_choch_bearish",
    "ict_m15_displacement_bullish", "ict_m15_displacement_bearish",
    "ict_m15_fvg_bullish", "ict_m15_fvg_bearish",
    "ict_m15_sweep_up", "ict_m15_sweep_down",
    *(f"wyckoff_h1_phase={value}" for value in INTRADAY_PHASES),
    *(f"wyckoff_m15_phase={value}" for value in INTRADAY_PHASES),
    *(f"wyckoff_h1_event={value}" for value in INTRADAY_EVENTS),
    *(f"wyckoff_m15_event={value}" for value in INTRADAY_EVENTS),
)
_CATEGORIES = {
    "context_bucket": ("ALIGNED", "NEUTRAL", "AGAINST"),
    "h1_alignment": ("ALIGNED", "NEUTRAL", "AGAINST"),
    "d1_bias": ("BULLISH", "BEARISH", "UNKNOWN", "MIXED"),
    "h4_location": ("DISCOUNT", "PREMIUM", "EQUILIBRIUM", "MID", "UNKNOWN"),
}
_MIN_ROWS = {"train": 30, "validation": 10, "test": 10}


class OutcomeClassifierError(ValueError):
    """Error de contrato, datos o entrenamiento del clasificador."""


class TrainingAuthorizationError(OutcomeClassifierError):
    """La evidencia científica no autoriza entrenamiento real."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise OutcomeClassifierError(f"{field} debe ser numérico")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OutcomeClassifierError(f"{field} debe ser numérico") from exc
    if not math.isfinite(result):
        raise OutcomeClassifierError(f"{field} debe ser finito")
    return result


def _intraday_features(row: Mapping[str, Any]) -> np.ndarray:
    raw = row.get("features_at_t", row)
    if not isinstance(raw, Mapping):
        raise OutcomeClassifierError("features_at_t debe ser un objeto")
    context = raw.get("context_inputs", {})
    intraday = raw.get("intraday", {})
    if not isinstance(context, Mapping) or not isinstance(intraday, Mapping):
        raise OutcomeClassifierError("features_at_t intradía incompleto")
    ict = intraday.get("ict_m15", {})
    wyckoff = intraday.get("wyckoff", {})
    if not isinstance(ict, Mapping) or not isinstance(wyckoff, Mapping):
        raise OutcomeClassifierError("features_at_t intradía inválido")

    def flag(name: str) -> float:
        return 1.0 if bool(ict.get(name, False)) else 0.0

    def layer(name: str) -> Mapping[str, Any]:
        value = wyckoff.get(name, {})
        return value if isinstance(value, Mapping) else {}

    def event_set(layer_payload: Mapping[str, Any]) -> set[str]:
        events = layer_payload.get("events", ())
        if not isinstance(events, (list, tuple)):
            return set()
        result: set[str] = set()
        for event in events:
            if isinstance(event, Mapping):
                value = event.get("event_type", event.get("type", ""))
            else:
                value = event
            result.add(str(value).upper())
        return result

    h1 = layer("H1")
    m15 = layer("M15")
    h1_phase = str(h1.get("phase", "UNKNOWN")).upper()
    m15_phase = str(m15.get("phase", "UNKNOWN")).upper()
    h1_events = event_set(h1)
    m15_events = event_set(m15)
    values = [
        _finite(context.get("sequence_direction", row.get("direction", 0)), "direction"),
        _finite(row.get("sequence_depth", 0), "sequence_depth"),
        flag("bos_bullish"), flag("bos_bearish"),
        flag("choch_bullish"), flag("choch_bearish"),
        flag("displacement_bullish"), flag("displacement_bearish"),
        flag("fvg_bullish"), flag("fvg_bearish"),
        flag("sweep_up"), flag("sweep_down"),
    ]
    values.extend(1.0 if h1_phase == value else 0.0 for value in INTRADAY_PHASES)
    values.extend(1.0 if m15_phase == value else 0.0 for value in INTRADAY_PHASES)
    values.extend(1.0 if value in h1_events else 0.0 for value in INTRADAY_EVENTS)
    values.extend(1.0 if value in m15_events else 0.0 for value in INTRADAY_EVENTS)
    result = np.asarray(values, dtype=float)
    if len(result) != len(INTRADAY_FEATURE_NAMES) or not np.isfinite(result).all():
        raise OutcomeClassifierError("vector de features intradía inválido")
    return result


def _features(
    row: Mapping[str, Any],
    feature_names: Sequence[str] = FEATURE_NAMES,
) -> np.ndarray:
    if tuple(feature_names) == INTRADAY_FEATURE_NAMES:
        return _intraday_features(row)
    raw = row.get("features_at_t", row)
    if not isinstance(raw, Mapping):
        raise OutcomeClassifierError("features_at_t debe ser un objeto")
    context = raw.get("context_inputs", {})
    if not isinstance(context, Mapping):
        raise OutcomeClassifierError("features_at_t.context_inputs debe ser un objeto")
    sequence = raw.get("sequence", ())
    if not isinstance(sequence, (list, tuple)):
        raise OutcomeClassifierError("features_at_t.sequence debe ser una lista")
    values = [
        _finite(context.get("sequence_direction", row.get("direction", 0)), "direction"),
        _finite(row.get("sequence_depth", 0), "sequence_depth"),
    ]
    for field, categories in _CATEGORIES.items():
        actual = str(context.get(field, "UNKNOWN")).upper()
        values.extend(1.0 if actual == category else 0.0 for category in categories)
    stages = {str(stage).upper() for stage in sequence}
    values.extend(1.0 if stage in stages else 0.0 for stage in (
        "LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE", "OB", "FVG", "CONFLUENCE"
    ))
    result = np.asarray(values, dtype=float)
    if len(result) != len(FEATURE_NAMES) or not np.isfinite(result).all():
        raise OutcomeClassifierError("vector de features inválido")
    return result


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exponent = np.exp(np.clip(shifted, -700.0, 700.0))
    return exponent / exponent.sum(axis=1, keepdims=True)


def _rows(
    rows: Sequence[Mapping[str, Any]],
    target: str,
    feature_names: Sequence[str] = FEATURE_NAMES,
) -> tuple[np.ndarray, np.ndarray]:
    if not rows:
        raise OutcomeClassifierError("no hay filas para entrenar/evaluar")
    labels: list[int] = []
    matrix: list[np.ndarray] = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("can_trade") is not False:
            raise OutcomeClassifierError("todas las filas deben conservar can_trade=false")
        label = str(row.get(target, "")).lower()
        if label not in OUTCOME_CLASSES:
            raise OutcomeClassifierError(f"etiqueta {target} inválida: {label!r}")
        matrix.append(_features(row, feature_names))
        labels.append(OUTCOME_CLASSES.index(label))
    return np.vstack(matrix), np.asarray(labels, dtype=int)


def _metrics(probabilities: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    predicted = np.argmax(probabilities, axis=1)
    clipped = np.clip(probabilities[np.arange(len(labels)), labels], 1e-15, 1.0)
    counts = {name: int(np.sum(labels == index)) for index, name in enumerate(OUTCOME_CLASSES)}
    return {
        "rows": int(len(labels)),
        "accuracy": float(np.mean(predicted == labels)),
        "log_loss": float(-np.mean(np.log(clipped))),
        "class_counts": counts,
    }


@dataclass(frozen=True)
class OutcomeClassifierArtifact:
    """Modelo serializable, trazable y sin autoridad de trading."""

    model_id: str
    model_version: str
    target: str
    snapshot_id: str
    dataset_hash: str
    schema_hash: str
    source_code_commit: str
    experiment_id: str
    feature_names: tuple[str, ...]
    classes: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    weights: tuple[tuple[float, ...], ...]
    bias: tuple[float, ...]
    metrics: Mapping[str, Any]
    seed: int
    shadow_mode: bool = True
    can_trade: bool = False

    def _probabilities(self, features: Mapping[str, Any]) -> np.ndarray:
        vector = _features(features, self.feature_names)
        mean = np.asarray(self.mean, dtype=float)
        scale = np.asarray(self.scale, dtype=float)
        weights = np.asarray(self.weights, dtype=float)
        bias = np.asarray(self.bias, dtype=float)
        return _softmax(((vector - mean) / scale).reshape(1, -1) @ weights.T + bias)[0]

    def predict(self, features: Mapping[str, Any], *, in_domain: bool | None = None) -> dict[str, Any]:
        probabilities = self._probabilities(features)
        feature_vector = _features(features, self.feature_names)
        confidence = float(np.max(probabilities))
        index = int(np.argmax(probabilities))
        abstention = evaluate_abstention(
            {name: float(value) for name, value in zip(self.feature_names, feature_vector)},
            confidence,
            in_domain,
            required_features=("direction", "sequence_depth"),
        )
        return {
            "schema_version": OUTCOME_CLASSIFIER_SCHEMA_VERSION,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "target": self.target,
            "lineage": {
                "snapshot_id": self.snapshot_id,
                "dataset_hash": self.dataset_hash,
                "schema_hash": self.schema_hash,
                "source_code_commit": self.source_code_commit,
                "experiment_id": self.experiment_id,
            },
            "prediction": self.classes[index],
            "probabilities": {name: float(probabilities[i]) for i, name in enumerate(self.classes)},
            "confidence": confidence,
            "abstention": abstention.to_dict(),
            "shadow_mode": True,
            "can_trade": False,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": OUTCOME_CLASSIFIER_SCHEMA_VERSION,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "target": self.target,
            "snapshot_id": self.snapshot_id,
            "dataset_hash": self.dataset_hash,
            "schema_hash": self.schema_hash,
            "source_code_commit": self.source_code_commit,
            "experiment_id": self.experiment_id,
            "feature_names": list(self.feature_names),
            "classes": list(self.classes),
            "mean": list(self.mean),
            "scale": list(self.scale),
            "weights": [list(row) for row in self.weights],
            "bias": list(self.bias),
            "metrics": json.loads(json.dumps(self.metrics, sort_keys=True)),
            "seed": self.seed,
            "shadow_mode": True,
            "can_trade": False,
        }
        payload["artifact_hash"] = hashlib.sha256(_canonical_json(payload)).hexdigest()
        return payload

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination


def train_outcome_classifier(
    pipeline: TrainingPipeline,
    *,
    research_gate: Mapping[str, Any],
    target: str = "label_end_6",
    min_class_rows: int = 5,
    iterations: int = 500,
    learning_rate: float = 0.05,
    l2: float = 1e-4,
    feature_names: Sequence[str] = FEATURE_NAMES,
) -> OutcomeClassifierArtifact:
    """Entrena el baseline únicamente con autorización científica explícita."""
    plan = pipeline.plan()
    if not isinstance(research_gate, Mapping):
        raise TrainingAuthorizationError("research_gate requerido")
    if research_gate.get("status") != "PASS" or research_gate.get("verdict") != "TRAINING_ELIGIBLE":
        raise TrainingAuthorizationError("el experimento no está TRAINING_ELIGIBLE")
    if research_gate.get("dataset_hash") != plan.dataset_hash:
        raise TrainingAuthorizationError("research_gate.dataset_hash no coincide")
    if target not in plan.labels:
        raise OutcomeClassifierError(f"target no registrado en labels: {target}")
    if isinstance(min_class_rows, bool) or not isinstance(min_class_rows, int) or min_class_rows < 1:
        raise OutcomeClassifierError("min_class_rows debe ser entero positivo")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise OutcomeClassifierError("iterations debe ser entero positivo")
    feature_names = tuple(feature_names)
    if feature_names not in (FEATURE_NAMES, INTRADAY_FEATURE_NAMES):
        raise OutcomeClassifierError("perfil de features no registrado")
    lr = _finite(learning_rate, "learning_rate")
    penalty = _finite(l2, "l2")
    if lr <= 0 or penalty < 0:
        raise OutcomeClassifierError("learning_rate/l2 fuera de rango")

    train_rows, validation_rows, test_rows = plan.split.train, plan.split.validation, plan.split.test
    for name, rows in (("train", train_rows), ("validation", validation_rows), ("test", test_rows)):
        if len(rows) < _MIN_ROWS[name]:
            raise TrainingAuthorizationError(f"{name} no alcanza el mínimo de {_MIN_ROWS[name]} filas")
    x_train, y_train = _rows(train_rows, target, feature_names)
    x_validation, y_validation = _rows(validation_rows, target, feature_names)
    x_test, y_test = _rows(test_rows, target, feature_names)
    counts = np.bincount(y_train, minlength=len(OUTCOME_CLASSES))
    if np.any(counts < min_class_rows):
        raise TrainingAuthorizationError("TRAIN no contiene soporte mínimo para las tres clases")

    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale = np.where(scale > 0.0, scale, 1.0)
    normalized_train = (x_train - mean) / scale
    rng = np.random.default_rng(plan.seed)
    weights = rng.normal(0.0, 0.01, size=(len(OUTCOME_CLASSES), x_train.shape[1]))
    bias = np.zeros(len(OUTCOME_CLASSES), dtype=float)
    one_hot = np.eye(len(OUTCOME_CLASSES))[y_train]
    for _ in range(iterations):
        probabilities = _softmax(normalized_train @ weights.T + bias)
        error = probabilities - one_hot
        weights -= lr * ((error.T @ normalized_train) / len(y_train) + penalty * weights)
        bias -= lr * error.mean(axis=0)

    def evaluate(rows: Sequence[Mapping[str, Any]], x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
        normalized = (x - mean) / scale
        return _metrics(_softmax(normalized @ weights.T + bias), y)

    metrics = {
        "model_training_executed": True,
        "algorithm": "deterministic_multinomial_softmax",
        "target": target,
        "classes": list(OUTCOME_CLASSES),
        "train": evaluate(train_rows, x_train, y_train),
        "validation": evaluate(validation_rows, x_validation, y_validation),
        "test_oos": evaluate(test_rows, x_test, y_test),
        "selection_scope": "TRAIN only for fitting; VALIDATION for reporting",
        "oos_scope": "TEST_OOS never used for fitting",
        "calibration_status": "NOT_CALIBRATED",
        "policy": "SHADOW_ONLY_NO_ORDER",
    }
    return OutcomeClassifierArtifact(
        model_id=plan.model_id,
        model_version=plan.model_version,
        target=target,
        snapshot_id=plan.snapshot_id,
        dataset_hash=plan.dataset_hash,
        schema_hash=plan.schema_hash,
        source_code_commit=pipeline.registry.get_model(plan.model_id, plan.model_version).git_commit,
        experiment_id=pipeline.registry.get_model(plan.model_id, plan.model_version).experiment_id,
        feature_names=feature_names,
        classes=OUTCOME_CLASSES,
        mean=tuple(float(value) for value in mean),
        scale=tuple(float(value) for value in scale),
        weights=tuple(tuple(float(value) for value in row) for row in weights),
        bias=tuple(float(value) for value in bias),
        metrics=metrics,
        seed=plan.seed,
    )


__all__ = [
    "FEATURE_NAMES",
    "INTRADAY_FEATURE_NAMES",
    "OUTCOME_CLASSES",
    "OUTCOME_CLASSIFIER_SCHEMA_VERSION",
    "OutcomeClassifierArtifact",
    "OutcomeClassifierError",
    "TrainingAuthorizationError",
    "train_outcome_classifier",
]
