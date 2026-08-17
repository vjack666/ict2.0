#!/usr/bin/env python3
"""Acquire EUR/USD M5 candles from Dukascopy and write Parquet + metadata.

Dukascopy native M1 candle BI5 records are 24 bytes: 5 big-endian unsigned
integers (seconds, OHLC) plus one float volume. The pipeline decodes M1 BID
candles and aggregates them deterministically to UTC M5.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import lzma
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

PIPELINE_VERSION = "1.2.0"
INSTRUMENT = "EURUSD"
TIMEFRAME = "M5"
TZ = "UTC"
PRICE_DIVISOR = 100_000.0
BASE_URL = "https://datafeed.dukascopy.com/datafeed/EURUSD"


def day_iter(start: datetime, end: datetime):
    cur = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    while cur < end:
        yield cur
        cur += timedelta(days=1)


def m1_url(day: datetime) -> str:
    return f"{BASE_URL}/{day.year}/{day.month - 1:02d}/{day.day:02d}/BID_candles_min_1.bi5"


def download_day(day: datetime, session: requests.Session) -> tuple[str, bytes]:
    url = m1_url(day)
    response = session.get(url, timeout=60)
    if response.status_code in (404, 410) or not response.content:
        return url, b""
    response.raise_for_status()
    return url, response.content


def decode_m1(payload: bytes, day: datetime) -> pd.DataFrame:
    raw = lzma.decompress(payload)
    if len(raw) % 24:
        raise ValueError(f"Invalid M1 BI5 payload length: {len(raw)}")

    rows = []
    for offset in range(0, len(raw), 24):
        seconds, op, hi, lo, cl, vol = struct.unpack(">IIIIIf", raw[offset:offset + 24])
        rows.append((
            day + timedelta(seconds=int(seconds)),
            op / PRICE_DIVISOR,
            hi / PRICE_DIVISOR,
            lo / PRICE_DIVISOR,
            cl / PRICE_DIVISOR,
            float(vol),
        ))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


def aggregate_m5(m1: pd.DataFrame) -> pd.DataFrame:
    if m1.empty:
        return m1.copy()
    x = m1.set_index("timestamp").sort_index()
    return (
        x.resample("5min", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )


def validate(df: pd.DataFrame) -> dict:
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    if df.empty:
        raise ValueError("Dataset is empty")
    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps detected")
    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError("Timestamps are not strictly ordered")

    numeric = ["open", "high", "low", "close", "volume"]
    if not df[numeric].apply(lambda s: s.map(math.isfinite).all()).all():
        raise ValueError("NaN/Inf detected")
    if (df.high < df[["open", "close"]].max(axis=1)).any():
        raise ValueError("high is below open/close")
    if (df.low > df[["open", "close"]].min(axis=1)).any():
        raise ValueError("low is above open/close")
    if (df.high < df.low).any():
        raise ValueError("high < low")

    # Validate M5 timestamps themselves, not the distance between consecutive
    # trading candles: weekends/holidays naturally create large gaps.
    if (df.timestamp.dt.minute % 5 != 0).any() or (df.timestamp.dt.second != 0).any():
        raise ValueError("Timestamp is not aligned to UTC M5 boundary")

    delta = df.timestamp.diff().dropna().dt.total_seconds()
    return {
        "rows": int(len(df)),
        "first_timestamp": df.timestamp.iloc[0].isoformat(),
        "last_timestamp": df.timestamp.iloc[-1].isoformat(),
        "duplicate_timestamps": 0,
        "gaps_over_5m": int((delta > 300).sum()),
        "columns": {c: str(df[c].dtype) for c in df.columns},
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True, help="UTC date YYYY-MM-DD")
    p.add_argument("--end", required=True, help="UTC date YYYY-MM-DD, exclusive")
    p.add_argument("--output", default="data/raw/EURUSD/EURUSD_M5.parquet")
    p.add_argument("--metadata", default="data/metadata/EURUSD_M5.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    if end <= start:
        raise ValueError("--end must be after --start")

    out = Path(args.output)
    meta_path = Path(args.metadata)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    frames = []
    source_urls = []
    empty_days = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "ict2.0-data-pipeline/" + PIPELINE_VERSION
        for day in day_iter(start, end):
            url, payload = download_day(day, session)
            source_urls.append(url)
            if not payload:
                empty_days.append(day.date().isoformat())
                continue
            frames.append(decode_m1(payload, day))

    if not frames:
        raise RuntimeError("No M1 data downloaded")

    m1 = pd.concat(frames, ignore_index=True)
    m1 = m1[(m1.timestamp >= start) & (m1.timestamp < end)]
    df = aggregate_m5(m1)
    df = df.drop_duplicates("timestamp", keep="first").sort_values("timestamp").reset_index(drop=True)
    stats = validate(df)

    df.to_parquet(out, index=False, engine="pyarrow")
    digest = sha256(out)
    meta = {
        "schema_version": "1",
        "pipeline_version": PIPELINE_VERSION,
        "source": "Dukascopy Historical Data",
        "source_base_url": BASE_URL,
        "source_urls_count": len(source_urls),
        "instrument": INSTRUMENT,
        "timeframe": TIMEFRAME,
        "source_timeframe": "M1",
        "aggregation": "UTC 5-minute OHLCV from native M1 BID candles",
        "timezone": TZ,
        "price_side": "BID",
        "price_divisor": PRICE_DIVISOR,
        "requested_start": start.isoformat(),
        "requested_end_exclusive": end.isoformat(),
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "parquet_path": str(out),
        "sha256": digest,
        "empty_days": empty_days,
        "validation": stats,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    Path(str(meta_path).replace(".json", ".sha256")).write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
