from __future__ import annotations

import json

import pandas as pd
import pytest

from engine.daily_motor import DailyMotorConfig, build_daily_motor_snapshot
from engine.market_object import MarketObject, ObjectState, ObjectType


def _frame(tf: str, n: int = 30, *, trend: str = "BULLISH", future: bool = False) -> pd.DataFrame:
    start = "2030-01-01" if future else "2020-01-01"
    t = pd.date_range(start, periods=n, freq="h")
    close = [1.1000 + i * 0.0001 for i in range(n)]
    return pd.DataFrame(
        {
            "time": t,
            "open": close,
            "high": [x + 0.0002 for x in close],
            "low": [x - 0.0002 for x in close],
            "close": close,
            "trend": [trend] * n,
            "bos_dir": [1] * n if trend == "BULLISH" else [-1] * n,
            "bos_status": ["active"] * n,
            "fvg_state": ["ACTIVE"] * n if tf == "M15" else ["NONE"] * n,
            "ob_direction": ["BULLISH"] * n if tf == "M15" else ["-"] * n,
        }
    )


def _frames() -> dict[str, pd.DataFrame]:
    return {tf: _frame(tf) for tf in ("D1", "H4", "H1", "M15")}


def _canonical_zone(*, retested: bool = True) -> MarketObject:
    return MarketObject(
        id="FVG_M15_CANONICAL_1",
        type=ObjectType.FVG,
        origin_tf="M15",
        direction=1,
        zone_high=1.1020,
        zone_low=1.1010,
        state=ObjectState.PARTIALLY_MITIGATED if retested else ObjectState.ACTIVE,
        candidate_time=pd.Timestamp("2020-01-01 08:00", tz="UTC"),
        confirmation_time=pd.Timestamp("2020-01-01 10:00", tz="UTC"),
        tradable_time=pd.Timestamp("2020-01-01 10:00", tz="UTC"),
        first_touch_time=(pd.Timestamp("2020-01-01 12:00", tz="UTC") if retested else None),
        touch_count=1 if retested else 0,
        parent_object="POI_H1_1",
        related_objects=["BOS_M15_1"],
        meta={"lineage_refs": ["SEQ_H1_1"]},
    )


def test_daily_motor_is_observe_only_and_reports_ltf():
    result = build_daily_motor_snapshot(
        _frames(),
        decision_time=pd.Timestamp("2020-01-02"),
        canonical_zones={"M15": [_canonical_zone()]},
        sequence_snapshot={"refs": ["SEQ_H1_1"], "depth": 7},
        context_snapshot={"poi_refs": ["POI_H1_1"]},
    )
    assert result["policy"] == "OBSERVE_ONLY_NO_ORDER"
    assert result["entry_authorized"] is False
    assert "entry" not in result
    assert result["profile_id"] == "DAILY_D1_H4_H1_M15_READING"
    assert set(result["asof_times_by_tf"]) == {"D1", "H4", "H1", "M15"}
    assert result["ltf"]["tf"] == "M15"
    assert result["ltf"]["zone_present"] is True
    assert result["ltf"]["zone_refs"][0]["zone_id"] == "FVG_M15_CANONICAL_1"
    assert result["ltf"]["retest_state"] == "OBSERVED"
    assert result["sequence"] == {"available": True, "refs": ["SEQ_H1_1"], "depth": 7}
    assert "POI_H1_1" in result["lineage_refs"]


def test_daily_motor_does_not_promote_legacy_dataframe_zone_flags():
    result = build_daily_motor_snapshot(
        _frames(),
        decision_time=pd.Timestamp("2020-01-02"),
        config=DailyMotorConfig(require_pd=False),
    )
    assert result["ltf"]["legacy_zone_marker"] is True
    assert result["ltf"]["zone_present"] is False
    assert result["status"] == "WAIT_LTF_ZONE"


