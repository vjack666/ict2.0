from __future__ import annotations

import json

import pandas as pd

from engine.market_object import ObjectState
from engine.mt5_operational_snapshot import build_mt5_operational_snapshot, build_object_market_state


def _frame(start: str = "2024-01-01", n: int = 8) -> pd.DataFrame:
    times = pd.date_range(start, periods=n, freq="h", tz="UTC")
    # FVG at bar 2 and a later touch; OB detector remains valid on the same
    # canonical OHLC stream when a footprint/follow-through pair is present.
    rows = [
        (1.1000, 1.1010, 1.0990, 1.0995),
        (1.0995, 1.1000, 1.0990, 1.0998),
        (1.1005, 1.1020, 1.1005, 1.1015),
        (1.1000, 1.1005, 1.0985, 1.0990),
        (1.0990, 1.0995, 1.0975, 1.0980),
        (1.0980, 1.0990, 1.0970, 1.0985),
        (1.0985, 1.1000, 1.0980, 1.0995),
        (1.0995, 1.1000, 1.0985, 1.0990),
    ]
    rows = rows[:n]
    return pd.DataFrame(
        {
            "time": times,
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "tick_volume": [100] * n,
        }
    )


def _frames() -> dict[str, pd.DataFrame]:
    return {tf: _frame() for tf in ("D1", "H4", "H1", "M15", "M5", "M1")}


def test_object_market_state_is_event_sourced_and_does_not_mutate_frames():
    frames = _frames()
    before = {tf: df.copy(deep=True) for tf, df in frames.items()}
    state = build_object_market_state(frames, pd.Timestamp("2024-01-01 07:00", tz="UTC"), symbol="EURUSD")
    assert state.all_objects()
    assert any(state.history_of(obj.id) for obj in state.all_objects())
    for tf in frames:
        pd.testing.assert_frame_equal(frames[tf], before[tf])


def test_snapshot_is_blocked_when_required_mt5_timeframe_is_missing():
    frames = _frames()
    frames.pop("M1")
    result = build_mt5_operational_snapshot(
        frames,
        pd.Timestamp("2024-01-01 07:00", tz="UTC"),
        required_tfs=("D1", "H4", "H1", "M15", "M5", "M1"),
        generator_commit="abc123",
    )
    assert result["status"] == "BLOCKED"
    assert result["missing_timeframes"] == ["M1"]
    assert result["policy"] == "OBSERVE_ONLY_NO_ORDER"
    assert result["entry_authorized"] is False


def test_source_artifacts_populate_hashes_and_mismatch_blocks(tmp_path):
    source = tmp_path / "EURUSD_M15.parquet"
    source.write_bytes(b"canonical-mt5-fixture")
    frames = _frames()
    result = build_mt5_operational_snapshot(
        frames,
        pd.Timestamp("2024-01-01 07:00", tz="UTC"),
        required_tfs=tuple(frames),
        source_files={"M15": str(source)},
        generator_commit="abc123",
    )
    assert result["provenance"]["status"] == "PASS"
    assert result["source_hashes"]["M15"] == result["source_artifacts"][0]["sha256"]

    bad = build_mt5_operational_snapshot(
        frames,
        pd.Timestamp("2024-01-01 07:00", tz="UTC"),
        required_tfs=tuple(frames),
        source_files={"M15": str(source)},
        source_hashes={"M15": "wrong"},
        generator_commit="abc123",
    )
    assert bad["status"] == "BLOCKED"
    assert "M15:hash_mismatch" in bad["provenance"]["errors"]


def test_future_rows_do_not_change_operational_snapshot_at_t():
    t = pd.Timestamp("2024-01-01 04:00", tz="UTC")
    base = _frames()
    before = build_mt5_operational_snapshot(base, t, generator_commit="abc123")
    extended = {tf: pd.concat([df, _frame("2024-01-02", n=2)], ignore_index=True) for tf, df in base.items()}
    after = build_mt5_operational_snapshot(extended, t, generator_commit="abc123")
    assert before == after
    json.dumps(after, sort_keys=True, allow_nan=False)


def test_object_projection_is_frozen_at_decision_time():
    frames = _frames()
    t = pd.Timestamp("2024-01-01 03:00", tz="UTC")
    state = build_object_market_state(frames, t, symbol="EURUSD")
    projection = state.objects_existing_at(t)
    assert all(obj.creation_time <= t for obj in projection)
    assert all(obj.state in set(ObjectState) for obj in projection)
