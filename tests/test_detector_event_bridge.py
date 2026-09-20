"""Prevent premature OB visibility, phantom BOS and overcounting in MarketState."""
import importlib.util

import pandas as pd
import pytest

from engine.detector_event_bridge import build_event_market_state, object_from_occurrence
from engine.market_object import ObjectType, ObjectState


def _row(kind='OB', *, time='2026-08-24T20:30:00Z', tf='M5', direction=1):
    return dict(tf=tf, tipo=kind, direccion=direction,
                confirmation_time_utc=time, nivel=1.100, zone_high=1.110,
                source_close=1.105, detector_object_id='OB_M5_15_BULL')


def test_dedup_poll_and_reject_zero_direction():
    row=_row('BOS')
    result=build_event_market_state([row, row, dict(row)], as_of='2026-08-24T20:35Z')
    assert result['count']==1
    assert len(result['market_state'].history_of(next(iter(result['objects']))))==1
    with pytest.raises(ValueError, match='poll'):
        object_from_occurrence(_row('BOS', direction=0))


def test_ob_cannot_be_seen_before_confirmation_and_does_not_infer_lineage():
    row=_row('OB', time='2026-08-24T20:30Z')
    result=build_event_market_state([row], as_of='2026-08-24T20:40Z')
    ms=result['market_state']
    assert not ms.projection_at(pd.Timestamp('2026-08-24T20:29Z'))
    obj=next(iter(ms.projection_at(pd.Timestamp('2026-08-24T20:30Z')).values()))
    assert obj.type==ObjectType.ORDER_BLOCK and obj.parent_object is None
    assert obj.meta['lifecycle_status']=='NOT_REPLAYED'
    assert ms.state_at(obj.id,'2026-08-24T20:29Z') is None
    assert obj.state==ObjectState.ACTIVE


def test_full_prefix_is_equal_and_future_injection_blocked():
    before=_row('FVG',time='2026-08-24T20:25Z')
    later=_row('FVG',time='2026-08-24T20:35Z')
    prefix=build_event_market_state([before],as_of='2026-08-24T20:30Z')
    assert list(prefix['objects'])==list(build_event_market_state([before],as_of='2026-08-24T20:30Z')['objects'])
    with pytest.raises(ValueError,match='future event'):
        build_event_market_state([before,later],as_of='2026-08-24T20:30Z')
    assert list(prefix['objects'])==list(build_event_market_state([later,before],as_of='2026-08-24T20:35Z')['market_state'].projection_at('2026-08-24T20:30Z'))


def test_geometry_conflicts_and_missing_real_geometry_fail_closed():
    row=_row('FVG')
    with pytest.raises(ValueError,match='conflicting'):
        build_event_market_state([row,dict(row,zone_high=1.120)],as_of='2026-08-24T20:35Z')
    with pytest.raises(ValueError,match='zone_high'):
        object_from_occurrence(dict(row,zone_high=None))
    with pytest.raises(ValueError,match='zone_high < zone_low'):
        object_from_occurrence(dict(row,zone_high=1.099))


def test_prior_inventory_without_complete_geometry_is_rejected():
    # Original inventory A/B had nivel but no zone_high; never fabricate FVG width.
    prior=_row('FVG')
    prior.pop('zone_high')
    with pytest.raises(ValueError, match='zone_high'):
        object_from_occurrence(prior)
