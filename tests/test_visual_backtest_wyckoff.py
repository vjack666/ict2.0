"""Causal Wyckoff timeline tests, including FULL-vs-PREFIX identity."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.replay import _canonical_frame, load_raw_frames
from backtest.schema import json_safe
from backtest.wyckoff_timeline import FSM_CONTRACT, build_wyckoff_timeline
from engine.Wyckoff import build_wyckoff_snapshot
from engine.mtf_navigation import MTFNavigator, NavigatorConfig


def _ohlc(start: str, periods: int, freq: str, step: float = 0.0002) -> pd.DataFrame:
    index = np.arange(periods, dtype=float)
    close = 1.08 + np.sin(index / 2.7) * 0.002 + index * step
    return pd.DataFrame({
        "time": pd.date_range(start, periods=periods, freq=freq, tz="UTC"),
        "open": close - 0.0002,
        "high": close + 0.0008,
        "low": close - 0.0008,
        "close": close,
        "tick_volume": 100 + index * 3,
    })


def _frames() -> dict[str, pd.DataFrame]:
    raw = {
        "D1": _ohlc("2023-12-01", 40, "1D"),
        "H4": _ohlc("2023-12-25", 60, "4h"),
        "H1": _ohlc("2023-12-28", 120, "1h"),
        "M15": _ohlc("2024-01-01", 40, "15min"),
    }
    return {
        tf: _canonical_frame(frame, name=tf, timeframe=tf, timestamp_semantics="open")
        for tf, frame in raw.items()
    }


def test_full_vs_prefix_timeline_is_identical_at_every_visible_cut():
    frames = _frames()
    full_timeline, full_events = build_wyckoff_timeline(
        frames, main_tf="M15", authority_tf="H1",
        visible_start_index=12, visible_end_index=20,
        layers=("D1", "H4", "H1", "M15"),
    )
    event_cuts = {
        12 + int(event["first_seen_index"])
        for event in full_events
        if 12 <= 12 + int(event["first_seen_index"]) <= 20
    }
    cuts = sorted({12, 16, 20, *(list(event_cuts)[:1])})
    for cut in cuts:
        cut_time = pd.Timestamp(frames["M15"].iloc[cut]["time"])
        prefixes = {
            tf: frame.loc[pd.to_datetime(frame["time"], utc=True) <= cut_time].copy().reset_index(drop=True)
            for tf, frame in frames.items()
        }
        prefix_timeline, prefix_events = build_wyckoff_timeline(
            prefixes, main_tf="M15", authority_tf="H1",
            visible_start_index=12, visible_end_index=cut,
            layers=("D1", "H4", "H1", "M15"),
        )
        length = cut - 12 + 1
        assert full_timeline[:length] == prefix_timeline
        assert [event for event in full_events if event["first_seen_index"] < length] == prefix_events
    for point in full_timeline:
        decision = pd.Timestamp(point["decision_time"])
        assert all(pd.Timestamp(value) <= decision for value in point["asof_by_tf"].values() if value)


def test_snapshot_is_engine_output_plus_only_explicit_contract_disclosure():
    frames = _frames()
    timeline, events = build_wyckoff_timeline(
        frames, main_tf="M15", authority_tf="H1",
        visible_start_index=16, visible_end_index=16,
        layers=("D1", "H4", "H1", "M15"),
    )
    point = timeline[0]
    decision = pd.Timestamp(point["decision_time"])
    prefixes = {
        tf: frame.loc[pd.to_datetime(frame["time"], utc=True) <= decision].copy().reset_index(drop=True)
        for tf, frame in frames.items()
    }
    context_frames = {tf: prefixes[tf] for tf in ("D1", "H4", "H1")}
    context = MTFNavigator(context_frames, NavigatorConfig(precompute_sequences=False)).navigate(
        decision, exec_tf="H1"
    )
    expected = json_safe(build_wyckoff_snapshot(
        prefixes, decision, context_state=context, authority_tf="H1",
        layers=("D1", "H4", "H1", "M15"),
    ).to_dict())
    actual = dict(point["wyckoff"])
    assert actual.pop("range_id") is None
    assert actual.pop("episode_id") is None
    assert actual.pop("fsm_contract") == FSM_CONTRACT
    assert actual == expected
    assert [event["id"] for event in events] == [event["id"] for event in events]


def test_event_wrappers_are_deterministic_and_preserve_engine_identity():
    frames = _frames()
    first = build_wyckoff_timeline(
        frames, main_tf="M15", authority_tf="H1",
        visible_start_index=10, visible_end_index=20,
        layers=("D1", "H4", "H1", "M15"),
    )
    second = build_wyckoff_timeline(
        frames, main_tf="M15", authority_tf="H1",
        visible_start_index=10, visible_end_index=20,
        layers=("D1", "H4", "H1", "M15"),
    )
    assert first == second
    for event in first[1]:
        assert event["id"].startswith("WY_")
        assert event["engine_event_id"]
        assert event["first_seen_decision_time"] >= event["event_time"]


@pytest.mark.skipif(not os.getenv("ICT_REAL_DATA_DIR"), reason="set ICT_REAL_DATA_DIR for the real-data PIT gate")
def test_real_eurusd_small_window_full_vs_prefix():
    frames = load_raw_frames(
        "EURUSD", ("D1", "H4", "H1", "M15", "M5", "M1"),
        data_dir=Path(os.environ["ICT_REAL_DATA_DIR"]),
        start="2026-08-17", end="2026-08-21", warmup_bars=200,
        timestamp_semantics="open",
    )
    start = int(frames["M15"].attrs["visible_start_index"])
    end = start + 3
    full = build_wyckoff_timeline(
        frames, main_tf="M15", authority_tf="H1",
        visible_start_index=start, visible_end_index=end,
        layers=("D1", "H4", "H1", "M15"),
    )
    cut = pd.Timestamp(frames["M15"].iloc[end]["time"])
    prefixes = {
        tf: frame.loc[pd.to_datetime(frame["time"], utc=True) <= cut].copy().reset_index(drop=True)
        for tf, frame in frames.items()
    }
    prefix = build_wyckoff_timeline(
        prefixes, main_tf="M15", authority_tf="H1",
        visible_start_index=start, visible_end_index=end,
        layers=("D1", "H4", "H1", "M15"),
    )
    assert full == prefix
