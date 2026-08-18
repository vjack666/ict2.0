from audits.codigo.audit_stack import run_stack


def rows():
    return [
        {"id": "1", "time": 1, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},
        {"id": "2", "time": 2, "open": 1.15, "high": 1.25, "low": 1.05, "close": 1.2},
    ]


def events():
    return [{"id": "e", "candidate_time": 1, "confirmation_time": 2, "tradable_time": 2, "observation_time": 2}]


def funnel():
    return [
        {"stage": "VALID_BARS", "id": "b1", "accepted": True, "direction": 1},
        {"stage": "STRUCTURE", "id": "s1", "accepted": True, "direction": 1},
        {"stage": "BOS_CHOCH", "id": "c1", "accepted": True, "direction": 1},
        {"stage": "DISPLACEMENT", "id": "d1", "accepted": True, "direction": 1},
        {"stage": "FVG", "id": "f1", "accepted": True, "direction": 1},
        {"stage": "OB", "id": "o1", "accepted": True, "direction": 1, "ob_type": "CANONICAL"},
        {"stage": "CONFLUENCE", "id": "x1", "accepted": True, "direction": 1},
        {"stage": "LINEAGE", "id": "l1", "accepted": True, "direction": 1},
        {"stage": "SETUP", "id": "u1", "accepted": True, "direction": 1},
        {"stage": "SETUP", "id": "u2", "accepted": True, "direction": -1},
    ]


def test_full_audit_stack_passes_contract_smoke():
    result = run_stack(rows(), events(), funnel())
    assert result["status"] == "PASS"
    assert list(result["gates"]) == [
        "A0_DATA_INTEGRITY", "A1_SCHEMA", "A2_POINT_IN_TIME",
        "A3_SEMANTICS", "A4_DETECTOR_METAMORPHIC", "A5_CROSS_TIMEFRAME",
        "A6_LINEAGE", "A7_FUNNEL", "A8_COVERAGE_REGIME", "A9_GOVERNANCE",
    ]


def test_full_audit_stack_catches_future_event():
    bad_events = [{"id": "future", "candidate_time": 1, "confirmation_time": 2, "tradable_time": 5, "observation_time": 2}]
    result = run_stack(rows(), bad_events, funnel())
    assert result["status"] == "FAIL"
    assert any(x["code"] == "LOOK_AHEAD" for x in result["findings"])
