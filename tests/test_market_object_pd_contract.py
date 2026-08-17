from engine.market_object import MarketObject, ObjectState, ObjectType, Role


def _base(**kwargs):
    values = dict(id="OBJ_001", symbol="EURUSD", type=ObjectType.FVG, origin_tf="M5", role=Role.REFINEMENT)
    values.update(kwargs)
    return MarketObject(**values)


def test_temporal_contract_round_trip():
    obj = _base(direction=1, zone_high=1.1020, zone_low=1.1010, candidate_bar=10, confirmation_bar=11, tradable_bar=11, first_touch_bar=15, touch_count=1, state=ObjectState.ACTIVE, parent_object="DISP_001", related_objects=["BOS_001"], quality_score=0.8)
    restored = MarketObject.from_dict(obj.to_dict())
    assert restored.id == obj.id
    assert restored.type == ObjectType.FVG
    assert restored.state == ObjectState.ACTIVE
    assert restored.candidate_bar == 10
    assert restored.tradable_bar == 11
    assert restored.first_touch_bar == 15
    assert restored.parent_object == "DISP_001"
    assert restored.related_objects == ["BOS_001"]
    assert restored.quality_score == 0.8


def test_all_pd_array_types_are_canonical():
    for object_type in (ObjectType.FVG, ObjectType.ORDER_BLOCK, ObjectType.BREAKER, ObjectType.BPR):
        assert _base(id=f"{object_type.value}_001", type=object_type).type is object_type


def test_temporal_contract_rejects_future_confirmation_order():
    try:
        _base(type=ObjectType.ORDER_BLOCK, candidate_bar=20, confirmation_bar=19)
    except ValueError as exc:
        assert "candidate <= confirmation <= tradable" in str(exc)
    else:
        raise AssertionError("confirmation_bar < candidate_bar debe ser inválido")


def test_tradable_requires_confirmation():
    try:
        _base(type=ObjectType.ORDER_BLOCK, candidate_bar=20, tradable_bar=21)
    except ValueError as exc:
        assert "tradable_bar requiere confirmation_bar" in str(exc)
    else:
        raise AssertionError("tradable_bar sin confirmation_bar debe ser inválido")


def test_time_contract_rejects_out_of_order_values():
    try:
        _base(candidate_time=3, confirmation_time=2)
    except ValueError as exc:
        assert "candidate_time" in str(exc)
    else:
        raise AssertionError("candidate_time > confirmation_time debe ser inválido")


def test_first_touch_requires_positive_touch_count():
    try:
        _base(first_touch_bar=12, touch_count=0)
    except ValueError as exc:
        assert "touch_count >= 1" in str(exc)
    else:
        raise AssertionError("first_touch_bar con touch_count=0 debe ser inválido")


def test_first_touch_cannot_precede_tradable_bar():
    try:
        _base(candidate_bar=10, confirmation_bar=11, tradable_bar=11, first_touch_bar=10, touch_count=1)
    except ValueError as exc:
        assert "first_touch_bar" in str(exc)
    else:
        raise AssertionError("first_touch_bar anterior a tradable_bar debe ser inválido")


def test_invalidated_bar_cannot_precede_candidate():
    try:
        _base(type=ObjectType.ORDER_BLOCK, candidate_bar=20, invalidated_bar=19)
    except ValueError as exc:
        assert "invalidated_bar" in str(exc)
    else:
        raise AssertionError("invalidated_bar anterior a candidate_bar debe ser inválido")


def test_foundational_direction_zone_and_score_invariants():
    for bad_direction in (-2, 2):
        try:
            _base(direction=bad_direction)
        except ValueError as exc:
            assert "direction debe ser -1, 0 o 1" in str(exc)
        else:
            raise AssertionError("direction fuera de {-1,0,1} debe ser inválida")
    try:
        _base(zone_high=1.1000, zone_low=1.1010)
    except ValueError as exc:
        assert "zone_high debe ser >= zone_low" in str(exc)
    else:
        raise AssertionError("Una zona invertida debe ser inválida")
    try:
        _base(quality_score=1.1)
    except ValueError as exc:
        assert "quality_score" in str(exc)
    else:
        raise AssertionError("quality_score > 1 debe ser inválido")


def test_lineage_rejects_self_parent_duplicates_and_empty_ids():
    for kwargs, expected in [({"id": "SELF", "parent_object": "SELF"}, "propio objeto"), ({"id": "SELF2", "related_objects": ["BOS", "BOS"]}, "duplicados"), ({"id": "SELF3", "related_objects": [""]}, "ids vacíos")]:
        try:
            _base(**kwargs)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("lineage inválido debe ser rechazado")


def test_lifecycle_transition_contract():
    obj = _base()
    assert obj.can_transition_to(ObjectState.ACTIVE)
    obj.transition_to(ObjectState.ACTIVE)
    obj.transition_to(ObjectState.PARTIALLY_MITIGATED)
    obj.transition_to(ObjectState.MITIGATED)
    assert obj.is_terminal
    assert not obj.can_transition_to(ObjectState.ACTIVE)
    try:
        obj.transition_to(ObjectState.ACTIVE)
    except ValueError as exc:
        assert "Transición de estado inválida" in str(exc)
    else:
        raise AssertionError("Un estado terminal no debe reactivarse")


def test_created_can_invalidate_or_expire_without_becoming_tradable():
    obj = _base(candidate_bar=10)
    obj.transition_to(ObjectState.INVALIDATED)
    assert obj.is_terminal
    expired = _base(id="EXP", candidate_bar=10)
    expired.transition_to(ObjectState.EXPIRED)
    assert expired.is_terminal


def test_poi_layer_rule_is_preserved():
    try:
        _base(id="POI_BAD", type=ObjectType.FVG, origin_tf="M15", role=Role.POI)
    except ValueError as exc:
        assert "POI solo en HTF" in str(exc)
    else:
        raise AssertionError("POI M15 debe seguir prohibido por la ontología vigente")
