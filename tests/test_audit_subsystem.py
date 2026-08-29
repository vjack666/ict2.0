from audits.codigo.data_integrity import audit_ohlc
from audits.codigo.temporal import audit_events
from audits.codigo.funnel import (
    A7_REQUIRED_REPORT_METRICS,
    FunnelAudit,
    aggregate_a7_status,
    missing_a7_report_metrics,
)
from audits.codigo.gate import GateStatus

T0 = "2026-01-01T00:00:00+00:00"
T1 = "2026-01-01T01:00:00+00:00"
T2 = "2026-01-01T02:00:00+00:00"


def candle(i, o=1.1, h=1.2, l=1.0, c=1.15):
    return {"id": str(i), "time": i, "open": o, "high": h, "low": l, "close": c}


def test_data_integrity_passes_valid_ohlc():
    result = audit_ohlc([candle(1), candle(2)])
    assert result.status is GateStatus.PASS
    assert result.accepted_count == 2


def test_data_integrity_rejects_invalid_high():
    result = audit_ohlc([candle(1, h=1.05)])
    assert result.status is GateStatus.FAIL
    assert any(f.code == "INVALID_OHLC" for f in result.findings)


def test_temporal_audit_rejects_future_parent():
    events = [{
        "id": "FVG1",
        "candidate_time": 10,
        "confirmation_time": 11,
        "tradable_time": 11,
        "observation_time": 11,
        "parent_time": 12,
    }]
    violations = audit_events(events)
    assert any(v.code == "LOOK_AHEAD" for v in violations)


def test_funnel_rejects_duplicate_logical_event():
    records = [
        {"stage": "FVG", "id": "F1", "accepted": True, "observation_time": T0},
        {"stage": "FVG", "id": "F1", "accepted": True, "observation_time": T0},
    ]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "DUPLICATE_EVENT" for f in result.findings)


def test_funnel_rejects_unexplained_rejection():
    records = [{"stage": "OB", "id": "O1", "accepted": False}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "UNEXPLAINED_REJECTION" for f in result.findings)


def test_funnel_requires_observation_time():
    # Contrato A7: evento aceptado sin observation_time => CONTRACT_VIOLATION.
    records = [{"stage": "FVG", "id": "F1", "accepted": True}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "CONTRACT_VIOLATION" for f in result.findings)


def test_funnel_rejects_candidate_after_confirmation():
    # Orden causal: candidate_time > confirmation_time => TEMPORAL_VIOLATION.
    records = [{"stage": "FVG", "id": "F1", "accepted": True,
                "candidate_time": T2, "confirmation_time": T1, "tradable_time": T2,
                "observation_time": T2}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "TEMPORAL_VIOLATION" for f in result.findings)


def test_funnel_rejects_observation_before_confirmation():
    # observation_time < confirmation_time => TEMPORAL_VIOLATION.
    records = [{"stage": "FVG", "id": "F1", "accepted": True,
                "candidate_time": T0, "confirmation_time": T1, "tradable_time": T2,
                "observation_time": T0}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "TEMPORAL_VIOLATION" for f in result.findings)


def test_funnel_rejects_self_parent_cycle():
    # parent_id == id => ciclo => CONTRACT_VIOLATION.
    records = [{"stage": "CONFLUENCE", "id": "X1", "accepted": True,
                "observation_time": T1, "requires_parent": True, "parent_id": "X1",
                "lineage_valid": True}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "CONTRACT_VIOLATION" for f in result.findings)


def test_funnel_rejects_orphan_parent():
    # requires_parent con padre que no existe en el run => MISSING_PARENT.
    records = [{"stage": "CONFLUENCE", "id": "X1", "accepted": True,
                "observation_time": T1, "requires_parent": True, "parent_id": "GHOST",
                "lineage_valid": True}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "MISSING_PARENT" for f in result.findings)


def test_funnel_rejects_invalid_direction():
    records = [{"stage": "FVG", "id": "F1", "accepted": True,
                "observation_time": T1, "direction": 5}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "INVALID_DIRECTION" for f in result.findings)


def test_funnel_rejects_unknown_rejection_reason():
    records = [{"stage": "OB", "id": "O1", "accepted": False, "rejection_reason": "MADE_UP"}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "CONTRACT_VIOLATION" for f in result.findings)


