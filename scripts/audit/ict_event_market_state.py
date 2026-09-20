#!/usr/bin/env python3
"""Read-only real detector inventory -> MarketState projection (not accepted ICT episodes).

Run ict_event_inventory.py first with --source on ORIGINAL, then provide
its generated CSV. No data source is silently substituted or invented.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.detector_event_bridge import build_event_market_state

DECISIONS = {'A': '2026-09-17T18:20:00Z', 'B': '2026-08-24T20:35:00Z'}


def run(inventory: Path, *, control: str, output: Path) -> dict:
    if control not in DECISIONS:
        raise ValueError('control must be A or B')
    if not inventory.is_file():
        raise FileNotFoundError(f'missing detector inventory: {inventory}')
    df = pd.read_csv(inventory)
    required = {'control','tf','tipo','direccion','confirmation_time_utc','nivel','zone_high'}
    if missing := required - set(df.columns):
        raise ValueError(f'inventory lacks geometry / provenance: {sorted(missing)}; regenerate with updated detector script')
    selected = df.loc[df['control'] == control].copy()
    if selected.empty:
        raise ValueError(f'inventory has no real occurrence rows for CONTROL {control}')
    bridge = build_event_market_state(selected.to_dict('records'), as_of=DECISIONS[control])
    ms = bridge['market_state']
    snapshot = ms.projection_at(DECISIONS[control])
    if len(snapshot) != bridge['count']:
        raise AssertionError('MarketState projection did not preserve unique identity')
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'status': bridge['status'], 'control': control, 'decision_time_utc': DECISIONS[control],
        'inventory_path': str(inventory),
        'inventory_sha256': hashlib.sha256(inventory.read_bytes()).hexdigest(),
        'inventory_rows': len(selected), 'unique_detector_marketobjects': bridge['count'],
        'by_tf': dict(sorted(Counter(obj.origin_tf for obj in snapshot.values()).items())),
        'by_kind': dict(sorted(Counter(obj.meta['detector_kind'] for obj in snapshot.values()).items())),
        'lineage_linked_count': 0, 'lifecycle_replayed_count': 0,
        'accepted_episodes_count': None, 'accepted_episodes_status': 'NOT_EVALUATED',
        'gates': {'P1_FULL_FUNNEL': 'NOT_RUN', 'P2': 'NOT_RUN',
                  'FULL_PREFIX_DETECTORS': 'NOT_RUN', 'INDEPENDENT_AUDIT': 'NOT_RUN'},
    }
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--inventory', required=True, type=Path, help='CSV from updated scripts/audit/ict_event_inventory.py')
    p.add_argument('--control', required=True, choices=sorted(DECISIONS))
    p.add_argument('--output', type=Path, default=Path('reports/audits/experiments/temporal/DETECTOR_MARKET_STATE.json'))
    a=p.parse_args()
    print(json.dumps(run(a.inventory,control=a.control,output=a.output),indent=2,ensure_ascii=False))
