from copy import deepcopy

import pandas as pd

from audits.codigo.mtf_replay_t7 import derive_h4
from engine.historical_event_objects import build_historical_event_objects
from engine.market_object import ObjectType


def _m15(periods: int = 320) -> pd.DataFrame:
    times = pd.date_range("2025-01-01T00:15:00Z", periods=periods, freq="15min")
    # Deterministic sawtooth with impulses creates structure and displacement.
    base = []
    value = 1.10
    for i in range(periods):
        step = (0.0018 if (i // 24) % 2 == 0 else -0.0018) + (0.006 if i % 79 == 0 else 0)
        opened = value
        closed = value + step
        base.append({"time": times[i], "open": opened, "high": max(opened, closed) + 0.0004,
                     "low": min(opened, closed) - 0.0004, "close": closed, "volume": 100.0})
        value = closed
    return pd.DataFrame(base)


def _signature(result):
    return [(o.id, o.type.value, str(o.tradable_time), o.parent_object, tuple(o.related_objects)) for o in result["objects"]]


def test_historical_event_producer_is_deterministic_and_child_to_parent():
    m15 = _m15()
    frames = {"M15": m15, "H4": derive_h4(m15)}
    first = build_historical_event_objects(frames)
    second = build_historical_event_objects(deepcopy(frames))
    assert _signature(first) == _signature(second)
    by_id = {obj.id: obj for obj in first["objects"]}
    for obj in first["objects"]:
        if obj.parent_object:
            assert obj.parent_object in by_id
            assert pd.Timestamp(by_id[obj.parent_object].tradable_time) <= pd.Timestamp(obj.tradable_time)
        if obj.type in {ObjectType.BOS, ObjectType.DISPLACEMENT}:
            assert by_id[obj.parent_object].type is ObjectType.ORDER_BLOCK


def test_historical_event_producer_full_prefix_is_exact():
    m15 = _m15(480)
    cutoff = m15.iloc[319]["time"]
    full = build_historical_event_objects({"M15": m15, "H4": derive_h4(m15)})
    prefix_m15 = m15.loc[m15["time"] <= cutoff].copy()
    prefix = build_historical_event_objects({"M15": prefix_m15, "H4": derive_h4(prefix_m15)})
    visible = [row for row in _signature(full) if pd.Timestamp(row[2]) <= cutoff]
    assert visible == _signature(prefix)


def test_bos_and_displacement_are_event_objects_when_present():
    m15 = _m15(640)
    result = build_historical_event_objects({"M15": m15, "H4": derive_h4(m15)})
    for obj in result["objects"]:
        if obj.type is ObjectType.BOS:
            assert obj.parent_object and obj.origin_tf == "M15"
        if obj.type is ObjectType.DISPLACEMENT:
            assert obj.parent_object and obj.origin_tf == "M15"