def test_funnel_passes_explained_population():
    # Contrato A7: población explicada pasa.
    records = [
        {"stage": "FVG", "id": "F1", "accepted": True, "candidate_time": T0,
         "confirmation_time": T1, "tradable_time": T1, "observation_time": T1, "direction": 1},
        {"stage": "OB", "id": "O1", "accepted": False, "rejection_reason": "UNCONFIRMED_EVENT"},
    ]
    result, summaries = FunnelAudit().run(records)
    assert result.status is GateStatus.PASS
    assert len(summaries) == 12  # STAGES del contrato A7


def _valid_event(event_id="F1", stage="FVG", observation=T1):
    return {
        "stage": stage,
        "id": event_id,
        "accepted": True,
        "candidate_time": T0,
        "confirmation_time": T1,
        "tradable_time": T1,
        "observation_time": observation,
        "direction": 1,
    }


def test_funnel_rejects_each_missing_canonical_time():
    for field in ("candidate_time", "confirmation_time", "tradable_time", "observation_time"):
        record = _valid_event()
        record.pop(field)
        result, _ = FunnelAudit().run([record])
        assert result.status is GateStatus.FAIL
        assert any(f.code == "CONTRACT_VIOLATION" and field in f.message for f in result.findings)


def test_funnel_empty_population_is_not_pass():
    result, _ = FunnelAudit().run([])
    assert result.status is GateStatus.FAIL
    assert any("population is empty" in f.message for f in result.findings)


def test_funnel_rejects_unparseable_time_and_parent_time():
    record = _valid_event()
    record["confirmation_time"] = "not-a-time"
    record["requires_parent"] = True
    record["parent_id"] = "P"
    record["lineage_valid"] = True
    record["parent_time"] = "also-not-a-time"
    result, _ = FunnelAudit().run([record])
    assert result.status is GateStatus.FAIL
    assert sum(f.code == "CONTRACT_VIOLATION" for f in result.findings) >= 2


def test_funnel_rejects_parent_after_child_candidate():
    parent = _valid_event("P", "OB", T0)
    child = _valid_event("C", "CONFLUENCE")
    child.update({"requires_parent": True, "parent_id": "P", "lineage_valid": True, "parent_time": T2})
    result, _ = FunnelAudit().run([parent, child])
    assert result.status is GateStatus.FAIL
    assert any(f.code == "TEMPORAL_VIOLATION" and "parent_time" in f.message for f in result.findings)


def test_funnel_rejects_tradable_after_observation():
    record = _valid_event()
    record["tradable_time"] = T2
    result, _ = FunnelAudit().run([record])
    assert result.status is GateStatus.FAIL
    assert any(f.code == "TEMPORAL_VIOLATION" and "tradable_time" in f.message for f in result.findings)


def test_funnel_derives_parent_time_from_parent_record():
    parent = _valid_event("P", "OB", T0)
    parent.update({"candidate_time": T0, "confirmation_time": T0, "tradable_time": T0})
    child = _valid_event("C", "CONFLUENCE", T1)
    child.update({"requires_parent": True, "parent_id": "P", "lineage_valid": True})
    result, _ = FunnelAudit().run([parent, child])
    assert result.status is GateStatus.PASS


def test_funnel_rejects_rejected_parent():
    parent = _valid_event("P", "OB", T0)
    parent["accepted"] = False
    parent.pop("direction")
    parent["rejection_reason"] = "INVALID_DATA"
    child = _valid_event("C", "CONFLUENCE")
    child.update({"requires_parent": True, "parent_id": "P", "lineage_valid": True})
    result, _ = FunnelAudit().run([parent, child])
    assert result.status is GateStatus.FAIL
    assert any(f.code == "INVALID_PARENT" for f in result.findings)


def test_funnel_rejects_two_node_lineage_cycle():
    a = _valid_event("A", "CONFLUENCE")
    b = _valid_event("B", "LINEAGE")
    a.update({"requires_parent": True, "parent_id": "B", "lineage_valid": True})
    b.update({"requires_parent": True, "parent_id": "A", "lineage_valid": True})
    result, _ = FunnelAudit().run([a, b])
    assert result.status is GateStatus.FAIL
    assert any(f.code == "CONTRACT_VIOLATION" and "cycle detected" in f.message for f in result.findings)


def test_funnel_rejects_parent_fields_without_parent_requirement():
    record = _valid_event()
    record["parent_time"] = T0
    result, _ = FunnelAudit().run([record])
    assert result.status is GateStatus.FAIL
    assert any(f.code == "CONTRACT_VIOLATION" and "lineage fields" in f.message for f in result.findings)


