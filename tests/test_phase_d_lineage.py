from engine.lineage import CausalLink, link, validate_links
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
