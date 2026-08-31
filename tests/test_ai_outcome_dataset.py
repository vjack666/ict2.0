"""Pruebas focales del materializador causal de outcomes IA."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts.lab.experiments.ai_outcome_dataset import (
    CONTRACT_VERSION,
    OutcomeDatasetError,
    TrainingEligibilityError,
    build_snapshot_manifest,
    materialize_outcome_rows,
    write_jsonl,
)


def _features(direction: int = 1, *, observed_time: str | None = None) -> dict:
    values = {
        "sequence": ["LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE"],
        "sequence_depth": 4,
        "context_inputs": {
            "sequence_direction": direction,
            "d1_bias": "BULLISH" if direction == 1 else "BEARISH",
            "h4_location": "DISCOUNT" if direction == 1 else "PREMIUM",
            "h1_alignment": "ALIGNED",
        },
    }
    if observed_time is not None:
        values["observed_time"] = observed_time
    return values


def _fixtures(*, outcomes=("TP", "SL", "OPEN"), horizon=2):
    times = [f"2024-01-01T0{i}:00:00+00:00" for i in range(6)]
    candles = [
        {"index": i, "time": t, "open": 1.0 + i * 0.001, "high": 1.01 + i * 0.001, "low": 0.99 + i * 0.001, "close": 1.0 + i * 0.001}
        for i, t in enumerate(times)
    ]
    episodes = []
    trades = []
    for i, outcome in enumerate(outcomes):
        episode_id = f"EP_{i}"
        episodes.append({
            "episode_id": episode_id,
            "status": "ACCEPTED",
            "symbol": "TEST",
            "decision_time": times[i],
            "direction": 1,
            "sequence_depth": 4,
            "features_at_t": _features(),
        })
        trade = {
            "id": f"TRADE_{i}",
            "entry_index": i,
            "entry_time": times[i],
            "direction": "bullish",
            "outcome": outcome,
        }
        if outcome in {"TP", "SL"}:
            trade["exit_index"] = i + 1
            trade["exit_time"] = times[i + 1]
        trades.append(trade)
    funnel = {
        "contract_version": "EPISODES_FUNNEL_V1",
        "generator_commit": "a" * 40,
        "provenance": {"source": "synthetic-causal-fixture"},
        "aggregated_status": "PASS",
        "gates": {f"E{i}": "PASS" for i in range(6)},
        "full_prefix": {"prefix_matches_full": True},
        "episodes": episodes,
    }
    backtest = {
        "schema_version": "1.0",
        "symbol": "TEST",
        "timeframe": "H1",
        "candles": candles,
        "events": [],
        "trades": trades,
        "metadata": {
            "causal": True,
            "legacy_backtest": False,
            "promotion_authorized": False,
            "outcome": {"horizon_bars": horizon},
        },
    }
    a7 = {
        "gate": "A7",
        "aggregated_status": "PASS",
        "aggregated_findings": 0,
        "provenance_source": {
            "declared_status": "PASS",
            "license_and_permitted_use": "AUTHORIZED",
            "execution_verified": True,
            "source_provenance_complete": True,
        },
    }
    return funnel, backtest, a7


def _eligible_gate(result):
    return {"status": "PASS", "verdict": "TRAINING_ELIGIBLE", "dataset_hash": result.dataset_hash}


def test_labels_come_only_from_canonical_backtest_outcome_and_are_temporal():
    funnel, backtest, a7 = _fixtures()
    provisional = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7, research_gate=_eligible_gate(provisional))

    assert [row["label"] for row in result.rows] == ["continuation", "reversal", "failure"]
    assert [row["label_end_2"] for row in result.rows] == ["continuation", "reversal", "failure"]
    assert {row["split"] for row in result.rows} == {"HOLDOUT"}
    assert all(row["can_trade"] is False for row in result.rows)
    assert all(row["label_available_time"] > row["event_time"] for row in result.rows)
    assert all("label" not in row["features_at_t"] for row in result.rows)


def test_a7_source_provenance_blocked_never_becomes_training_eligible():
    funnel, backtest, a7 = _fixtures(outcomes=("TP",))
    a7["provenance_source"]["declared_status"] = "BLOCKED"
    a7["provenance_source"]["license_and_permitted_use"] = "UNKNOWN"
    provisional = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7, research_gate=_eligible_gate(provisional))

    assert result.rows
    assert result.status == "BLOCKED"
    assert result.training_eligible is False
    assert "A7_SOURCE_PROVENANCE_BLOCKED" in result.diagnostics
    assert "A7_LICENSE_OR_PERMITTED_USE_UNKNOWN" in result.diagnostics


def test_future_time_inside_features_is_rejected():
    funnel, backtest, a7 = _fixtures(outcomes=("TP",))
    funnel["episodes"][0]["features_at_t"] = _features(observed_time="2024-01-01T00:01:00+00:00")
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    assert any("ROW_REJECTED:EP_0: features_at_t contiene tiempo futuro" in item for item in result.diagnostics)
    assert not result.rows


def test_future_or_label_fields_inside_features_are_rejected():
    funnel, backtest, a7 = _fixtures(outcomes=("TP",))
    funnel["episodes"][0]["features_at_t"]["outcome"] = "TP"
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    assert any("campo futuro/prohibido" in item for item in result.diagnostics)
    assert result.rows == ()


def test_open_is_not_failure_when_the_file_does_not_cover_full_horizon():
    funnel, backtest, a7 = _fixtures(outcomes=("OPEN",), horizon=10)
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    assert not result.rows
    assert any("INSUFFICIENT_FUTURE_HORIZON" in item for item in result.diagnostics)


def test_invalid_outcome_and_ambiguous_trade_are_fail_closed():
    funnel, backtest, a7 = _fixtures(outcomes=("INVALID",))
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    assert any("BACKTEST_OUTCOME_INVALID" in item for item in result.diagnostics)
    funnel, backtest, a7 = _fixtures(outcomes=("TP",))
    backtest["trades"].append(deepcopy(backtest["trades"][0]))
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    assert any("BACKTEST_TRADE_AMBIGUOUS" in item for item in result.diagnostics)


def test_current_scientific_gate_is_required_even_when_rows_are_mechanically_valid():
    funnel, backtest, a7 = _fixtures(outcomes=("TP",))
    result = materialize_outcome_rows(
        funnel,
        backtest,
        a7_report=a7,
        research_gate={"status": "PASS", "verdict": "OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE"},
    )
    assert result.rows
    assert result.status == "BLOCKED"
    assert "RESEARCH_GATE_VERDICT_OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE" in result.diagnostics


def test_missing_features_is_an_exact_row_diagnostic():
    funnel, backtest, a7 = _fixtures(outcomes=("TP",))
    del funnel["episodes"][0]["features_at_t"]
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    assert result.rows == ()
    assert "ROW_REJECTED:EP_0: MISSING_FEATURES_AT_T" in result.diagnostics


def test_write_jsonl_is_deterministic_and_snapshot_manifest_stays_fail_closed(tmp_path):
    funnel, backtest, a7 = _fixtures(outcomes=("TP",))
    result = materialize_outcome_rows(funnel, backtest, a7_report=a7)
    path = write_jsonl(result, tmp_path / "outcomes.jsonl")
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["contract_version"] == CONTRACT_VERSION
    with pytest.raises(TrainingEligibilityError, match="no se puede crear manifest"):
        build_snapshot_manifest(result, path, experiment_id="EXP", code_commit="a" * 40, artifact_paths=["x.json"])
