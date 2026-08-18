from audits.checks.data_integrity import audit_ohlc
from audits.core.temporal import audit_ordered_events
from audits.funnel.engine import FunnelAudit, GateStatus


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
    violations = audit_ordered_events(events)
    assert any(v.code == "LOOK_AHEAD" for v in violations)


def test_funnel_rejects_duplicate_logical_event():
    records = [
        {"stage": "FVG", "id": "F1", "accepted": True},
        {"stage": "FVG", "id": "F1", "accepted": True},
    ]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "DUPLICATE_EVENT" for f in result.findings)


def test_funnel_rejects_unexplained_rejection():
    records = [{"stage": "OB", "id": "O1", "accepted": False}]
    result, _ = FunnelAudit().run(records)
    assert result.status is GateStatus.FAIL
    assert any(f.code == "UNEXPLAINED_REJECTION" for f in result.findings)


def test_funnel_passes_explained_population():
    records = [
        {"stage": "FVG", "id": "F1", "accepted": True},
        {"stage": "OB", "id": "O1", "accepted": False, "rejection_reason": "UNCONFIRMED_EVENT"},
    ]
    result, summaries = FunnelAudit().run(records)
    assert result.status is GateStatus.PASS
    assert len(summaries) == 9
