"""Real MarketState P-I-T regression for the 2026-09-20 A/B findings."""
from datetime import datetime, timezone

import pytest

from engine.causal_replay import replay_closed_bars
from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState


def t(h):
    return datetime(2026, 9, 20, h, tzinfo=timezone.utc)


def obj(name='OB_H4', born=None):
    born = t(8) if born is None else born
    return MarketObject(id=name, symbol='EURUSD', type=ObjectType.ORDER_BLOCK,
                        origin_tf='H4', role=Role.POI, direction=1,
                        zone_low=1.0000, zone_high=1.0100, creation_time=born,
                        confirmation_time=born, tradable_time=born,
                        state=ObjectState.ACTIVE, meta={'origin': 'confirmed'})


def bar(hour, ix, low, close):
    return {'time': t(hour), 'tf':'H4', '__index__':ix,
            'open':1.015, 'high':1.020, 'low':low, 'close':close}


def test_metadata_at_birth_touch_and_invalidation_are_historical():
    ms=MarketState()
    original=obj()
    ms.ingest(original)
    initial=ms.projection_at(t(8))['OB_H4']
    assert initial.invalidated_time is None and initial.first_touch_time is None
    assert initial.touch_count==0 and initial.meta=={'origin':'confirmed'}
    ms.advance_bar(original.id,bar(9,1,1.006,1.012))
    partial=ms.projection_at(t(9))[original.id]
    assert partial.state is ObjectState.PARTIALLY_MITIGATED
    assert partial.touch_count==1 and partial.first_touch_time==t(9)
    assert partial.meta.get('CE_TOUCHED') is False or partial.meta.get('CE_TOUCHED') is None
    ms.advance_bar(original.id,bar(10,2,1.003,1.012))
    twice=ms.projection_at(t(10))[original.id]
    assert twice.touch_count==2 and twice.meta.get('CE_TOUCHED') is True
    assert len(ms.history_of(original.id))==2  # touch changed, state did not
    ms.advance_bar(original.id,bar(11,3,0.997,0.996))
    assert ms.projection_at(t(11))[original.id].state is ObjectState.INVALIDATED
    assert ms.projection_at(t(11))[original.id].invalidated_time==t(11)
    for when, count in [(t(8),0),(t(9),1),(t(10),2)]:
        past=ms.projection_at(when)[original.id]
        assert past.touch_count==count
        assert past.invalidated_time is None
        assert past.invalidated_bar is None
        assert past.meta.get('CE_TOUCHED') is not True or when==t(10)
        assert all('2026-09-20 11:' not in str(v) for v in past.meta.values())


def test_future_mutations_and_checkpoint_continue_do_not_change_past():
    ms=MarketState()
    ms.ingest(obj())
    ms.advance_bar('OB_H4',bar(9,1,1.006,1.012))
    saved=ms.to_dict()
    restored=MarketState.from_dict(saved)
    assert saved==restored.to_dict()
    for market in (ms,restored):
        market.advance_bar('OB_H4',bar(10,2,1.003,1.012))
        market.advance_bar('OB_H4',bar(11,3,0.997,0.996))
        assert market.projection_at(t(8))['OB_H4'].touch_count==0
        assert market.projection_at(t(9))['OB_H4'].touch_count==1
        assert market.projection_at(t(10))['OB_H4'].touch_count==2
    assert ms.to_dict()==restored.to_dict()
    ms.all_objects()[0].invalidated_time=t(12)  # uncontrolled external mutation
    ms.all_objects()[0].meta['FUTURE_EXTRA']='wrong'
    assert ms.projection_at(t(8))['OB_H4'].invalidated_time is None
    assert 'FUTURE_EXTRA' not in ms.projection_at(t(9))['OB_H4'].meta


def test_legacy_checkpoint_without_object_timeline_fails_closed():
    ms=MarketState();ms.ingest(obj());d=ms.to_dict();d.pop('object_snapshots')
    restored=MarketState.from_dict(d)
    with pytest.raises(ValueError,match='NO_CAUSAL_METADATA_HISTORY'):
        restored.projection_at(t(8))


def test_simultaneous_parent_rejected_until_explicitly_resolved():
    parent=obj('parent')
    child=obj('child')
    child.parent_object=parent.id
    with pytest.raises(ValueError,match='simultaneous unproven parent'):
        replay_closed_bars({},[parent,child],as_of=t(9))


def test_earlier_parent_can_be_ingested_without_fabricating_links():
    parent=obj('parent')
    child=obj('child',born=t(9));child.parent_object=parent.id
    replay=replay_closed_bars({},[parent,child],as_of=t(10))
    assert type(replay['market_state']) is MarketState
    assert replay['linked_objects']==1
    assert replay['projection']['child'].parent_object=='parent'
    assert replay['projection']['parent'].related_objects==[]
    assert replay['gates']['FUNNEL']=='NOT_RUN'
