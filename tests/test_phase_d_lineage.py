import json

from engine.lineage import CausalLink, link, validate_hierarchical_lineage, validate_links, validate_six_tf_lineage
from engine.market_object import MarketObject, ObjectType, Role


def obj(i, bar, typ=ObjectType.BOS, parent=None, t=None):
    return MarketObject(
        id=f"o{i}",
        symbol="EURUSD",
        type=typ,
        origin_tf="H1",
        role=Role.CONTEXT,
        direction=1,
        zone_high=1.2,
        zone_low=1.1,
        bar_index=bar,
        bar_time=t if t is not None else bar,
        parent_object=parent,
    )


def test_parent_before_child_creates_causal_link():
    parent = obj(1, 10)
    child = obj(2, 12, typ=ObjectType.FVG, parent=parent.id)
    causal = link(parent, child, "DISPLACEMENT_TO_FVG")
    assert causal.parent_id == parent.id
    assert causal.child_id == child.id
    assert causal.parent_bar == 10
    assert causal.child_bar == 12


def test_future_parent_is_rejected():
    parent = obj(1, 20)
    child = obj(2, 12, typ=ObjectType.FVG)
    try:
        link(parent, child, "FUTURE")
    except ValueError as exc:
        assert "después" in str(exc)
    else:
        raise AssertionError("Future parent must be rejected")


def test_future_parent_time_is_rejected():
    parent = obj(1, 10, t=20)
    child = obj(2, 12, typ=ObjectType.FVG, t=12)
    try:
        link(parent, child, "FUTURE_TIME")
    except ValueError as exc:
        assert "parent_time" in str(exc)
    else:
        raise AssertionError("Future parent_time must be rejected")


def test_duplicate_links_are_rejected():
    p = obj(1, 10)
    c = obj(2, 12, typ=ObjectType.FVG, parent=p.id)
    a = link(p, c, "PARENT")
    b = link(p, c, "PARENT")
    try:
        validate_links([a, b])
    except ValueError as exc:
        assert "duplicados" in str(exc)
    else:
        raise AssertionError("Duplicate causal links must be rejected")


def test_missing_bar_index_is_rejected():
    p = obj(1, 10)
    c = obj(2, 12, typ=ObjectType.FVG)
    c.bar_index = None
    try:
        link(p, c, "PARENT")
    except ValueError as exc:
        assert "bar_index" in str(exc)
    else:
        raise AssertionError("Missing bar_index must be rejected")


def test_market_object_parent_references_existing_id_but_lineage_link_is_explicit():
    p = obj(1, 10)
    c = obj(2, 12, typ=ObjectType.FVG, parent=p.id)
    causal = link(p, c, "BOS_TO_FVG")
    assert c.parent_object == p.id
    assert causal.relation == "BOS_TO_FVG"


def test_causal_link_is_immutable():
    link_obj = CausalLink("p", "c", "REL", 1, 2)
    try:
        link_obj.child_bar = 99
    except Exception:
        pass
    else:
        raise AssertionError("CausalLink must be immutable")



def test_global_lineage_rejects_orphan_parent():
    child = obj(2, 12, typ=ObjectType.FVG, parent="missing")
    result = validate_hierarchical_lineage([child])
    assert result.valid is False
    assert any("parent_object huérfano" in item for item in result.errors)


def test_global_lineage_rejects_cycle():
    a = obj(1, 10)
    b = obj(2, 12, typ=ObjectType.FVG, parent=a.id)
    a.parent_object = b.id
    result = validate_hierarchical_lineage([a, b])
    assert result.valid is False
    assert any("ciclo parent_object" in item for item in result.errors)


def test_cross_tf_uses_timestamps_not_incomparable_bar_indices():
    parent = MarketObject(
        id="h4_parent", symbol="EURUSD", type=ObjectType.ORDER_BLOCK,
        origin_tf="H4", role=Role.CONTEXT, direction=1,
        zone_high=1.2, zone_low=1.1, bar_index=1000,
        bar_time="2026-09-17T12:00:00+00:00",
    )
    child = MarketObject(
        id="m15_child", symbol="EURUSD", type=ObjectType.FVG,
        origin_tf="M15", role=Role.REFINEMENT, direction=1,
        zone_high=1.2, zone_low=1.1, bar_index=5,
        bar_time="2026-09-17T12:15:00+00:00", parent_object=parent.id,
    )
    result = validate_hierarchical_lineage([parent, child])
    assert result.valid is True
    assert result.link_count == 1


