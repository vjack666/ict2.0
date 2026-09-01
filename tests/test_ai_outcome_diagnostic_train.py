from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from runtime.ai_learning.diagnostic_training import (
    DiagnosticTrainingError,
    MIN_TOTAL_ROWS,
    run_diagnostic_training,
    write_diagnostic_artifact,
)


def _row(index: int, *, label: str | None = None) -> dict:
    context = ("ALIGNED", "NEUTRAL", "AGAINST")[index % 3]
    event_time = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
    available_time = event_time + timedelta(hours=1)
    return {
        "episode_id": f"EP_{index:04d}",
        "event_time": event_time.isoformat(),
        "direction": 1,
        "sequence_depth": 4 + index % 3,
        "features_at_t": {
            "sequence": ["STRUCTURE", "FVG"] if index % 2 else ["STRUCTURE"],
            "context_inputs": {
                "sequence_direction": 1,
                "context_bucket": context,
                "h1_alignment": context,
                "d1_bias": "BULLISH" if context == "ALIGNED" else "UNKNOWN",
                "h4_location": "DISCOUNT" if context == "ALIGNED" else "UNKNOWN",
            },
        },
        "label_end_6": label or ("continuation", "reversal", "failure")[index % 3],
        "label_available_time": available_time.isoformat(),
        "can_trade": False,
    }


def _write_rows(tmp_path, count: int = 1, *, labels: list[str] | None = None):
    path = tmp_path / "causal.jsonl"
    rows = [
        _row(index, label=labels[index] if labels else None)
        for index in range(count)
    ]
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_insufficient_jsonl_is_reported_without_fit_or_fabrication(tmp_path):
    source = _write_rows(tmp_path, 1, labels=["reversal"])

    result = run_diagnostic_training(source)

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "INSUFFICIENT_DATA"
    assert result["fit_executed"] is False
    assert result["input"]["rows"] == 1
    assert result["minimum_window"]["minimum_total_rows"] == MIN_TOTAL_ROWS == 50
    assert result["minimum_window"]["additional_rows_at_least"] == 49
    assert result["can_trade"] is False
    assert "model" not in result


def test_minimum_window_is_temporal_and_train_support_is_explicit(tmp_path):
    source = _write_rows(tmp_path, 60)

    result = run_diagnostic_training(source)

    window = result["minimum_window"]["earliest_qualifying_window"]
    assert window["rows_required"] == 50
    assert window["train_rows"] == 30
    assert window["validation_rows"] == 10
    assert window["test_rows"] == 10
    assert min(window["train_class_counts"].values()) >= 5


def test_sufficient_rows_use_the_real_classifier_and_stay_shadow_only(tmp_path):
    source = _write_rows(tmp_path, 60)

    result = run_diagnostic_training(source, code_commit="a" * 40)

    assert result["status"] == "DIAGNOSTIC_ONLY_COMPLETED"
    assert result["fit_executed"] is True
    assert result["metrics"]["model_training_executed"] is True
    assert result["metrics"]["train"]["rows"] == 36
    assert result["metrics"]["validation"]["rows"] == 12
    assert result["metrics"]["test_oos"]["rows"] == 12
    assert result["model"]["shadow_mode"] is True
    assert result["model"]["can_trade"] is False
    assert result["certified_snapshot"] is False
    assert result["scientific_training_eligible"] is False
    assert result["promotion_authorized"] is False
    assert result["can_trade"] is False
    assert result["training_plan"]["split"]["split_source"] == "diagnostic_configured_temporal"


def test_diagnostic_artifact_is_reproducible_and_immutable(tmp_path):
    source = _write_rows(tmp_path, 60)
    first = run_diagnostic_training(source, code_commit="b" * 40)
    second = run_diagnostic_training(source, code_commit="b" * 40)

    assert first == second
    destination = tmp_path / "diagnostic.json"
    write_diagnostic_artifact(first, destination)
    with pytest.raises(DiagnosticTrainingError, match="no se sobrescribe"):
        write_diagnostic_artifact(second, destination)
    on_disk = json.loads(destination.read_text(encoding="utf-8"))
    assert on_disk == first
    assert on_disk["artifact_hash"]


def test_future_feature_is_rejected_without_training(tmp_path):
    source = _write_rows(tmp_path, 60)
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    rows[0]["features_at_t"]["observed_time"] = "2020-01-02T00:00:00+00:00"
    source.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(DiagnosticTrainingError, match="tiempo futuro"):
        run_diagnostic_training(source)


def test_can_trade_true_is_rejected(tmp_path):
    source = _write_rows(tmp_path, 1)
    row = json.loads(source.read_text(encoding="utf-8"))
    row["can_trade"] = True
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(DiagnosticTrainingError, match="can_trade"):
        run_diagnostic_training(source)
