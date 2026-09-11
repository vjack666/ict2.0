from __future__ import annotations

from copy import deepcopy

from engine.mechanical_signal_assessment import assess_mechanical_signal


def _snapshot() -> dict:
    return {
        "schema_version": "MT5_OPERATIONAL_SNAPSHOT_V1",
        "status": "READY",
        "policy": "OBSERVE_ONLY_NO_ORDER",
        "symbol": "EURUSD",
        "decision_time": "2026-09-11T15:00:00+00:00",
        "missing_timeframes": [],
        "can_trade": False,
        "entry_authorized": False,
        "context_state": {"layers": {
            "H4": {"structure_bias": "BEARISH"},
            "H1": {"structure_bias": "BEARISH"},
            "M15": {"displacement_recent": True},
        }},
        "daily_motor": {
            "direction": -1,
            "context": {"constraints": {"allow_short": True, "allow_long": False}},
            "ltf": {"zone_present": True, "retest_observed": True},
        },
        "micro_confirmation": {"confirmed": False, "diagnostic": "M5_M1_ONLY"},
        "m15_evidence": {"sweep": True, "displacement": True, "bos_or_choch": True, "fvg_or_ob": True, "retest": True,
                         "source": "closed_m15_fixture"},
    }


def test_each_frozen_chain_rejection_is_explicit():
    cases = (
        ("sweep", False, "NO_SIGNAL", "NO_SWEEP"),
        ("displacement", False, "NO_SIGNAL", "NO_DISPLACEMENT"),
        ("bos_or_choch", False, "NO_SIGNAL", "NO_BOS"),
        ("fvg_or_ob", False, "NO_SIGNAL", "NO_FVG_OR_OB"),
        ("retest", False, "NO_SIGNAL", "WAIT_RETEST"),
    )
    for field, value, status, code in cases:
        snapshot = _snapshot()
        snapshot["m15_evidence"][field] = value
        result = assess_mechanical_signal(snapshot)
        assert (result["status"], result["code"]) == (status, code)
        assert result["entry_authorized"] is False
        assert result["can_trade"] is False


def test_candidate_requires_all_closed_evidence_but_is_not_trade_authority():
    result = assess_mechanical_signal(_snapshot())
    assert result["status"] == "CANDIDATE_SETUP"
    assert result["context_direction"] == "BEARISH"
    assert result["entry_authorized"] is False
    assert result["publication"] == "DIAGNOSTIC_ONLY_NO_MECHANICAL_SNAPSHOT"
    assert "probability" not in result
    assert "confirmed" not in result


def test_htf_and_data_fail_closed_before_m15_chain():
    conflict = _snapshot()
    conflict["context_state"]["layers"]["H1"]["structure_bias"] = "MIXED"
    assert assess_mechanical_signal(conflict)["code"] == "HTF_CONFLICT"

    missing = _snapshot()
    missing["missing_timeframes"] = ["M15"]
    assert assess_mechanical_signal(missing)["code"] == "M15_DATA_UNAVAILABLE"

    unavailable = _snapshot()
    unavailable.pop("m15_evidence")
    result = assess_mechanical_signal(unavailable)
    assert (result["status"], result["code"]) == ("BLOCKED", "SWEEP_EVIDENCE_UNAVAILABLE")


def test_full_and_prefix_have_the_same_assessment_at_decision_time():
    prefix = _snapshot()
    full = deepcopy(prefix)
    full["future_unavailable_at_decision_time"] = {"time": "2026-09-11T15:15:00+00:00", "sweep": False}
    assert assess_mechanical_signal(full) == assess_mechanical_signal(prefix)
