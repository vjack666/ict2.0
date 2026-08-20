from __future__ import annotations

import pandas as pd

from engine.ltf_canonical_feed import build_ltf_canonical_feed
from engine.market_object import ObjectState, ObjectType


def _m15() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=5, freq="15min"),
            "open": [1.09, 1.02, 1.12, 1.115, 1.13],
            "high": [1.10, 1.13, 1.14, 1.135, 1.14],
            "low": [1.00, 1.01, 1.11, 1.105, 1.12],
            "close": [1.01, 1.12, 1.13, 1.125, 1.135],
        }
    )


def test_canonical_feed_reuses_detectors_and_tracks_touch_as_of_decision_time():
    frame = _m15()
    result = build_ltf_canonical_feed(
        {"M15": frame},
        pd.Timestamp("2020-01-01 00:45", tz="UTC"),
        exec_tf="M15",
        include_sequence=False,
    )

    zones = result["zones"]["M15"]
    assert result["source"].startswith("engine.detectors")
    assert any(obj.type is ObjectType.FVG for obj in zones)
    fvg = next(obj for obj in zones if obj.type is ObjectType.FVG)
    assert fvg.state is ObjectState.PARTIALLY_MITIGATED
    assert fvg.touch_count == 1
    assert fvg.first_touch_time == frame.iloc[3]["time"]


def test_canonical_feed_excludes_future_objects_and_is_deterministic():
    frame = _m15()
    t = pd.Timestamp("2020-01-01 00:30", tz="UTC")
    before = build_ltf_canonical_feed({"M15": frame}, t, include_sequence=False)
    extended = pd.concat(
        [frame, pd.DataFrame({"time": [pd.Timestamp("2020-01-01 02:00")], "open": [1.1], "high": [1.2], "low": [1.0], "close": [1.15]})],
        ignore_index=True,
    )
    after = build_ltf_canonical_feed({"M15": extended}, t, include_sequence=False)
    assert [obj.to_dict() for obj in before["zones"]["M15"]] == [obj.to_dict() for obj in after["zones"]["M15"]]
