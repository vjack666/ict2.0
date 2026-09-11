from __future__ import annotations

from engine.mechanical_signal_publication import REQUIRED_GATES, evaluate_publication_gate


def _candidate():
    return {"status": "CANDIDATE_SETUP", "symbol": "EURUSD", "context_direction": "BEARISH", "decision_time": "2026-09-11T15:00:00+00:00"}


def _certificate():
    return {
        "gates": {gate: "PASS" for gate in REQUIRED_GATES},
        "direction_rule": "CANDIDATE_CONTEXT_DIRECTION_V1",
        "confirmed_definition": "PHASE2A_CHAIN_COMPLETE_CLOSED_M15_V1",
        "calibration": {"probability": .72, "fit_partition": "VALIDATION_ONLY", "oos_partition": "HOLDOUT_NEVER_USED_FOR_FIT", "brier": .18, "reliability_curve_hash": "a" * 64},
    }


def test_publication_fails_closed_for_each_independent_gate():
    for gate in REQUIRED_GATES:
        certificate = _certificate()
        certificate["gates"][gate] = "BLOCKED"
        result = evaluate_publication_gate(_candidate(), certificate)
        assert result["status"] == "BLOCKED"
        assert result["code"] == "PUBLICATION_GATES_BLOCKED"
        assert result["failed_gates"] == [gate]
        assert result["can_trade"] is False


def test_validated_contract_requires_calibration_and_bot_rechecks():
    result = evaluate_publication_gate(_candidate(), _certificate())
    assert result["status"] == "VALIDATED_MECHANICAL_SIGNAL"
    assert result["direction"] == "SELL"
    assert result["probability"] == .72
    assert result["confirmed"] is True
    assert result["can_trade"] is False
    assert "m15_stochastic_cross" in result["bot_rechecks_required"]


def test_probability_or_oos_evidence_cannot_be_a_score_in_disguise():
    cases = (("probability", "72%"), ("fit_partition", "TRAIN"), ("oos_partition", "OOS_USED_FOR_FIT"), ("brier", None), ("reliability_curve_hash", ""))
    for field, value in cases:
        certificate = _certificate()
        certificate["calibration"][field] = value
        result = evaluate_publication_gate(_candidate(), certificate)
        assert result["code"] == "CALIBRATION_EVIDENCE_INVALID"
        assert result["publication_authorized"] is False


def test_non_candidate_never_derives_a_direction_or_publication():
    result = evaluate_publication_gate({"status": "NO_SIGNAL"}, _certificate())
    assert result["status"] == "NO_SIGNAL"
    assert "direction" not in result
