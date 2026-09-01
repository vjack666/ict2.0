#!/usr/bin/env python3
"""Validate and canonicalize a Dukascopy-node EURUSD M5 CSV into Parquet + metadata."""
from __future__ import annotations
import argparse, hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

VERSION = "1.0.0"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--csv', required=True)
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--output', default='data/raw/EURUSD/EURUSD_M5.parquet')
    p.add_argument('--metadata', default='data/metadata/EURUSD_M5.json')
    a = p.parse_args()
    df = pd.read_csv(a.csv)
    required = ['timestamp','open','high','low','close','volume']
    if list(df.columns) != required:
        raise ValueError(f'Unexpected columns: {list(df.columns)}')
    if df.empty:
        raise ValueError('Dataset is empty')
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    numeric = required[1:]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors='raise')
    df = df.sort_values('timestamp').drop_duplicates('timestamp', keep='first').reset_index(drop=True)
    if not df.timestamp.is_monotonic_increasing:
        raise ValueError('Timestamps are not ordered')
    if df[numeric].isna().any().any() or not df[numeric].map(math.isfinite).all().all():
        raise ValueError('NaN/Inf detected')
    if (df.high < df[['open','close']].max(axis=1)).any(): raise ValueError('high below open/close')
    if (df.low > df[['open','close']].min(axis=1)).any(): raise ValueError('low above open/close')
    if (df.high < df.low).any(): raise ValueError('high < low')
    if (df.timestamp.dt.minute % 5 != 0).any() or (df.timestamp.dt.second != 0).any():
        raise ValueError('Timestamp is not aligned to UTC M5 boundary')
    start = pd.Timestamp(a.start, tz='UTC')
    end = pd.Timestamp(a.end, tz='UTC')
    df = df[(df.timestamp >= start) & (df.timestamp < end)].reset_index(drop=True)
    if df.empty: raise ValueError('No candles in requested range')
    out, meta = Path(a.output), Path(a.metadata)
    out.parent.mkdir(parents=True, exist_ok=True); meta.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False, engine='pyarrow')
    digest = sha256(out)
    delta = df.timestamp.diff().dropna().dt.total_seconds()
    payload = {
      'schema_version':'1', 'pipeline_version':VERSION,
      'source':'Dukascopy Historical Data via dukascopy-node',
      'source_url':'https://www.dukascopy.com/', 'instrument':'EURUSD',
      'timeframe':'M5', 'price_side':'BID', 'timezone':'UTC',
      'requested_start':start.isoformat(), 'requested_end_exclusive':end.isoformat(),
      'acquired_at':datetime.now(timezone.utc).isoformat(), 'parquet_path':str(out),
      'sha256':digest, 'validation':{
        'rows':len(df), 'first_timestamp':df.timestamp.iloc[0].isoformat(),
        'last_timestamp':df.timestamp.iloc[-1].isoformat(),
        'duplicate_timestamps':0, 'gaps_over_5m':int((delta > 300).sum()),
        'columns':{c:str(df[c].dtype) for c in df.columns}
      }
    }
    meta.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    Path(str(meta).replace('.json','.sha256')).write_text(f'{digest}  {out.name}\n', encoding='utf-8')
    print(json.dumps(payload, indent=2))

if __name__ == '__main__': main()
