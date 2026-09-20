"""PIT bridge: detector occurrence inventory -> observable MarketObjects.

This is NOT a sequence constructor and does NOT infer ICT lineage, lifecycle
or trade eligibility. It publishes an object no earlier than confirmation, even
when an OB detector reports an earlier source-candle creation_time.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import math
import pandas as pd

from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState

KINDS = {
    'BOS': (ObjectType.BOS, Role.CONFIRMATION),
    'CHOCH': (ObjectType.CHOCH, Role.CONFIRMATION),
    'MSS': (ObjectType.MSS, Role.CONFIRMATION),
    'DISPLACEMENT': (ObjectType.DISPLACEMENT, Role.TRIGGER),
    'OB': (ObjectType.ORDER_BLOCK, Role.REFINEMENT),
    'FVG': (ObjectType.FVG, Role.REFINEMENT),
}
TFS = frozenset(('D1', 'H4', 'H1', 'M15', 'M5', 'M1'))


def _time(value: Any) -> pd.Timestamp:
    result = pd.to_datetime(value, utc=True, errors='coerce')
    if pd.isna(result):
        raise ValueError('missing/invalid detector confirmation_time_utc')
    return result


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'missing {label}: cannot construct MarketObject geometry') from exc
    if not math.isfinite(result):
        raise ValueError(f'nonfinite {label}: cannot construct MarketObject geometry')
    return result


def object_from_occurrence(row: Mapping[str, Any], *, symbol: str = 'EURUSD') -> MarketObject:
    """Convert a *confirmed* detector row; do not infer parents or active lifecycle.

    `detector_object_id` is window-relative in the current detectors; stable
    cross-window identity instead uses symbol/TF/kind/confirmation/direction.
    """
    tf = str(row['tf'])
    kind = str(row['tipo'])
    if tf not in TFS or kind not in KINDS or not symbol:
        raise ValueError(f'unsupported detector type / TF / symbol: {kind}/{tf}/{symbol}')
    direction = int(row['direccion'])
    if direction not in (-1, 1):
        raise ValueError('a detector occurrence must have direction +/-1; a poll is not an event')
    confirmed = _time(row['confirmation_time_utc'])
    lower = _finite(row.get('nivel'), 'nivel/zone_low')
    upper = lower if kind in ('BOS','CHOCH','MSS') else _finite(row.get('zone_high'), 'zone_high')
    if upper < lower:
        raise ValueError(f'zone_high < zone_low for {kind}/{tf} at {confirmed}')
    if kind == 'DISPLACEMENT':
        _finite(row.get('source_close'), 'displacement source_close')
    typ, role = KINDS[kind]
    identity = f'{symbol}|{tf}|{kind}|{confirmed.isoformat()}|{direction:+d}'
    return MarketObject(
        id=identity, symbol=symbol, type=typ, origin_tf=tf, role=role,
        direction=direction, zone_low=lower, zone_high=upper,
        # Ingest uses creation_time. Source OB candle may predate confirmation:
        # never publish it at source candle time or reveal its future existence.
        creation_time=confirmed, bar_time=confirmed, confirmation_time=confirmed,
        tradable_time=confirmed, state=ObjectState.ACTIVE,
        meta={'bridge': 'DETECTOR_INVENTORY_NOT_FUNNEL', 'detector_kind': kind,
              'detector_object_id': str(row.get('detector_object_id') or ''),
              'lineage_status': 'UNRESOLVED', 'lifecycle_status': 'NOT_REPLAYED'},
    )


def build_event_market_state(
    rows: Iterable[Mapping[str, Any]], *, as_of: Any, symbol: str = 'EURUSD'
) -> dict[str, Any]:
    """Ingest only events confirmed by as_of; deduplicate repeated context polls.

    Fails closed on future rows and conflicting duplicates; does not mutate
    the canonical historical-event producer, MarketState, sequence or funnel.
    """
    cutoff = _time(as_of)
    objects: dict[str, MarketObject] = {}
    for row in rows:
        obj = object_from_occurrence(row, symbol=symbol)
        if _time(obj.confirmation_time) > cutoff:
            raise ValueError(f'future event leaked into as_of={cutoff}: {obj.id}')
        if obj.id in objects:
            prior = objects[obj.id]
            if (prior.zone_low, prior.zone_high, prior.type) != (obj.zone_low, obj.zone_high, obj.type):
                raise ValueError(f'conflicting detector occurrence identity: {obj.id}')
            continue
        objects[obj.id] = obj
    ms = MarketState()
    for obj in sorted(objects.values(), key=lambda x: (_time(x.confirmation_time), x.id)):
        ms.ingest(obj)
    return {'market_state': ms, 'objects': ms.projection_at(cutoff),
            'count': len(objects), 'status': 'DETECTOR_OBJECTS_ONLY_NO_LINEAGE_LIFECYCLE_OR_EPISODES'}
