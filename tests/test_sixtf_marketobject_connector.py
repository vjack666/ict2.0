from __future__ import annotations

import pandas as pd

from engine.lineage_hierarchy import LineageStatus
from engine.market_object import ObjectType
from engine.sixtf_marketobject_connector import (
    SIX_TFS,
    build_sixtf_episodes,
    build_sixtf_market_state,
)
from scripts.audit.run_sixtf_marketobject_connector import run_window


def _frame(start: str, periods: int, freq: str, step: float) -> pd.DataFrame:
    times = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    rows = []
    value = 1.1000
    for i, ts in enumerate(times):
        opened = value
        closed = value + step + (0.00001 * (i % 3))
        high = max(opened, closed) + 0.0002
        low = min(opened, closed) - 0.0002
        rows.append(
            {
                "time": ts,
                "open": opened,
                "high": high,
                "low": low,
                "close": closed,
                "volume": 100.0 + i,
            }
        )
        value = closed
    return pd.DataFrame(rows)


def _frames(periods: int = 80) -> dict[str, pd.DataFrame]:
    return {
        "D1": _frame("2026-01-01T00:00:00Z", 20, "1D", 0.0005),
        "H4": _frame("2026-01-01T04:00:00Z", 60, "4h", 0.00035),
        "H1": _frame("2026-01-01T01:00:00Z", periods, "1h", 0.00025),
        "M15": _frame("2026-01-01T00:15:00Z", periods * 4, "15min", 0.00012),
        "M5": _frame("2026-01-01T00:05:00Z", periods * 12, "5min", 0.00008),
        "M1": _frame("2026-01-01T00:01:00Z", periods * 60, "1min", 0.00003),
    }


def _signature(artifact: dict) -> list[tuple[str, str, str, str | None]]:
    return [
        (obj.id, obj.origin_tf, obj.type.value, obj.parent_object)
        for obj in sorted(artifact["objects"].values(), key=lambda item: item.id)
    ]


def test_connector_builds_six_tf_marketobjects_with_valid_lineage():
    decision_time = pd.Timestamp("2026-01-05T12:00:00Z")
    artifact = build_sixtf_market_state(_frames(), decision_time)

    objects = artifact["objects"]
    assert {obj.origin_tf for obj in objects.values()} == set(SIX_TFS)
    assert artifact["lineage"].status is LineageStatus.VALID
    assert artifact["lineage_summary"]["six_tfs_complete"] is True
    assert artifact["lineage_summary"]["tfs_present"] == ["D1", "H1", "H4", "M1", "M15", "M5"]
    assert any(obj.type is ObjectType.FVG and obj.origin_tf == "M15" for obj in objects.values())
    assert any(obj.type is ObjectType.BOS and obj.origin_tf == "M5" for obj in objects.values())
    assert any(obj.type is ObjectType.DISPLACEMENT and obj.origin_tf == "M1" for obj in objects.values())


def test_connector_feeds_setup_builder_and_episodes():
    decision_time = pd.Timestamp("2026-01-05T12:00:00Z")
    artifact = build_sixtf_episodes(_frames(), decision_time)

    assert artifact["status"] == "PASS"
    assert artifact["setup_count"] >= 1
    assert len(artifact["episodes"]) >= 1
    episode = artifact["episodes"][0]
    assert episode["status"] == "ACCEPTED"
    assert set(artifact["lineage_summary"]["provenance_by_tf"]) == set(SIX_TFS)
    assert "M1" in episode["component_tfs"].values()


def test_connector_full_prefix_is_literal_for_visible_objects():
    frames = _frames(periods=90)
    decision_time = pd.Timestamp("2026-01-05T12:00:00Z")
    full = build_sixtf_market_state(frames, decision_time)
    prefix_frames = {
        tf: frame.loc[pd.to_datetime(frame["time"], utc=True) <= decision_time].copy()
        for tf, frame in frames.items()
    }
    prefix = build_sixtf_market_state(prefix_frames, decision_time)

    assert _signature(full) == _signature(prefix)
    assert full["lineage_summary"] == prefix["lineage_summary"]


def test_connector_fails_closed_when_a_layer_is_missing():
    frames = _frames()
    frames["M1"] = frames["M1"].iloc[0:0].copy()

    try:
        build_sixtf_market_state(frames, pd.Timestamp("2026-01-05T12:00:00Z"))
    except ValueError as exc:
        assert "MISSING_CLOSED_LAYER:M1" in str(exc)
    else:
        raise AssertionError("expected missing M1 to fail closed")


def test_window_runner_passes_full_prefix_over_multiple_decisions(tmp_path, monkeypatch):
    from scripts.audit import run_sixtf_marketobject_connector as runner

    monkeypatch.setattr(runner, "load_frames", lambda *args, **kwargs: _frames(periods=120))
    output = tmp_path / "window.json"
    report = run_window(
        data_dir=tmp_path,
        start_time="2026-01-03T00:00:00Z",
        end_time="2026-01-03T12:00:00Z",
        decisions=6,
        step_minutes=60,
        output=output,
    )

    assert report["status"] == "PASS"
    assert report["window_gates"]["full_prefix_all_pass"] is True
    assert report["window_gates"]["all_lineage_valid"] is True
    assert report["window_gates"]["all_six_tfs_complete"] is True
    assert report["aggregates"]["episode_count"] >= 1
    assert report["aggregates"]["rejection_count"] >= 1
    assert output.exists()
