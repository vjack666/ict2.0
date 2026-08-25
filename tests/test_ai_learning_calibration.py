from __future__ import annotations

import math

import pytest

from runtime.ai_learning.calibration import (
    CalibrationError,
    brier_score,
    calibrate_scores,
    calibration_error,
    confidence_score,
    coverage,
    fit_calibrator,
    reliability_curve,
    score_to_probability,
    uncertainty,
)


def test_isotonic_calibration_is_deterministic_monotonic_and_uses_only_allowed_rows():
    scores = (-0.8, -0.2, 0.2, 0.8)
    outcomes = (0, 1, 0, 1)
    allowed = (True, True, False, True)

    first = fit_calibrator(scores, outcomes, allowed=allowed)
    second = fit_calibrator(scores, outcomes, allowed=allowed)

    assert first.to_dict() == second.to_dict()
    assert first.predict((-0.8, -0.2, 0.8)) == (0.0, 1.0, 1.0)
    assert tuple(sorted(first.predict(scores))) == first.predict(scores)
    assert calibrate_scores(scores, outcomes, allowed=allowed) == first.predict(scores)


def test_calibration_rejects_unpermitted_data_and_nan_or_extreme_values():
    with pytest.raises(CalibrationError, match="no están permitidos"):
        fit_calibrator((0.0, 1.0), (0, 1), allowed=False)
    with pytest.raises(CalibrationError, match="no hay datos permitidos"):
        fit_calibrator((0.0, 1.0), (0, 1), allowed=(False, False))
    with pytest.raises(CalibrationError, match="NaN"):
        score_to_probability(float("nan"))
    with pytest.raises(CalibrationError, match="extremo"):
        score_to_probability(1_000_001.0)
    with pytest.raises(CalibrationError, match="NaN"):
        brier_score((float("nan"),), (1,))


def test_probability_metrics_and_reliability_curve_are_bounded():
    probabilities = (0.1, 0.2, 0.8, 0.9)
    outcomes = (0, 0, 1, 1)
    curve = reliability_curve(probabilities, outcomes, n_bins=2)

    assert brier_score(probabilities, outcomes) == pytest.approx(0.025)
    assert calibration_error(probabilities, outcomes, n_bins=2) == pytest.approx(0.15)
    assert calibration_error(probabilities, outcomes, n_bins=2, norm="max") == pytest.approx(0.15)
    assert sum(point.count for point in curve) == 4
    assert all(0.0 <= point.mean_probability <= 1.0 for point in curve)
    assert all(0.0 <= point.observed_frequency <= 1.0 for point in curve)


def test_confidence_is_not_probability_and_uncertainty_has_expected_extrema():
    assert score_to_probability(0.0) == pytest.approx(0.5)
    assert confidence_score(0.5) == 0.0
    assert confidence_score(0.9) == confidence_score(0.1)
    assert confidence_score(0.9) != 0.9
    assert uncertainty(0.5) == pytest.approx(1.0)
    assert uncertainty(0.0) == pytest.approx(0.0)
    assert coverage((0.1, 0.5, 0.9), min_confidence=0.5) == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    "probabilities,outcomes",
    [((1.2,), (1,)), ((0.2,), (2,)), ((math.inf,), (1,)), ((), ())],
)
def test_metrics_reject_invalid_ranges(probabilities, outcomes):
    with pytest.raises(CalibrationError):
        brier_score(probabilities, outcomes)
