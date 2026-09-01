from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.relations import relate_fvg_ob, relation_links


def obj(object_id, object_type, direction, bar, low, high, candidate=None, confirm=None):
    c = candidate if candidate is not None else max(0, bar - 1)
    conf = confirm if confirm is not None else bar
    return MarketObject(
        id=object_id,
        symbol="EURUSD",
        type=object_type,
        origin_tf="H1",
        role=Role.REFINEMENT,
        direction=direction,
        zone_low=low,
        zone_high=high,
        creation_time=conf,
        state=ObjectState.ACTIVE,
        bar_index=conf,
        bar_time=conf,
        candidate_bar=c,
        candidate_time=c,
        confirmation_bar=conf,
        confirmation_time=conf,
        tradable_bar=conf,
        tradable_time=conf,
    )


def test_strict_causal_ob_before_fvg_creates_relation_and_lineage():
    # OB footprint at 8, confirm 9; FVG candidate 10, confirm 12
    ob = obj("o1", ObjectType.ORDER_BLOCK, 1, 9, 1.1020, 1.1080, candidate=8, confirm=9)
    fvg = obj("f1", ObjectType.FVG, 1, 12, 1.1000, 1.1050, candidate=10, confirm=12)

    relations = relate_fvg_ob([fvg], [ob], max_bars_apart=10, causal_mode="strict")
    assert len(relations) == 1
    assert relations[0].relation == "FVG_OB_CAUSAL"
    assert relations[0].causal_order == "OB_BEFORE_FVG"
    assert relations[0].overlap_low == 1.1020
    assert relations[0].overlap_high == 1.1050
    assert relations[0].bars_apart == 12 - 8  # fvg_confirm - ob_anchor

    links = relation_links(relations, {fvg.id: fvg}, {ob.id: ob})
    assert len(links) == 1
    assert links[0].parent_id == "o1"  # OB is always parent in strict mode
    assert links[0].child_id == "f1"
    assert links[0].relation == "FVG_OB_CAUSAL"


def test_strict_rejects_ob_after_fvg():
    fvg = obj("f1", ObjectType.FVG, 1, 10, 1.1000, 1.1050, candidate=8, confirm=10)
    ob_after = obj("o2", ObjectType.ORDER_BLOCK, 1, 12, 1.1020, 1.1080, candidate=11, confirm=12)

    assert relate_fvg_ob([fvg], [ob_after], max_bars_apart=20, causal_mode="strict") == []


def test_direction_and_distance_are_part_of_relation_contract():
    fvg = obj("f1", ObjectType.FVG, 1, 12, 1.1000, 1.1050, candidate=10, confirm=12)
    opposite = obj("o2", ObjectType.ORDER_BLOCK, -1, 9, 1.1020, 1.1080, candidate=8, confirm=9)
    far = obj("o3", ObjectType.ORDER_BLOCK, 1, 1, 1.1020, 1.1080, candidate=0, confirm=1)  # lag >> 5

    assert relate_fvg_ob([fvg], [opposite], max_bars_apart=20, causal_mode="strict") == []
    assert relate_fvg_ob([fvg], [far], max_bars_apart=5, causal_mode="strict") == []


def test_symmetric_mode_still_allows_either_order():
    fvg = obj("f1", ObjectType.FVG, 1, 10, 1.1000, 1.1050, candidate=8, confirm=10)
    ob_after = obj("o4", ObjectType.ORDER_BLOCK, 1, 12, 1.1020, 1.1080, candidate=11, confirm=12)

    rel = relate_fvg_ob([fvg], [ob_after], max_bars_apart=5, causal_mode="symmetric")
    assert len(rel) == 1
    assert rel[0].relation == "FVG_OB_OVERLAP"
    assert rel[0].causal_order == "SYMMETRIC"


def test_no_future_beyond_allowed_window_is_linked():
    fvg = obj("f1", ObjectType.FVG, 1, 10, 1.1000, 1.1050, candidate=8, confirm=10)
    future_ob = obj("o5", ObjectType.ORDER_BLOCK, 1, 31, 1.1020, 1.1080, candidate=30, confirm=31)

    assert relate_fvg_ob([fvg], [future_ob], max_bars_apart=20, causal_mode="strict") == []
    assert relate_fvg_ob([fvg], [future_ob], max_bars_apart=20, causal_mode="symmetric") == []
