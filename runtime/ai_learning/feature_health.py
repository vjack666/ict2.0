"""Automatic guards for the recurrent single-candle/constant-feature failure."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


class FeatureHealthError(ValueError):
    """The training input cannot represent a temporal decision sequence."""


def validate_temporal_feature_health(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_varying_fraction: float = 0.10,
) -> dict[str, Any]:
    """Fail closed when the input collapses to one candle or constants.

    This guard is intentionally model-agnostic. It does not repair values or
    infer missing events; it reports the exact remediation for the extractor,
    funnel and backtest.
    """
    if not rows:
        raise FeatureHealthError("TEMPORAL_FEATURES_EMPTY")
    vectors = [row.get("features_at_t") for row in rows]
    if any(not isinstance(v, Mapping) for v in vectors):
        raise FeatureHealthError("TEMPORAL_FEATURES_MISSING")
    names = sorted({str(k) for v in vectors for k in v})
    varying = []
    for name in names:
        values = {repr(v.get(name)) for v in vectors}
        if len(values) > 1:
            varying.append(name)
    fraction = len(varying) / max(len(names), 1)
    depths = [v.get("sequence_depth") for v in vectors]
    if all(d in (None, 0, "0") for d in depths):
        raise FeatureHealthError("TEMPORAL_SEQUENCE_DEPTH_ZERO: rebuild rolling closed-bar sequence")
    if fraction < min_varying_fraction:
        raise FeatureHealthError(
            f"TEMPORAL_FEATURES_NEAR_CONSTANT:varying_fraction={fraction:.4f}; "
            "rebuild rolling sequence in engine/funnel/backtest"
        )
    return {"rows": len(rows), "feature_count": len(names), "varying_count": len(varying), "varying_fraction": fraction}


__all__ = ["FeatureHealthError", "validate_temporal_feature_health"]