def test_cross_tf_future_parent_time_is_rejected_globally():
    parent = MarketObject(
        id="h4_future", symbol="EURUSD", type=ObjectType.ORDER_BLOCK,
        origin_tf="H4", role=Role.CONTEXT, direction=1,
        zone_high=1.2, zone_low=1.1, bar_index=1,
        bar_time="2026-09-17T12:30:00+00:00",
    )
    child = MarketObject(
        id="m15_past", symbol="EURUSD", type=ObjectType.FVG,
        origin_tf="M15", role=Role.REFINEMENT, direction=1,
        zone_high=1.2, zone_low=1.1, bar_index=999,
        bar_time="2026-09-17T12:15:00+00:00", parent_object=parent.id,
    )
    result = validate_hierarchical_lineage([parent, child])
    assert result.valid is False
    assert any("parent_time" in item for item in result.errors)



def _six_tf_chain():
    tfs = ("D1", "H4", "H1", "M15", "M5", "M1")
    times = (
        "2026-08-22T00:00:00+00:00",
        "2026-08-24T20:00:00+00:00",
        "2026-08-24T20:00:01+00:00",
        "2026-08-24T20:30:00+00:00",
        "2026-08-24T20:35:00+00:00",
        "2026-08-24T20:35:00+00:00",
    )
    out = []
    parent = None
    for idx, (tf, when) in enumerate(zip(tfs, times)):
        item = MarketObject(
            id=f"SPINE_{tf}",
            symbol="EURUSD",
            type=ObjectType.CONTRACT,
            origin_tf=tf,
            role=Role.CONTEXT,
            direction=0,
            zone_low=1.0,
            zone_high=1.0,
            bar_index=idx,
            bar_time=when,
            parent_object=parent,
            meta={"lineage_layer_anchor": True},
        )
        out.append(item)
        parent = item.id
    return out


def test_six_tf_direct_parent_spine_passes():
    chain = _six_tf_chain()
    result = validate_six_tf_lineage(
        chain,
        decision_time="2026-08-24T20:35:00+00:00",
    )
    assert result.valid is True
    assert result.object_ids == (
        "SPINE_D1", "SPINE_H4", "SPINE_H1",
        "SPINE_M15", "SPINE_M5", "SPINE_M1",
    )
    assert result.missing_tfs == ()


def test_six_tf_every_parent_edge_is_mandatory():
    original = _six_tf_chain()
    for idx in range(1, len(original)):
        chain = [MarketObject.from_dict(item.to_dict()) for item in original]
        chain[idx].parent_object = None
        result = validate_six_tf_lineage(
            chain,
            decision_time="2026-08-24T20:35:00+00:00",
        )
        assert result.valid is False, f"edge into {chain[idx].origin_tf} should be mandatory"
        assert any("no existe camino parent_object directo" in error for error in result.errors)


def test_six_tf_missing_each_layer_fails_closed():
    original = _six_tf_chain()
    for tf in ("D1", "H4", "H1", "M15", "M5", "M1"):
        chain = [item for item in original if item.origin_tf != tf]
        result = validate_six_tf_lineage(
            chain,
            decision_time="2026-08-24T20:35:00+00:00",
        )
        assert result.valid is False
        assert tf in result.missing_tfs


def test_six_tf_save_load_roundtrip_preserves_exact_spine():
    before = _six_tf_chain()
    payload = json.loads(json.dumps([item.to_dict() for item in before]))
    restored = [MarketObject.from_dict(item) for item in payload]
    a = validate_six_tf_lineage(before, decision_time="2026-08-24T20:35:00+00:00")
    b = validate_six_tf_lineage(restored, decision_time="2026-08-24T20:35:00+00:00")
    assert a.valid is True and b.valid is True
    assert a.object_ids == b.object_ids
    assert a.required_chain == b.required_chain


def test_six_tf_rejects_mixed_symbol_spine():
    chain = _six_tf_chain()
    chain[-1].symbol = "XAUUSD"
    result = validate_six_tf_lineage(
        chain,
        decision_time="2026-08-24T20:35:00+00:00",
    )
    assert result.valid is False
    assert any("mezcla símbolos" in error for error in result.errors)
