from __future__ import annotations

from datetime import datetime, timezone

from engine.lineage_hierarchy import (
    LineageStatus,
    build_hierarchical_lineage,
    lineage_result_to_snapshot_summary,
)
from engine.market_object import MarketObject, ObjectState, ObjectType, Role


def _obj(
    object_id: str,
    tf: str,
    bar: int,
    *,
    parent: str | None = None,
    role: Role = Role.REFINEMENT,
) -> MarketObject:
    return MarketObject(
        id=object_id,
        symbol="EURUSD",
        type=ObjectType.ORDER_BLOCK if role is Role.POI else ObjectType.FVG,
        origin_tf=tf,
        role=role,
        direction=1,
        zone_high=1.2,
        zone_low=1.1,
        state=ObjectState.ACTIVE,
        parent_object=parent,
        bar_index=bar,
        bar_time=datetime(2020, 1, 1, bar, tzinfo=timezone.utc),
        creation_time=datetime(2020, 1, 1, bar, tzinfo=timezone.utc),
    )


def test_hierarchical_lineage_validates_all_six_timeframes():
    objects = {
        "D1_POI": _obj("D1_POI", "D1", 1, role=Role.POI),
        "H4_POI": _obj("H4_POI", "H4", 2, parent="D1_POI", role=Role.POI),
        "H1_POI": _obj("H1_POI", "H1", 3, parent="H4_POI", role=Role.POI),
        "M15_REF": _obj("M15_REF", "M15", 4, parent="H1_POI"),
        "M5_EXEC": _obj("M5_EXEC", "M5", 5, parent="M15_REF"),
        "M1_TRIG": _obj("M1_TRIG", "M1", 6, parent="M5_EXEC"),
    }

    lineage = build_hierarchical_lineage(objects, require_all_six_tfs=True)
    summary = lineage_result_to_snapshot_summary(lineage)

    assert lineage.status is LineageStatus.VALID
    assert lineage.depth == 5
    assert summary["lineage_validated"] is True
    assert summary["six_tfs_complete"] is True
    assert summary["tfs_present"] == ["D1", "H1", "H4", "M1", "M15", "M5"]


def test_hierarchical_lineage_marks_h4_m15_only_as_legacy_when_six_tfs_required():
    objects = {
        "H4_POI": _obj("H4_POI", "H4", 1, role=Role.POI),
        "M15_REF": _obj("M15_REF", "M15", 2, parent="H4_POI"),
    }

    lineage = build_hierarchical_lineage(objects, require_all_six_tfs=True)

    assert lineage.status is LineageStatus.LEGACY_UNVALIDATED