def test_funnel_is_order_invariant_and_accepts_generators():
    records = [_valid_event("F1"), _valid_event("F2", observation=T2)]
    first = FunnelAudit().run(records)
    second = FunnelAudit().run(iter(reversed(records)))
    assert first == second


def test_funnel_rejects_identity_stage_and_direction_contract_errors():
    records = [_valid_event("", "NOT_A_STAGE"), _valid_event("B", "FVG")]
    records[1]["direction"] = True
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "CONTRACT_VIOLATION" and "stage" in f.message for f in result.findings)
    assert any(f.code == "INVALID_DIRECTION" for f in result.findings)


def test_funnel_expected_stage_manifest_cannot_pass_unverified():
    result, _ = FunnelAudit().run([_valid_event()], expected_stages=("FVG", "OB"))
    assert result.status is GateStatus.FAIL
    assert any(f.stage == "OB" and "not verified" in f.message for f in result.findings)


def test_funnel_full_prefix_atomic_check_is_fail_closed():
    full = [_valid_event("F1", observation=T1), _valid_event("F2", observation=T2)]
    ok, _ = FunnelAudit().run(full, prefix_records=[full[0]], prefix_time=T1)
    assert ok.status is GateStatus.PASS
    bad, _ = FunnelAudit().run(full, prefix_records=[], prefix_time=T1)
    assert bad.status is GateStatus.FAIL
    assert any(f.stage == "PREFIX" for f in bad.findings)


def test_a7_aggregate_cannot_hide_external_gate_failures():
    result, _ = FunnelAudit().run([_valid_event()])
    assert aggregate_a7_status(result) is GateStatus.PASS
    assert aggregate_a7_status(result, provenance_ok=False) is GateStatus.FAIL
    assert aggregate_a7_status(result, prefix_invariant=False) is GateStatus.FAIL
    assert aggregate_a7_status(result, idempotent=False) is GateStatus.FAIL


def test_oe_a76_a77_metrics_are_contractually_required_at_runner_boundary():
    accepted = _valid_event("F1")
    accepted["timeframe"] = "H1"
    rejected = {"stage": "FVG", "id": "F2", "accepted": False,
                "rejection_reason": "NO_OB_CAUSAL", "observation_time": T1,
                "timeframe": "H1"}
    result, _ = FunnelAudit().run([accepted, rejected])

    # This is the executable contract that the runner must serialize. It is
    # intentionally tested without importing/changing mtf_seq_funnel_a7.py.
    assert set(A7_REQUIRED_REPORT_METRICS) == {"rejection_reason_counts", "timeframe_counts"}
    assert missing_a7_report_metrics(result.metrics) == ()
    assert result.metrics["rejection_reason_counts"] == {"NO_OB_CAUSAL": 1}
    assert result.metrics["timeframe_counts"] == {"H1": 2}


def test_funnel_accepts_real_sequence_atomic_substages_and_aggregates_them():
    records = [_valid_event("L", "LIQUIDITY_POOL"), _valid_event("S", "SWEEP"), _valid_event("R", "RETEST")]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.PASS
    assert result.metrics["extra_stage_counts"] == {"LIQUIDITY_POOL": 1, "RETEST": 1, "SWEEP": 1}


def test_funnel_rejects_sequence_complete_without_canonical_times():
    record = _valid_event("SEQ-1", "SEQUENCE")
    for field in ("candidate_time", "confirmation_time", "tradable_time"):
        record.pop(field)
    result, _ = FunnelAudit().run([record])
    assert result.status is GateStatus.FAIL
    assert sum(f.code == "CONTRACT_VIOLATION" and field in f.message for f in result.findings for field in ("candidate_time", "confirmation_time", "tradable_time")) >= 3


def test_funnel_rejects_parent_time_after_observation():
    parent = _valid_event("P", "OB", T1)
    child = _valid_event("C", "CONFLUENCE", T1)
    child.update({"requires_parent": True, "parent_id": "P", "lineage_valid": True, "parent_time": T2})
    result, _ = FunnelAudit().run([parent, child])
    assert result.status is GateStatus.FAIL
    assert any(f.code == "TEMPORAL_VIOLATION" and "parent_time" in f.message for f in result.findings)
