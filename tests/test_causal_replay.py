"""Aislated scheduler contract tests; Hermes must run integration against real engine."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from engine.causal_replay import replay_closed_bars


def tm(i):
    return datetime(2026, 8, 24, 10, i, tzinfo=timezone.utc)


@dataclass
class Obj:
    id: str
    origin_tf: str = 'M5'
    authority_tf: str = 'M5'
    confirmation_time: object = field(default_factory=lambda: tm(5))
    tradable_time: object = field(default_factory=lambda: tm(5))
    creation_time: object = field(default_factory=lambda: tm(0))
    type: object = field(default_factory=lambda: SimpleNamespace(value='FVG'))
    parent_object: str | None = None
    related_objects: list = field(default_factory=list)


class FakeMS:
    def __init__(self):
        self.objects = {}
        self.seen = []
    def ingest(self, obj):
        assert obj.id not in self.objects
        self.objects[obj.id] = obj
    def advance_bar(self, obj_id, bar):
        assert bar['tf'] == self.objects[obj_id].authority_tf
        assert bar['time'] > self.objects[obj_id].tradable_time
        self.seen.append((obj_id, bar['tf'], bar['time']))
    def projection_at(self, t):
        return {key: value for key, value in self.objects.items() if value.creation_time <= t}


def bar(t):
    return {'time': t, 'open': 1., 'high': 1.1, 'low': .9, 'close': 1.}


def run(frames, objects, cutoff=tm(20)):
    return replay_closed_bars(frames, objects, as_of=cutoff, market_state_factory=FakeMS)


def test_birth_after_same_close_bar_and_only_origin_tf_can_transition():
    source = Obj('zone', creation_time=tm(0))
    x = run({'M5':[bar(tm(5)), bar(tm(10)), bar(tm(15))],
             'M1':[bar(tm(6)),bar(tm(11))]}, [source])
    assert x['objects'] == 1
    assert x['stats']['lifecycle_observations'] == 2
    assert [t for _,_,t in x['market_state'].seen] == [tm(10),tm(15)]
    assert source.creation_time == tm(0)  # input not mutated
    assert next(iter(x['projection'].values())).creation_time == tm(5)


def test_streaming_order_across_tf_and_equal_time_determinism():
    obj=Obj('o',origin_tf='H1',authority_tf='H1',confirmation_time=tm(5),tradable_time=tm(5))
    x=run({'M5':[bar(tm(10)),bar(tm(20))],'H1':[bar(tm(5)),bar(tm(20))]},[obj])
    assert x['market_state'].seen == [('o','H1',tm(20))]
    assert x['stats']['bars_M5'] == 2


def test_future_objects_and_bars_cannot_leak():
    a=Obj('now')
    later=Obj('later', confirmation_time=tm(20), tradable_time=tm(20))
    x=run({'M5':[bar(tm(5)),bar(tm(10)),bar(tm(20))]},[a,later],cutoff=tm(10))
    assert set(x['projection']) == {'now'}
    assert x['stats']['bars_M5'] == 2
    assert x['gates']['FUNNEL']=='NOT_RUN'


def test_unproven_lineage_and_duplicates_fail_closed():
    with pytest.raises(ValueError,match='missing observable parent'):
        run({},[Obj('child',parent_object='not-present')])
    with pytest.raises(ValueError,match='duplicate'):
        run({},[Obj('z'),Obj('z')])
    with pytest.raises(ValueError,match='prelinked'):
        run({},[Obj('z',related_objects=['future-child'])])
    with pytest.raises(ValueError,match='future or simultaneous'):
        run({},[Obj('parent',confirmation_time=tm(10),tradable_time=tm(10)),
                Obj('child',parent_object='parent',confirmation_time=tm(10),tradable_time=tm(10))])


def test_explicit_close_timestamp_monotonic_and_ohlc():
    with pytest.raises(ValueError,match='naive'):
        run({'M5':[bar(datetime(2026,8,24,10,5))]},[])
    with pytest.raises(ValueError,match='non-increasing'):
        run({'M5':[bar(tm(10)),bar(tm(5))]},[])
    with pytest.raises(ValueError,match='missing timestamp/OHLC'):
        run({'M5':[{'time':tm(5)}]},[])


def test_strict_time_contract_and_authority():
    with pytest.raises(ValueError,match='tradable before confirmation'):
        run({},[Obj('z',confirmation_time=tm(10),tradable_time=tm(5))])
    with pytest.raises(ValueError,match='unsupported authority'):
        run({},[Obj('z',authority_tf='H4')])
    x=run({},[Obj('parent'),Obj('child',parent_object='parent',confirmation_time=tm(10),tradable_time=tm(10))])
    assert x['linked_objects']==1 and x['objects']==2
