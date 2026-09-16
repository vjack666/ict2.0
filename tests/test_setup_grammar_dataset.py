from __future__ import annotations

from scripts.lab.experiments.materialize_setup_grammar_dataset_v1 import materialize_row


def _row(*, context_bucket="ALIGNED", direction=1, stages=None):
    if stages is None:
        stages = ["LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE", "FVG", "RETEST"]
    return {
        "event_id": "row-1",
        "event_time": "2026-09-15T12:00:00+00:00",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "split": "DESIGN",
        "direction": direction,
        "sequence_depth": len(stages),
        "structure_mode": "lite",
        "context_bucket": context_bucket,
        "label_end_6": "continuation",
        "features_at_t": {
            "constraints": {
                "allow_long": direction > 0,
                "allow_short": direction < 0,
                "direction_hint": "BULLISH" if direction > 0 else "BEARISH",
            },
            "context_inputs": {
                "d1_bias": "BULLISH" if direction > 0 else "BEARISH",
                "h1_alignment": context_bucket,
                "h4_location": "DISCOUNT" if direction > 0 else "PREMIUM",
                "sequence_direction": direction,
            },
            "context_layers": {},
            "sequence": stages,
        },
        "_source_file": "fixture.jsonl",
    }


def test_materialize_complete_local_grammar_without_trade_authority():
    out = materialize_row(_row())
    labels = out["grammar_labels"]
    assert labels["htf_narrative"] == "HTF_OK"
    assert labels["po3_phase"] == "CHAIN_COMPLETE"
    assert labels["liquidity_sweep"] == "SWEEP_VALID"
    assert labels["pd_array_zone"] == "USABLE_UNGRADED"
    assert labels["retest_entry"] == "RETESTED"
    assert labels["poi_quality"] == "T2_CANDIDATE_UNVERIFIED"
    assert labels["setup_decision"] == "ABSTAIN"
    assert labels["exec_tf_integrity"] == "MISSING_EXEC_TF_REPLAY"
    assert out["can_trade"] is False
    assert out["entry_authorized"] is False


def test_materialize_rejects_htf_conflict_before_zone_quality():
    out = materialize_row(_row(context_bucket="AGAINST"))
    labels = out["grammar_labels"]
    assert labels["htf_narrative"] == "HTF_CONFLICT"
    assert labels["setup_decision"] == "REJECT"
    assert labels["weak_link"] == "htf_narrative"


def test_materialize_marks_missing_pd_array_and_retest_as_explicit_gap():
    out = materialize_row(_row(stages=["LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE"]))
    labels = out["grammar_labels"]
    assert labels["po3_phase"] == "D_CONFIRMED"
    assert labels["pd_array_zone"] == "NO_ZONE"
    assert labels["retest_entry"] == "MISSING_ZONE_FEATURE"
    assert "PD_ARRAY_ZONE_NOT_MATERIALIZED" in out["diagnostics"]
