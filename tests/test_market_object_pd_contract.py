from engine.market_object import MarketObject, ObjectState, ObjectType, Role


def test_temporal_contract_round_trip():
    obj = MarketObject(
        id="FVG_001",
        symbol="EURUSD",
        type=ObjectType.FVG,
        origin_tf="M5",
        role=Role.REFINEMENT,
        direction=1,
        zone_high=1.1020,
        zone_low=1.1010,
        candidate_bar=10,
        confirmation_bar=11,
        tradable_bar=11,
        first_touch_bar=15,
        touch_count=1,
        state=ObjectState.ACTIVE,
        parent_object="DISP_001",
    )

    restored = MarketObject.from_dict(obj.to_dict())
    assert restored.id == obj.id
    assert restored.type == ObjectType.FVG
    assert restored.candidate_bar == 10
    assert restored.confirmation_bar == 11
    assert restored.tradable_bar == 11
    assert restored.first_touch_bar == 15
    assert restored.touch_count == 1
    assert restored.parent_object == "DISP_001"


def test_temporal_contract_rejects_future_confirmation_order():
    try:
        MarketObject(
            id="OB_BAD",
            symbol="EURUSD",
            type=ObjectType.ORDER_BLOCK,
            origin_tf="M5",
            role=Role.REFINEMENT,
            candidate_bar=20,
            confirmation_bar=19,
        )
    except ValueError as exc:
        assert "candidate <= confirmation <= tradable" in str(exc)
    else:
        raise AssertionError("El contrato temporal debe rechazar confirmation_bar < candidate_bar")


def test_tradable_requires_confirmation():
    try:
        MarketObject(
            id="OB_BAD_2",
            symbol="EURUSD",
            type=ObjectType.ORDER_BLOCK,
            origin_tf="M5",
            role=Role.REFINEMENT,
            candidate_bar=20,
            tradable_bar=21,
        )
    except ValueError as exc:
        assert "tradable_bar requiere confirmation_bar" in str(exc)
    else:
        raise AssertionError("tradable_bar sin confirmation_bar debe ser inválido")


def test_poi_layer_rule_is_preserved():
    try:
        MarketObject(
            id="POI_BAD",
            symbol="EURUSD",
            type=ObjectType.FVG,
            origin_tf="M15",
            role=Role.POI,
        )
    except ValueError as exc:
        assert "POI solo en HTF" in str(exc)
    else:
        raise AssertionError("POI M15 debe seguir prohibido por la ontología vigente")