def test_daily_motor_ignores_future_ltf_and_htf_rows():
    frames = _frames()
    t = pd.Timestamp("2020-01-01 12:00", tz="UTC")
    zones = {"M15": [_canonical_zone()]}
    before = build_daily_motor_snapshot(frames, decision_time=t, canonical_zones=zones)
    for tf in frames:
        frames[tf] = pd.concat([frames[tf], _frame(tf, n=5, future=True)], ignore_index=True)
    after = build_daily_motor_snapshot(frames, decision_time=t, canonical_zones=zones)
    assert after["decision_time"] == before["decision_time"]
    assert after["direction"] == before["direction"]
    assert after["status"] == before["status"]
    assert after["ltf"]["asof_time"] == before["ltf"]["asof_time"]
    assert after["asof_times_by_tf"] == before["asof_times_by_tf"]
    assert json.dumps(after, sort_keys=True, allow_nan=False)


@pytest.mark.parametrize("future_tf", ["D1", "H4", "M15"])
def test_daily_motor_future_added_to_one_tf_does_not_mutate_snapshot(future_tf):
    frames = _frames()
    t = pd.Timestamp("2020-01-01 12:00", tz="UTC")
    zones = {"M15": [_canonical_zone()]}
    before = build_daily_motor_snapshot(
        frames,
        decision_time=t,
        config=DailyMotorConfig(require_pd=False),
        canonical_zones=zones,
    )
    frames[future_tf] = pd.concat([frames[future_tf], _frame(future_tf, n=5, future=True)], ignore_index=True)
    after = build_daily_motor_snapshot(
        frames,
        decision_time=t,
        config=DailyMotorConfig(require_pd=False),
        canonical_zones=zones,
    )
    assert after == before


def test_daily_motor_same_input_is_deterministic_and_ltf_cannot_change_bias():
    frames = _frames()
    t = pd.Timestamp("2020-01-02", tz="UTC")
    context = {"direction_hint": "BULLISH", "poi_refs": ["POI_H1_1"]}
    first = build_daily_motor_snapshot(
        frames,
        decision_time=t,
        config=DailyMotorConfig(require_pd=False),
        canonical_zones={"M15": [_canonical_zone()]},
        sequence_snapshot={"refs": ["SEQ_H1_1"], "depth": 7},
        context_snapshot=context,
    )
    second = build_daily_motor_snapshot(
        frames,
        decision_time=t,
        config=DailyMotorConfig(require_pd=False),
        canonical_zones={"M15": [_canonical_zone()]},
        sequence_snapshot={"refs": ["SEQ_H1_1"], "depth": 7},
        context_snapshot=context,
    )
    assert first == second
    assert first["context"]["direction_hint"] == 1

    opposite = {**frames, "M15": _frame("M15", trend="BEARISH")}
    result = build_daily_motor_snapshot(
        opposite,
        decision_time=t,
        config=DailyMotorConfig(require_pd=False),
        context_snapshot=context,
    )
    assert result["context"]["direction_hint"] == 1
    assert result["status"] == "WAIT_LTF_CONFIRMATION"


def test_daily_motor_missing_context_does_not_promote_ltf():
    frames = {"M15": _frame("M15")}
    result = build_daily_motor_snapshot(
        frames,
        decision_time=pd.Timestamp("2020-01-02"),
        config=DailyMotorConfig(require_d1=False, require_itf=False, require_context=False, require_pd=False),
    )
    assert result["status"] in {"WAIT_CONTEXT", "WAIT_LTF_CONFIRMATION", "WAIT_LTF_ZONE", "WAIT_RETEST"}
    assert result["entry_authorized"] is False


def test_daily_motor_retest_requires_canonical_touch_after_tradable():
    result = build_daily_motor_snapshot(
        _frames(),
        decision_time=pd.Timestamp("2020-01-02", tz="UTC"),
        config=DailyMotorConfig(require_pd=False),
        canonical_zones={"M15": [_canonical_zone(retested=False)]},
    )
    assert result["ltf"]["zone_present"] is True
    assert result["ltf"]["retest_observed"] is False
    assert result["status"] == "WAIT_RETEST"
