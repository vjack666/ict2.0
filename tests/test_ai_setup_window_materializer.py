"""Tests exclusivos de la utilidad CAIO/Datos de ventanas y lotes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.lab.experiments.ai_setup_window_materializer import (
    SetupWindowError,
    Window,
    materialize_window,
    materialize_windows,
    parse_window_spec,
)


def _write_artifacts(root: Path, *, provenance_status: str = "BLOCKED") -> tuple[Path, Path]:
    funnel = root / "funnel.json"
    backtest = root / "backtest.json"
    funnel.write_text(json.dumps({
        "contract_version": "EPISODES_FUNNEL_V1",
        "aggregated_status": "PASS",
        "gates": {"E0": "PASS", "E1": "PASS", "causal_full_vs_prefix": "PASS"},
        "full_prefix": {"prefix_matches_full": True},
        "generator_commit": "abcdef1234567",
        "provenance": {"status": provenance_status, "provider": "Dukascopy"},
        "episodes": [{
            "episode_id": "EP_1",
            "status": "ACCEPTED",
            "symbol": "EURUSD",
            "decision_time": "2025-01-02T01:00:00+00:00",
            "direction": -1,
            "features_at_t": {
                "sequence": ["SWEEP", "DISPLACEMENT", "FVG"],
                "sequence_depth": 3,
                "context_inputs": {
                    "sequence_direction": -1,
                    "d1_bias": "UNKNOWN",
                    "h4_location": "UNKNOWN",
                    "h1_alignment": "NEUTRAL",
                },
            },
            "meta": {"backtest_signal_index": 7},
        }],
    }), encoding="utf-8")
    backtest.write_text(json.dumps({
        "schema_version": "1.0",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "metadata": {"causal": True, "outcome": {"horizon_bars": 2}},
        "provenance": {"status": provenance_status, "provider": "Dukascopy"},
        "candles": [
            {"index": 0, "time": "2025-01-02T00:00:00+00:00"},
            {"index": 1, "time": "2025-01-02T01:00:00+00:00"},
            {"index": 2, "time": "2025-01-02T02:00:00+00:00"},
            {"index": 3, "time": "2025-01-02T03:00:00+00:00"},
        ],
        "events": [],
        "signals": [],
        "trades": [{
            "id": "T_1", "signal_index": 7, "direction": "bearish",
            "entry_index": 1, "entry_time": "2025-01-02T01:00:00+00:00",
            "exit_index": 2, "exit_time": "2025-01-02T02:00:00+00:00", "outcome": "SL",
        }],
    }), encoding="utf-8")
    return funnel, backtest


def test_streaming_window_materializes_horizon_split_and_label(tmp_path):
    funnel, backtest = _write_artifacts(tmp_path)
    result = materialize_window(
        funnel, backtest,
        parse_window_spec("2025-01-01T00:00:00Z,2025-01-31T23:59:59Z"),
    )
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["label"] == "reversal"
    assert row["label_end_2"] == "reversal"
    assert row["horizon_bars"] == 2
    assert row["split"] == "HOLDOUT"
    assert row["event_time"] == "2025-01-02T01:00:00+00:00"
    assert row["can_trade"] is False


def test_materialize_windows_is_blocked_by_provenance_and_writes_summary(tmp_path):
    funnel, backtest = _write_artifacts(tmp_path)
    output = tmp_path / "rows.jsonl"
    summary = tmp_path / "rows.summary.json"
    result = materialize_windows(
        funnel, backtest,
        [Window(parse_window_spec("2025-01-01T00:00:00Z,2025-01-31T23:59:59Z").start,
                parse_window_spec("2025-01-01T00:00:00Z,2025-01-31T23:59:59Z").end)],
        output,
        batch_size=1,
        summary_path=summary,
    )
    assert result["status"] == "BLOCKED"
    assert result["materialization_status"] == "PASS"
    assert result["training_eligible"] is False
    assert result["can_trade"] is False
    assert result["provenance"]["status"] == "BLOCKED"
    assert output.read_text(encoding="utf-8").count("\n") == 1
    assert json.loads(summary.read_text(encoding="utf-8"))["horizon_bars"] == 2


def test_window_uses_decision_time_not_candle_range(tmp_path):
    funnel, backtest = _write_artifacts(tmp_path)
    result = materialize_window(
        funnel, backtest,
        parse_window_spec("2025-02-01T00:00:00Z,2025-02-28T23:59:59Z"),
    )
    assert result.rows == ()


def test_feature_future_field_is_rejected(tmp_path):
    funnel, backtest = _write_artifacts(tmp_path)
    payload = json.loads(funnel.read_text(encoding="utf-8"))
    payload["episodes"][0]["features_at_t"]["future_label"] = "reversal"
    funnel.write_text(json.dumps(payload), encoding="utf-8")
    result = materialize_window(
        funnel, backtest,
        parse_window_spec("2025-01-01T00:00:00Z,2025-01-31T23:59:59Z"),
    )
    assert result.rows == ()
    assert any("FUTURE_FEATURE_FIELD" in item for item in result.diagnostics)


def test_output_is_immutable_and_windows_are_required(tmp_path):
    funnel, backtest = _write_artifacts(tmp_path)
    output = tmp_path / "rows.jsonl"
    output.write_text("existing\n", encoding="utf-8")
    with pytest.raises(SetupWindowError, match="OUTPUT_EXISTS_NO_OVERWRITE"):
        materialize_windows(funnel, backtest, [parse_window_spec("2025-01-01,2025-01-31")], output)
    with pytest.raises(SetupWindowError, match="WINDOWS_REQUIRED"):
        materialize_windows(funnel, backtest, [], tmp_path / "other.jsonl")
