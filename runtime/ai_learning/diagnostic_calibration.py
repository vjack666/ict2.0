"""First calibration runner for DIAGNOSTIC_ONLY outcome-classifier artifacts.

The calibrator answers one narrow question: given the model's top-class
confidence, how likely is that top-class prediction to be correct?  It fits
only the frozen validation partition and evaluates TEST/OOS without refitting.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .calibration import brier_score, calibration_error, fit_calibrator, reliability_curve
from .diagnostic_training import _build_split, load_causal_jsonl
from .outcome_classifier import OutcomeClassifierArtifact


class DiagnosticCalibrationError(ValueError):
    """A diagnostic model artifact cannot be calibrated safely."""


def _predictions(model: OutcomeClassifierArtifact, rows: Sequence[Mapping[str, Any]], target: str) -> tuple[list[float], list[int]]:
    scores: list[float] = []
    outcomes: list[int] = []
    for row in rows:
        prediction = model.predict(row, in_domain=True)
        scores.append(float(prediction["confidence"]))
        outcomes.append(int(prediction["prediction"] == str(row[target]).lower()))
    if not scores:
        raise DiagnosticCalibrationError("partición vacía")
    return scores, outcomes


def _metrics(probabilities: Sequence[float], outcomes: Sequence[int]) -> dict[str, Any]:
    return {
        "rows": len(probabilities),
        "brier": brier_score(probabilities, outcomes),
        "ece_l1": calibration_error(probabilities, outcomes, n_bins=10),
        "reliability": [point.to_dict() for point in reliability_curve(probabilities, outcomes, n_bins=10)],
    }


def calibrate_diagnostic_artifact(payload: Mapping[str, Any], *, jsonl_path: str) -> dict[str, Any]:
    """Calibrate a completed diagnostic artifact without fitting on TEST/OOS."""

    if payload.get("status") != "DIAGNOSTIC_ONLY_COMPLETED" or payload.get("fit_executed") is not True:
        raise DiagnosticCalibrationError("se requiere artefacto DIAGNOSTIC_ONLY_COMPLETED")
    if payload.get("can_trade") is not False or payload.get("shadow_mode") is not True:
        raise DiagnosticCalibrationError("Shadow Mode y can_trade=false son obligatorios")
    target = str(payload.get("target", ""))
    source = load_causal_jsonl(jsonl_path, target=target)
    expected_hash = (payload.get("input") or {}).get("sha256")
    if source.raw_sha256 != expected_hash:
        raise DiagnosticCalibrationError("JSONL_SOURCE_HASH_MISMATCH")
    config = payload.get("config") or {}
    split = _build_split(
        source.rows,
        train_fraction=float(config.get("train_fraction", 0.6)),
        validation_fraction=float(config.get("validation_fraction", 0.2)),
    )
    validation = list(split.validation)
    test = list(split.test)
    model = OutcomeClassifierArtifact.from_dict(payload.get("model", {}))
    validation_scores, validation_outcomes = _predictions(model, validation, target)
    calibrator = fit_calibrator(validation_scores, validation_outcomes, allowed=True)
    test_scores, test_outcomes = _predictions(model, test, target)
    validation_calibrated = list(calibrator.predict(validation_scores))
    test_calibrated = list(calibrator.predict(test_scores))
    return {
        "kind": "diagnostic_top_class_correctness_calibration",
        "source_artifact_hash": payload.get("artifact_hash"),
        "source_jsonl_sha256": source.raw_sha256,
        "target": target,
        "fit_partition": "VALIDATION_ONLY",
        "test_partition": "TEST_OOS_NEVER_USED_FOR_FIT",
        "calibrator": calibrator.to_dict(),
        "validation": {"raw": _metrics(validation_scores, validation_outcomes), "calibrated": _metrics(validation_calibrated, validation_outcomes)},
        "test_oos": {"raw": _metrics(test_scores, test_outcomes), "calibrated": _metrics(test_calibrated, test_outcomes)},
        "shadow_mode": True,
        "can_trade": False,
        "scientific_training_eligible": False,
        "promotion_authorized": False,
    }
