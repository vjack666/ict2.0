"""Pruebas estructurales del materializador IA por lotes.

Las fixtures son contractuales y pequeñas: no representan datos de mercado ni
se usan para afirmar un edge. Solo verifican streaming, particionado, vínculo
causal con el backtest y fail-closed de los gates.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.lab.experiments.ai_outcome_batch_materializer import (
    BatchMaterializationError,
    materialize_in_batches,
)


def _features(direction: int = 1) -> dict:
    return {
        "sequence": ["SWEEP", "DISPLACEMENT", "STRUCTURE"],
        "sequence_depth": 3,
        "context_inputs": {
            "sequence_direction": direction,
            "d1_bias": "BULLISH" if direction == 1 else "BEARISH",
            "h4_location": "DISCOUNT" if direction == 1 else "PREMIUM",
            "h1_alignment": "ALIGNED",
        },
    }


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    times = [f"2025-01-01T0{i}:00:00+00:00" for i in range(8)]
    backtest = {
        "schema_version": "1.0",
        "symbol": "FIXTURE",
        "timeframe": "H1",
        "candles": [{"index": i, "time": value} for i, value in enumerate(times)],
        "events": [],
        "trades": [
            {
                "id": "TRADE_0",
                "entry_index": 0,
                "entry_time": times[0],
                "direction": "LONG",
                "outcome": "TP",
                "exit_index": 1,
                "exit_time": times[1],
            },
            {
                "id": "TRADE_1",
                "entry_index": 2,
                "entry_time": times[2],
                "direction": "LONG",
                "outcome": "SL",
                "exit_index": 3,
                "exit_time": times[3],
            },
        ],
        "metadata": {
            "causal": True,
            "legacy_backtest": False,
            "promotion_authorized": False,
            "outcome": {"horizon_bars": 1},
            "provenance": {"status": "BLOCKED", "license_and_permitted_use": "UNKNOWN"},
        },
    }
    funnel = {
        "contract_version": "EPISODES_FUNNEL_V1",
        "aggregated_status": "PASS",
        "gates": {"E0": "PASS", "E1": "PASS"},
        "full_prefix": {"prefix_matches_full": True},
        "generator_commit": "a" * 40,
        "provenance": {"status": "BLOCKED", "license_and_permitted_use": "UNKNOWN"},
        "episodes": [
            {
                "episode_id": "EP_0",
                "status": "ACCEPTED",
                "symbol": "FIXTURE",
                "decision_time": times[0],
                "direction": 1,
                "features_at_t": _features(),
            },
            {
                "episode_id": "EP_1",
                "status": "ACCEPTED",
                "symbol": "FIXTURE",
                "decision_time": times[2],
                "direction": 1,
                "features_at_t": _features(),
            },
        ],
    }
    funnel_path = tmp_path / "funnel.json"
    backtest_path = tmp_path / "backtest.json"
    funnel_path.write_text(json.dumps(funnel), encoding="utf-8")
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    return funnel_path, backtest_path


def test_materializer_partitions_and_bounds_memory(tmp_path):
    funnel, backtest = _write_fixture(tmp_path)
    manifest = materialize_in_batches(
        funnel_path=funnel,
        backtest_path=backtest,
        output_dir=tmp_path / "dataset",
        partition="month",
        max_episodes_per_batch=1,
    )

    assert manifest["status"] == "BLOCKED"
    assert manifest["training_eligible"] is False
    assert manifest["can_trade"] is False
    assert manifest["partitioning"]["full_backtest_arrays_loaded"] is False
    assert manifest["counts"]["candles_indexed"] == 8
    assert manifest["counts"]["batches"] == 2
    assert manifest["counts"]["rows"] == 2
    assert manifest["temporal_splits"]["counts"] == {"HOLDOUT": 2}

    rows = []
    for path in sorted((tmp_path / "dataset" / "partitions").rglob("*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    assert [row["label"] for row in rows] == ["continuation", "reversal"]
    assert all(row["can_trade"] is False for row in rows)


def test_existing_output_is_never_overwritten(tmp_path):
    funnel, backtest = _write_fixture(tmp_path)
    output = tmp_path / "dataset"
    output.mkdir()
    with pytest.raises(BatchMaterializationError, match="OUTPUT_EXISTS"):
        materialize_in_batches(funnel_path=funnel, backtest_path=backtest, output_dir=output)


def test_bad_candle_index_fails_closed(tmp_path):
    funnel, backtest = _write_fixture(tmp_path)
    payload = json.loads(backtest.read_text(encoding="utf-8"))
    payload["candles"][1]["index"] = 99
    backtest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BatchMaterializationError, match="CANDLE_INDEX_NOT_CONTIGUOUS"):
        materialize_in_batches(
            funnel_path=funnel,
            backtest_path=backtest,
            output_dir=tmp_path / "dataset",
        )


def test_ambiguous_trade_is_reported_not_silently_dropped(tmp_path):
    funnel, backtest = _write_fixture(tmp_path)
    payload = json.loads(backtest.read_text(encoding="utf-8"))
    duplicate = deepcopy(payload["trades"][0])
    duplicate["id"] = "TRADE_DUPLICATE"
    payload["trades"].append(duplicate)
    backtest.write_text(json.dumps(payload), encoding="utf-8")

    manifest = materialize_in_batches(
        funnel_path=funnel,
        backtest_path=backtest,
        output_dir=tmp_path / "dataset",
        max_episodes_per_batch=256,
    )

    assert manifest["status"] == "BLOCKED"
    assert manifest["counts"]["rows"] == 1
    diagnostics = (tmp_path / "dataset" / "diagnostics.jsonl").read_text(encoding="utf-8")
    assert "BACKTEST_TRADE_AMBIGUOUS" in diagnostics
