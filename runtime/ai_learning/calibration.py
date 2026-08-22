"""Calibración determinista y métricas de probabilidad para INF-6.

Este módulo es deliberadamente puro: no lee ni escribe archivos, no ejecuta
experimentos y no depende de un modelo entrenado. El calibrador isotónico se
ajusta únicamente con observaciones marcadas como permitidas por el llamador.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Sequence


DEFAULT_MAX_ABS_SCORE = 1_000_000.0
DEFAULT_BIN_COUNT = 10


class CalibrationError(ValueError):
    """Entrada inválida o contrato de calibración incumplido."""


@dataclass(frozen=True)
class ReliabilityBin:
    """Una celda de una curva de fiabilidad."""

    bin_lower: float
    bin_upper: float
    count: int
    mean_probability: float
    observed_frequency: float

    @property
    def calibration_gap(self) -> float:
        return abs(self.mean_probability - self.observed_frequency)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bin_lower": self.bin_lower,
            "bin_upper": self.bin_upper,
            "count": self.count,
            "mean_probability": self.mean_probability,
            "observed_frequency": self.observed_frequency,
            "calibration_gap": self.calibration_gap,
        }


@dataclass(frozen=True)
class _Block:
    upper_score: float
    probability: float
    count: int


@dataclass(frozen=True)
class IsotonicCalibrator:
    """Calibrador isotónico serializable por sus valores, sin estado externo."""

    blocks: tuple[_Block, ...]
    score_min: float
    score_max: float
    max_abs_score: float = DEFAULT_MAX_ABS_SCORE

    def predict(self, scores: Iterable[float]) -> tuple[float, ...]:
        values = _validated_scores(scores, max_abs_score=self.max_abs_score)
        return tuple(self.predict_one(value) for value in values)

    def predict_one(self, score: float) -> float:
        if not _valid_positive_finite(self.max_abs_score):
            raise CalibrationError("max_abs_score debe ser finito y positivo")
        value = _validated_score(score, max_abs_score=self.max_abs_score)
        for block in self.blocks:
            if value <= block.upper_score:
                return block.probability
        return self.blocks[-1].probability

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": "isotonic",
            "score_min": self.score_min,
            "score_max": self.score_max,
            "max_abs_score": self.max_abs_score,
            "blocks": [
                {
                    "upper_score": block.upper_score,
                    "probability": block.probability,
                    "count": block.count,
                }
                for block in self.blocks
            ],
        }


def fit_calibrator(
    scores: Sequence[float],
    outcomes: Sequence[int | bool],
    *,
    allowed: bool | Sequence[bool],
    max_abs_score: float = DEFAULT_MAX_ABS_SCORE,
) -> IsotonicCalibrator:
    """Ajusta un calibrador isotónico solo con observaciones permitidas.

    ``allowed=True`` autoriza explícitamente todas las filas. Con una máscara,
    las filas falsas se excluyen antes del ajuste. ``allowed=False`` y una
    máscara sin filas permitidas se rechazan para evitar calibración accidental
    con datos no autorizados.
    """

    score_values = _validated_scores(scores, max_abs_score=max_abs_score)
    outcome_values = _validated_outcomes(outcomes)
    if len(score_values) != len(outcome_values):
        raise CalibrationError("scores y outcomes deben tener la misma longitud")
    selected = _allowed_indices(len(score_values), allowed)
    if not selected:
        raise CalibrationError("no hay datos permitidos para calibrar")

    pairs = sorted(
        ((score_values[index], float(outcome_values[index])) for index in selected),
        key=lambda pair: pair[0],
    )
    grouped: list[list[float]] = []
    for score, outcome in pairs:
        if grouped and grouped[-1][0] == score:
            grouped[-1][1] += outcome
            grouped[-1][2] += 1.0
        else:
            grouped.append([score, outcome, 1.0])

    # PAVA (pool adjacent violators algorithm), con medias ponderadas.
    blocks: list[list[float]] = []  # [upper_score, positive_count, count]
    for score, positives, count in grouped:
        blocks.append([score, positives, count])
        while len(blocks) >= 2 and _rate(blocks[-2]) > _rate(blocks[-1]):
            right = blocks.pop()
            left = blocks.pop()
            blocks.append(
                [right[0], left[1] + right[1], left[2] + right[2]]
            )

    return IsotonicCalibrator(
        blocks=tuple(
            _Block(
                upper_score=block[0],
                probability=_rate(block),
                count=int(block[2]),
            )
            for block in blocks
        ),
        score_min=pairs[0][0],
        score_max=pairs[-1][0],
        max_abs_score=max_abs_score,
    )


def calibrate_scores(
    scores: Sequence[float],
    outcomes: Sequence[int | bool],
    *,
    allowed: bool | Sequence[bool],
    query_scores: Sequence[float] | None = None,
    max_abs_score: float = DEFAULT_MAX_ABS_SCORE,
) -> tuple[float, ...]:
    """Ajusta y aplica calibración en una sola operación determinista."""

    calibrator = fit_calibrator(
        scores, outcomes, allowed=allowed, max_abs_score=max_abs_score
    )
    return calibrator.predict(scores if query_scores is None else query_scores)


def score_to_probability(
    score: float,
    *,
    temperature: float = 1.0,
    max_abs_score: float = DEFAULT_MAX_ABS_SCORE,
) -> float:
    """Convierte un score firmado en probabilidad mediante sigmoide estable.

    Esta es una transformación monotónica y determinista; no pretende
    sustituir ``fit_calibrator`` cuando existan datos permitidos de calibración.
    """

    if not _valid_positive_finite(max_abs_score):
        raise CalibrationError("max_abs_score debe ser finito y positivo")
    value = _validated_score(score, max_abs_score=max_abs_score)
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
        raise CalibrationError("temperature debe ser numérica")
    if not math.isfinite(float(temperature)) or float(temperature) <= 0.0:
        raise CalibrationError("temperature debe ser finita y positiva")
    logit = value / float(temperature)
    if logit >= 0.0:
        exponent = math.exp(-logit)
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(logit)
    return exponent / (1.0 + exponent)


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int | bool]) -> float:
    """Calcula el Brier score binario, menor es mejor."""

    values, labels = _validated_probability_outcomes(probabilities, outcomes)
    return sum((probability - label) ** 2 for probability, label in zip(values, labels)) / len(values)


def reliability_curve(
    probabilities: Sequence[float],
    outcomes: Sequence[int | bool],
    *,
    n_bins: int = DEFAULT_BIN_COUNT,
) -> tuple[ReliabilityBin, ...]:
    """Agrupa probabilidades en bins uniformes y devuelve observados vs. predichos."""

    values, labels = _validated_probability_outcomes(probabilities, outcomes)
    bin_count = _validated_bin_count(n_bins)
    buckets: list[list[float]] = [[] for _ in range(bin_count)]
    for probability, label in zip(values, labels):
        index = min(int(probability * bin_count), bin_count - 1)
        buckets[index].append((probability, float(label)))
    width = 1.0 / bin_count
    result: list[ReliabilityBin] = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        result.append(
            ReliabilityBin(
                bin_lower=index * width,
                bin_upper=(index + 1) * width,
                count=len(bucket),
                mean_probability=sum(item[0] for item in bucket) / len(bucket),
                observed_frequency=sum(item[1] for item in bucket) / len(bucket),
            )
        )
    return tuple(result)


def calibration_error(
    probabilities: Sequence[float],
    outcomes: Sequence[int | bool],
    *,
    n_bins: int = DEFAULT_BIN_COUNT,
    norm: str = "l1",
) -> float:
    """Calcula ECE (``l1``) o el máximo error de calibración (``max``)."""

    values, _ = _validated_probability_outcomes(probabilities, outcomes)
    curve = reliability_curve(values, outcomes, n_bins=n_bins)
    if norm == "max":
        return max((point.calibration_gap for point in curve), default=0.0)
    if norm != "l1":
        raise CalibrationError("norm debe ser 'l1' o 'max'")
    total = len(values)
    return sum(point.count * point.calibration_gap for point in curve) / total


def uncertainty(probability: float) -> float:
    """Devuelve entropía binaria normalizada en [0, 1]."""

    value = _validated_probability(probability)
    if value in (0.0, 1.0):
        return 0.0
    return -(value * math.log2(value) + (1.0 - value) * math.log2(1.0 - value))


def confidence_score(probability: float) -> float:
    """Devuelve confianza separada de probabilidad: 0 en 0.5 y 1 en extremos."""

    value = _validated_probability(probability)
    return abs(2.0 * value - 1.0)


def coverage(
    probabilities: Sequence[float],
    *,
    min_confidence: float = 0.5,
) -> float:
    """Fracción de predicciones cuya confianza alcanza el umbral indicado."""

    values = tuple(_validated_probability(value) for value in probabilities)
    if not values:
        raise CalibrationError("probabilities no puede estar vacío")
    if not isinstance(min_confidence, (int, float)) or isinstance(min_confidence, bool):
        raise CalibrationError("min_confidence debe ser numérica")
    threshold = float(min_confidence)
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise CalibrationError("min_confidence debe estar en [0, 1]")
    return sum(confidence_score(value) >= threshold for value in values) / len(values)


def _allowed_indices(length: int, allowed: bool | Sequence[bool]) -> tuple[int, ...]:
    if isinstance(allowed, bool):
        if not allowed:
            raise CalibrationError("los datos de calibración no están permitidos")
        return tuple(range(length))
    if isinstance(allowed, (str, bytes)):
        raise CalibrationError("allowed debe ser booleano o máscara booleana")
    try:
        mask = tuple(allowed)
    except TypeError as exc:
        raise CalibrationError("allowed debe ser booleano o máscara booleana") from exc
    if len(mask) != length or not all(isinstance(value, bool) for value in mask):
        raise CalibrationError("allowed debe tener la longitud y tipo booleano correctos")
    return tuple(index for index, value in enumerate(mask) if value)


def _validated_scores(values: Iterable[float], *, max_abs_score: float) -> tuple[float, ...]:
    if not _valid_positive_finite(max_abs_score):
        raise CalibrationError("max_abs_score debe ser finito y positivo")
    try:
        result = tuple(_validated_score(value, max_abs_score=max_abs_score) for value in values)
    except TypeError as exc:
        raise CalibrationError("scores debe ser una secuencia numérica") from exc
    if not result:
        raise CalibrationError("scores no puede estar vacío")
    return result


def _validated_score(value: float, *, max_abs_score: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError("score debe ser numérico")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise CalibrationError("score no puede ser NaN ni infinito")
    if abs(numeric) > max_abs_score:
        raise CalibrationError("score extremo fuera del límite permitido")
    return numeric


def _validated_outcomes(values: Iterable[int | bool]) -> tuple[int, ...]:
    try:
        result = tuple(values)
    except TypeError as exc:
        raise CalibrationError("outcomes debe ser una secuencia binaria") from exc
    if not result:
        raise CalibrationError("outcomes no puede estar vacío")
    if any(value not in (0, 1, False, True) for value in result):
        raise CalibrationError("outcomes debe contener solo 0, 1, False o True")
    return tuple(int(value) for value in result)


def _validated_probability(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError("probability debe ser numérica")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise CalibrationError("probability no puede ser NaN ni infinito")
    if not 0.0 <= numeric <= 1.0:
        raise CalibrationError("probability debe estar en [0, 1]")
    return numeric


def _validated_probability_outcomes(
    probabilities: Sequence[float], outcomes: Sequence[int | bool]
) -> tuple[tuple[float, ...], tuple[int, ...]]:
    values = tuple(_validated_probability(value) for value in probabilities)
    labels = _validated_outcomes(outcomes)
    if len(values) != len(labels):
        raise CalibrationError("probabilities y outcomes deben tener la misma longitud")
    return values, labels


def _validated_bin_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000:
        raise CalibrationError("n_bins debe ser un entero entre 1 y 1000")
    return value


def _valid_positive_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0.0


def _rate(block: Sequence[float]) -> float:
    return block[1] / block[2]


__all__ = [
    "CalibrationError",
    "DEFAULT_BIN_COUNT",
    "DEFAULT_MAX_ABS_SCORE",
    "IsotonicCalibrator",
    "ReliabilityBin",
    "brier_score",
    "calibrate_scores",
    "calibration_error",
    "confidence_score",
    "coverage",
    "fit_calibrator",
    "reliability_curve",
    "score_to_probability",
    "uncertainty",
]
