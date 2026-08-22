from __future__ import annotations

import numpy as np
import pandas as pd

from engine.mtf_navigation import NavigatorConfig, TimeframeLayer
from scripts.audit.tna_streaming_prefix_compare import (
    _BatchFingerprintNavigator,
    _StreamingFingerprintNavigator,
    _prefix_hash,
    _snapshot_payload,
)


def _frames(n: int = 90) -> dict[str, pd.DataFrame]:
    times = pd.date_range("2020-01-01", periods=n, freq="h")
    out = {}
    for seed, tf in enumerate(("D1", "H4", "H1")):
        rng = np.random.default_rng(seed + 70)
        close = 1.1 + np.cumsum(rng.normal(0, 0.0005, n))
        out[tf] = pd.DataFrame(
            {
                "time": times,
                "open": close,
                "high": close + 0.0005,
                "low": close - 0.0005,
                "close": close,
            }
        )
    return out


def test_streaming_prefix_matches_batch_at_every_decision():
    frames = _frames()
    config = NavigatorConfig(precompute_sequences=True, sequence_tf="H1")
    full = _BatchFingerprintNavigator(frames, config)
    for pre in full._pre.values():
        pre["zone_prefix_hash"] = _prefix_hash(pre["zone_events"])
    prefix = _StreamingFingerprintNavigator(frames, config, full)

    for i, decision_time in enumerate(frames["H1"]["time"]):
        prefix.advance(decision_time)
        for tf in ("D1", "H4", "H1"):
            layer = TimeframeLayer(tf)
            assert _snapshot_payload(full._snapshot(layer, decision_time)) == _snapshot_payload(
                prefix._snapshot(layer, decision_time)
            )
        if i in (0, len(frames["H1"]) - 1):
            assert full.navigate(decision_time).to_dict() == prefix.navigate(decision_time).to_dict()
