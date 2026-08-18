from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.relations import relate_fvg_ob, relation_links


def obj(object_id, object_type, direction, bar, low, high):
    return MarketObject(
        id=object_id,
        symbol="EURUSD",
        type=object_type,
        origin_tf="H1",
        role=Role.REFINEMENT,
        direction=direction,
        zone_low=low,
        zone_high=high,
        creation_time=bar,
        state=ObjectState.ACTIVE,
        bar_index=bar,
        bar_time=bar,
        candidate_bar=max(0, bar - 1),
        candidate_time=max(0, bar - 1),
        confirmation_bar=bar,
        confirmation_time=bar,
        tradable_bar=bar,
        tradable_time=bar,
    )


def test_fvg_ob_overlap_creates_relation_and_lineage():
    fvg = obj("f1", ObjectType.FVG, 1, 10, 1.1000, 1.1050)
    ob = obj("o1", ObjectType.ORDER_BLOCK, 1, 12, 1.1020, 1.1080)

    relations = relate_fvg_ob([fvg], [ob], max_bars_apart=5)
    assert len(relations) == 1
    assert relations[0].overlap_low == 1.1020
    assert relations[0].overlap_high == 1.1050
    assert relations[0].temporal_ok is True

    links = relation_links(relations, {fvg.id: fvg}, {ob.id: ob})
    assert len(links) == 1
    assert links[0].relation == "FVG_OB_OVERLAP"
    assert links[0].parent_id == "f1"
    assert links[0].child_id == "o1"


def test_direction_and_distance_are_part_of_relation_contract():
    fvg = obj("f1", ObjectType.FVG, 1, 10, 1.1000, 1.1050)
    opposite = obj("o2", ObjectType.ORDER_BLOCK, -1, 12, 1.1020, 1.1080)
    far = obj("o3", ObjectType.ORDER_BLOCK, 1, 40, 1.1020, 1.1080)

    assert relate_fvg_ob([fvg], [opposite], max_bars_apart=5) == []
    assert relate_fvg_ob([fvg], [far], max_bars_apart=5) == []


def test_no_future_beyond_allowed_window_is_linked():
    fvg = obj("f1", ObjectType.FVG, 1, 10, 1.1000, 1.1050)
    future_ob = obj("o4", ObjectType.ORDER_BLOCK, 1, 31, 1.1020, 1.1080)

    assert relate_fvg_ob([fvg], [future_ob], max_bars_apart=20) == []
