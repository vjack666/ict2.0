"""Replay cerrado multi-TF para objetos ya detectados; no genera señales ni episodios.

Entrada: frames con 'time' = cierre UTC, objetos de productor canónico con
confirmation_time/tradable_time explícitos. Nunca crea relaciones nuevas.
El productor de eventos DEBE superar su propio FULL/PREFIX; esta capa no lo
certifica y NO convierte el inventario aislado de detectores en un funnel.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from heapq import heappop, heappush
from typing import Any, Mapping

ZONAL = frozenset({'FVG', 'ORDER_BLOCK', 'BREAKER', 'BPR'})
TFS = ('D1', 'H4', 'H1', 'M15', 'M5', 'M1')


def utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif hasattr(value, 'to_pydatetime'):
        result = value.to_pydatetime()
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    else:
        raise ValueError(f'unsupported timestamp: {value!r}')
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f'naive time rejected: {value!r}')
    return result.astimezone(timezone.utc)


def _availability(obj: Any) -> datetime:
    if obj.confirmation_time is None or obj.tradable_time is None:
        raise ValueError(f'object without confirmation/tradable time: {obj.id}')
    confirmed, tradable = utc(obj.confirmation_time), utc(obj.tradable_time)
    if tradable < confirmed:
        raise ValueError(f'tradable before confirmation: {obj.id}')
    return tradable  # never publish before available and tradable


def replay_closed_bars(frames: Mapping[str, Any], objects: list[Any], *, as_of: Any,
                       market_state_factory=None) -> dict[str, Any]:
    """Chronological merge of preclosed TF bars; bounded working memory.

    All dataframes must already have a trustworthy UTC CLOSE timestamp. A
    global chronological scheduler ingests new events AFTER same-close bars,
    then evaluates only preexisting zonal objects on their own authority TF.
    """
    cutoff = utc(as_of)
    if market_state_factory is None:
        from engine.market_state import MarketState
        market_state_factory = MarketState
    ms = market_state_factory()
    scheduled = []
    by_id = {}
    for source in objects:
        obj = deepcopy(source)  # producer-owned objects may contain old OB candle time
        if not obj.id or obj.id in by_id:
            raise ValueError(f'duplicate or missing object id: {obj.id!r}')
        birth = _availability(obj)
        if birth > cutoff:
            continue  # historical as-of snapshot: future objects invisible
        if obj.authority_tf != obj.origin_tf or obj.origin_tf not in TFS:
            raise ValueError(f'unsupported authority/origin TF: {obj.id}')
        # Related objects may leak future-child IDs via reverse pointers.
        if obj.related_objects:
            raise ValueError(f'prelinked related_objects not PIT-certified: {obj.id}')
        obj.creation_time = birth
        by_id[obj.id] = (birth, obj)
        scheduled.append((birth, obj.id))
    for birth, obj in by_id.values():
        parent = obj.parent_object
        if parent:
            if parent not in by_id:
                raise ValueError(f'missing observable parent: {obj.id} -> {parent}')
            if by_id[parent][0] >= birth:
                raise ValueError(f'future or simultaneous unproven parent: {obj.id} -> {parent}')
    scheduled.sort()
    # frames are input iterables/dataframes, NEVER read one future bar to decide
    # at an earlier time; individual TF streams are merged by their close time.
    heap = []
    readers = {}
    previous = {}
    counts = Counter()
    for tf in TFS:
        if tf not in frames:
            continue
        data = frames[tf]
        if getattr(data, 'empty', False):
            continue
        if hasattr(data, 'iterrows'):
            reader = ((int(i), row.to_dict()) for i, row in data.iterrows())
        else:
            reader = ((i, dict(row)) for i, row in enumerate(data))
        readers[tf] = reader
        def push_next(tf=tf):
            try:
                idx, bar = next(readers[tf])
            except StopIteration:
                return
            if 'time' not in bar or any(k not in bar for k in ('open','high','low','close')):
                raise ValueError(f'bar missing timestamp/OHLC in {tf}')
            t = utc(bar['time'])
            if tf in previous and t <= previous[tf]:
                raise ValueError(f'non-increasing closed bar time: {tf} {t}')
            previous[tf] = t
            if t <= cutoff:
                bar.update(time=t, tf=tf, __index__=idx)
                heappush(heap, (t, TFS.index(tf), idx, tf, bar))
        push_next()
    active = {}  # original source objects are never mutated
    birth_index = 0
    while heap or birth_index < len(scheduled):
        next_bar = heap[0][0] if heap else None
        next_birth = scheduled[birth_index][0] if birth_index < len(scheduled) else None
        t = min(x for x in (next_bar, next_birth) if x is not None)
        # Only previously tradable zones can be touched by a closed bar.
        while heap and heap[0][0] == t:
            _, _, _, tf, bar = heappop(heap)
            for obj in tuple(active.values()):
                if (obj.authority_tf == tf and obj.type.value in ZONAL
                        and _availability(obj) < t):
                    ms.advance_bar(obj.id, bar)
                    counts['lifecycle_observations'] += 1
            counts[f'bars_{tf}'] += 1
            push_next(tf)
        while birth_index < len(scheduled) and scheduled[birth_index][0] == t:
            _, obj_id = scheduled[birth_index]
            obj = by_id[obj_id][1]
            if obj.parent_object and obj.parent_object not in active:
                raise ValueError(f'parent not born by child confirmation: {obj.id}')
            ms.ingest(obj)
            active[obj.id] = obj
            counts[f'birth_{obj.origin_tf}'] += 1
            birth_index += 1
    projection = ms.projection_at(cutoff)
    if set(projection) != set(active):
        raise AssertionError('as-of projection differs from ingested IDs')
    return {'market_state': ms, 'projection': projection, 'stats': dict(sorted(counts.items())),
            'objects': len(projection), 'linked_objects': sum(bool(x.parent_object) for x in projection.values()),
            'status': 'PIT_REPLAY_DIAGNOSTIC_NOT_CANONICAL_SEQUENCE_OR_FUNNEL',
            'gates': {'FULL_PREFIX_PRODUCER': 'NOT_RUN', 'SIX_TF_CONTEXT': 'NOT_RUN',
                      'SEQUENCE': 'NOT_RUN', 'FUNNEL': 'NOT_RUN', 'EPISODES': 'NOT_RUN'}}
