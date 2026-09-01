from __future__ import annotations

from copy import deepcopy

import pytest

from backtest.schema import MTFReplayArtifact, logical_checksum, validate_mtf_replay


def _artifact() -> dict:
    payload = MTFReplayArtifact(
        run_metadata={"symbol": "EURUSD"},
        profiles=[{"profile_id": "INTRADAY_H4_M15"}],
        candles_by_tf={
            "H4": [
                {
                    "index": 0,
                    "tf": "H4",
                    "observation_time": "2024-01-01T04:00:00+00:00",
                    "open": 1.0,
                    "high": 1.2,
                    "low": 0.9,
                    "close": 1.1,
                }
            ]
        },
        timeline=[
            {
                "id": "TICK-0",
                "observation_time": "2024-01-01T04:00:00+00:00",
                "authority_tf": "H4",
                "parent_ids": ["DELTA-0"],
            }
        ],
        state_deltas=[
            {
                "id": "DELTA-0",
                "observation_time": "2024-01-01T04:00:00+00:00",
                "authority_tf": "H4",
                "parent_ids": [],
            }
        ],
    ).to_dict()
    validate_mtf_replay(payload)
    return payload


def test_schema_20_accepts_safe_artifact_and_stable_checksum():
    payload = _artifact()
    assert payload["checksum"] == logical_checksum(payload)
    changed = deepcopy(payload)
    changed["generated_at"] = "volatile"
    assert logical_checksum(changed) == payload["checksum"]


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda p: p["timeline"].append(deepcopy(p["timeline"][0])), "duplicate"),
        (lambda p: p["timeline"][0].update(observation_time="bad"), "invalid observation"),
        (lambda p: p["timeline"][0].update(parent_ids=["ORPHAN"]), "broken lineage"),
        (lambda p: p["policy"].update(can_trade=True), "unsafe policy"),
    ],
)
def test_schema_20_fails_closed(mutation, match):
    payload = _artifact()
    mutation(payload)
    payload["checksum"] = logical_checksum(payload)
    with pytest.raises(ValueError, match=match):
        validate_mtf_replay(payload)


def test_schema_20_rejects_multinode_cycle():
    payload = _artifact()
    payload["timeline"][0]["parent_ids"] = ["DELTA-0"]
    payload["state_deltas"][0]["parent_ids"] = ["TICK-0"]
    payload["checksum"] = logical_checksum(payload)
    with pytest.raises(ValueError, match="cyclic lineage"):
        validate_mtf_replay(payload)


def test_schema_10_remains_distinct_and_compatible():
    from backtest.schema import VisualBacktest, validate_visual_backtest

    payload = VisualBacktest("EURUSD", "H1", [], [], []).to_dict()
    validate_visual_backtest(payload)
    assert payload["schema_version"] == "1.0"
