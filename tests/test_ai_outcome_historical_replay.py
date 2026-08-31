"""Focused tests for the LOCAL_ONLY AI-outcome historical replay exporter."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.schema import VisualBacktest, validate_visual_backtest
from scripts.lab.experiments import ai_outcome_historical_replay as exporter


def _frame(timeframe: str, rows: int = 80) -> pd.DataFrame:
    freq = {"D1": "D", "H4": "4h", "H1": "h"}[timeframe]
    index = np.arange(rows)
    close = 1.10 + np.sin(index / 4.0) * 0.004 + index * 0.00001
    return pd.DataFrame({
        "time": pd.date_range("2006-01-01", periods=rows, freq=freq),
        "open": close,
        "high": close + 0.001,
        "low": close - 0.001,
        "close": close,
    })


def _dataset(tmp_path: Path) -> Path:
    root = tmp_path / "eurusd_dukascopy_20y"
    root.mkdir()
    for timeframe in exporter.TIMEFRAMES:
        _frame(timeframe).to_csv(root / f"EURUSD_{timeframe}.csv", index=False)
    return root


def test_source_boundary_requires_exact_three_csvs(tmp_path):
    root = _dataset(tmp_path)
    (root / "EURUSD_M5.csv").write_text("time,open,high,low,close\n", encoding="utf-8")
    with pytest.raises(exporter.HistoricalReplayError, match="SOURCE_BOUNDARY_INVALID"):
        exporter.build_historical_replay(dataset_dir=root)


def test_missing_source_and_mt5_source_fail_closed(tmp_path):
    root = _dataset(tmp_path)
    (root / "EURUSD_H4.csv").unlink()
    with pytest.raises(exporter.HistoricalReplayError, match="SOURCE_BOUNDARY_INVALID"):
        exporter.build_historical_replay(dataset_dir=root)

    raw_root = tmp_path / "data" / "raw"
    raw_root.mkdir(parents=True)
    for timeframe in exporter.TIMEFRAMES:
        _frame(timeframe).to_csv(raw_root / f"EURUSD_{timeframe}.csv", index=False)
    with pytest.raises(exporter.HistoricalReplayError, match="MT5_SOURCE_REJECTED"):
        exporter.build_historical_replay(dataset_dir=raw_root)


def test_parquet_under_candidate_source_is_rejected(tmp_path):
    root = _dataset(tmp_path)
    (root / "EURUSD_M5.parquet").write_bytes(b"not an input")
    with pytest.raises(exporter.HistoricalReplayError, match="MT5_SOURCE_REJECTED"):
        exporter.build_historical_replay(dataset_dir=root)


def test_export_uses_fixed_h1_replay_and_fail_closed_metadata(tmp_path, monkeypatch):
    root = _dataset(tmp_path)
    captured = {}

    def fake_replay(frames, config):
        captured["frames"] = frames
        captured["config"] = config
        return VisualBacktest(
            symbol="EURUSD",
            timeframe="H1",
            candles=[{"index": 0, "time": "2006-01-01T00:00:00+00:00", "open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1}],
            events=[],
            trades=[],
        )

    monkeypatch.setattr(exporter, "run_visual_replay", fake_replay)
    payload = exporter.build_historical_replay(dataset_dir=root)

    assert tuple(captured["frames"]) == exporter.TIMEFRAMES
    assert captured["config"].timeframe == "H1"
    assert captured["config"].timeframes == exporter.TIMEFRAMES
    assert captured["config"].execution_tf == "H1"
    assert captured["config"].use_multitf_context is True
    assert captured["config"].outcome.horizon_bars == 6
    assert payload["can_trade"] is False
    assert payload["promotion_authorized"] is False
    assert payload["causal"] is True
    assert payload["status"] == "BLOCKED"
    assert payload["metadata"]["outcome"]["horizon_bars"] == 6
    assert payload["metadata"]["funnel_episodes"]["derived"] is False
    assert payload["provenance"]["files"]["H1"]["sha256"]
    validate_visual_backtest(payload)


def test_real_small_fixture_runs_canonical_replay_and_writes_json(tmp_path):
    root = _dataset(tmp_path)
    output = tmp_path / "visual_backtest.json"
    payload = exporter.export_historical_replay(output, dataset_dir=root)
    assert output.exists()
    assert payload["timeframe"] == "H1"
    assert payload["metadata"]["source_timeframes"] == ["D1", "H4", "H1"]
    assert all(trade.get("execution_tf") == "H1" for trade in payload["trades"])
    validate_visual_backtest(json.loads(output.read_text(encoding="utf-8")))


def test_exporter_has_no_operational_or_legacy_backtest_loader():
    source = Path(exporter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all("ict_backtest" not in ast.unparse(node) for node in imports)
    assert "load_raw_frames" not in source
