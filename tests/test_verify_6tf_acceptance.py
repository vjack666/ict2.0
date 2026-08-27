"""Tests for the real FULL/PREFIX acceptance comparison."""

from __future__ import annotations

from scripts.verify_6tf_acceptance import compare_full_prefix


def _payload(count: int = 3) -> dict:
    return {
        "schema_version": "1.2",
        "symbol": "TEST",
        "timeframe": "H1",
        "authority_tf": "H1",
        "market_state": [
            {
                "decision_time": f"2024-01-01T{index:02d}:00:00+00:00",
                "authority_tf": "H1",
                "entities": [],
                "terminal_entities": [],
                "delta": {"created": [], "transitioned": [], "terminal": []},
            }
            for index in range(count)
        ],
        "setups": [
            {
                "id": f"SETUP_{index}",
                "decision_time": f"2024-01-01T{index:02d}:00:00+00:00",
                "estado": "WAIT_D1",
            }
            for index in range(count)
        ],
        "candles": [{"bar_close_time": f"2024-01-01T{index:02d}:00:00+00:00"} for index in range(count)],
    }


def test_full_prefix_compares_overlapping_market_state_and_setup():
    result = compare_full_prefix(_payload(4), _payload(2))
    assert result["pass"] is True
    assert result["checked_snapshots"] == 2


def test_full_prefix_rejects_a_market_state_difference():
    full = _payload(3)
    prefix = _payload(2)
    prefix["market_state"][1]["delta"]["created"] = ["future-difference"]
    result = compare_full_prefix(full, prefix)
    assert result["pass"] is False
    assert "market_state" in result["reason"]
