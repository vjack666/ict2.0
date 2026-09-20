#!/usr/bin/env python3
"""Piloto de replay histórico H4/M15: objetos reales, sin señales ni P1 PASS.

Usa las mismas fuentes que el manifiesto A/B; no inventa enlaces entre
ocurrencias del inventario ni declara secuencias ICT completas. El productor
H4/M15 existente determina los enlaces que sí puede acreditar.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.audit.ict_event_inventory import (CONTROLS, MEMBERS, TFS, WARMUP,
                                               read_source, verify_sha256_manifest)
from engine.causal_replay import replay_closed_bars
from engine.historical_event_objects import build_historical_event_objects


def run(*, source: Path, manifest: Path, control: str, output: Path) -> dict:
    if control not in CONTROLS:
        raise ValueError('unknown control')
    cutoff = pd.Timestamp(CONTROLS[control])
    with ZipFile(source) as z:
        physical_hashes = verify_sha256_manifest(z, manifest)
        frames = {}
        details = {}
        for tf in ('H4','M15'):
            df, metadata = read_source(z, tf, cutoff-pd.Timedelta(WARMUP[tf]))
            df['time'] = df['time'] + pd.Timedelta(TFS[tf])
            df = df.loc[df['time'] <= cutoff].copy().reset_index(drop=True)
            if df.empty or (cutoff-df['time'].iloc[-1]) > pd.Timedelta(TFS[tf]):
                raise ValueError(f'MISSING_CLOSED_COVERAGE_{tf} at {cutoff}')
            frames[tf] = df
            details[tf] = {'rows_closed': len(df), 'first_close':df['time'].iloc[0].isoformat(),
                           'last_close':df['time'].iloc[-1].isoformat(),
                           'source_filename':Path(MEMBERS[tf]).name,
                           'source_sha256':physical_hashes[tf]['sha256'],
                           'source_total_rows':metadata['total_source_rows']}
    produced = build_historical_event_objects(frames)
    replay = replay_closed_bars(frames, produced['objects'], as_of=cutoff)
    projection = replay['projection']
    samples = []
    for obj in sorted(projection.values(), key=lambda o:(str(o.tradable_time), o.id))[:20]:
        samples.append({'object_id':obj.id, 'type':obj.type.value, 'tf':obj.origin_tf,
                        'direction':obj.direction, 'parent_object':obj.parent_object,
                        'confirmation_time':str(obj.confirmation_time),
                        'tradable_time':str(obj.tradable_time),
                        'state_as_of':obj.state.value,
                        'linked_to_canonical_parent':bool(obj.parent_object)})
    report = {'status':replay['status'], 'control':control, 'as_of_utc':cutoff.isoformat(),
              'scope':'CANONICAL_PRODUCER_H4_M15_PILOT_ONLY',
              'sources':details, 'producer_counts':produced['counts'],
              'marketobjects_as_of':replay['objects'],
              'linked_objects_as_of':replay['linked_objects'],
              'object_types':dict(sorted(Counter(o.type.value for o in projection.values()).items())),
              'state_counts':dict(sorted(Counter(o.state.value for o in projection.values()).items())),
              'replay_stats':replay['stats'], 'gates':replay['gates'],
              'limitations':['Not a six-TF benchmark, seq/funnel/episodes not run',
                             'Producer reads full as-of history, not independently FULL/PREFIX-audited here',
                             'Fixed TF close=source open+duration; verify provider H4/D1 calendar',
                             'Samples are canonical MarketObjects, NOT trade signals']}
    output.mkdir(parents=True, exist_ok=True)
    (output/'replay_h4_m15_summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (output/'replay_h4_m15_sample.jsonl').write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in samples),encoding='utf-8')
    report['summary_sha256'] = hashlib.sha256((output/'replay_h4_m15_summary.json').read_bytes()).hexdigest()
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True,help='EURUSD.zip original')
    p.add_argument('--manifest',type=Path,default=ROOT/'benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json')
    p.add_argument('--control',choices=sorted(CONTROLS),required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run(source=args.source,manifest=args.manifest,control=args.control,output=args.output),indent=2,ensure_ascii=False))
