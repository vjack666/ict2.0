from audits.codigo.data_integrity import audit_ohlc
from audits.codigo.temporal import audit_events
from audits.codigo.funnel import FunnelAudit
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
        {"stage": "FVG", "id": "F1", "accepted": True, "observation_time": T0, "direction": 1},
        {"stage": "OB", "id": "O1", "accepted": False, "rejection_reason": "UNCONFIRMED_EVENT"},
    ]
    result, summaries = FunnelAudit().run(records)
    assert result.status is GateStatus.PASS
    assert len(summaries) == 12  # STAGES del contrato A7
