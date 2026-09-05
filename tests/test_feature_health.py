import pytest

from runtime.ai_learning.feature_health import FeatureHealthError, validate_temporal_feature_health


def _row(depth, value):
    return {"features_at_t": {"sequence_depth": depth, "direction": value, "state": value}}


def test_rejects_zero_temporal_depth():
    with pytest.raises(FeatureHealthError, match="SEQUENCE_DEPTH_ZERO"):
        validate_temporal_feature_health([_row(0, 1), _row(0, -1)])


def test_rejects_nearly_constant_features():
    rows = [_row(3, 1) for _ in range(20)]
    with pytest.raises(FeatureHealthError, match="NEAR_CONSTANT"):
        validate_temporal_feature_health(rows)


def test_accepts_varying_temporal_features():
    rows = [_row(3 + i % 2, i % 3) for i in range(20)]
    result = validate_temporal_feature_health(rows)
    assert result["varying_fraction"] >= 0.10
