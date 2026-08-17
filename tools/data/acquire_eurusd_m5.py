#!/usr/bin/env python3
"""Acquire EUR/USD M5 candles from Dukascopy and write Parquet + metadata.

The script deliberately keeps the raw dataset outside Git. It is designed to
be reproducible by Hermes/CI with explicit start/end dates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

PIPELINE_VERSION = "1.0.0"
INSTRUMENT = "EURUSD"
TIMEFRAME = "M5"
TZ = "UTC"
BASE_URL = "https://datafeed.dukascopy.com/datafeed/EURUSD/5m"


def month_iter(start: datetime, end: datetime):
    cur = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    while cur < end:
        yield cur.year, cur.month
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            cur = datetime(cur.year, cur.month + 1, 1, tzinfo=timezone.utc)


def dukascopy_url(year: int, month: int) -> str:
    # Dukascopy monthly candle endpoint uses zero-based month numbers.
    return f"{BASE_URL}/{year}/{month - 1:02d}/BID_candles_min_5.bi5"


def download_month(year: int, month: int, session: requests.Session) -> bytes:
    url = dukascopy_url(year, month)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    if not response.content:
        raise RuntimeError(f"Empty response from {url}")
    return response.content


def decode_bi5(payload: bytes) -> pd.DataFrame:
    """Decode Dukascopy BI5 5-minute BID candles.

    Dukascopy BI5 records are 20-byte blocks: timestamp delta (ms), open/high/
    low/close integer prices and volume. The exact compression format has
    historically varied, therefore decoding is kept isolated and validated.
    """
    import lzma
    import struct

    raw = lzma.decompress(payload)
    if len(raw) % 20:
        raise ValueError(f"Invalid BI5 payload length: {len(raw)}")

    rows = []
    for offset in range(0, len(raw), 20):
        ms, op, hi, lo, cl, vol = struct.unpack(">5i", raw[offset:offset + 20])
        # Dukascopy candle timestamps are milliseconds from the month start.
        rows.append((ms, op, hi, lo, cl, vol))

    return pd.DataFrame(rows, columns=["offset_ms", "open", "high", "low", "close", "volume"])


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

    delta = df.timestamp.diff().dropna().dt.total_seconds()
    gaps = int((delta > 300).sum())
    return {
        "rows": int(len(df)),
        "first_timestamp": df.timestamp.iloc[0].isoformat(),
        "last_timestamp": df.timestamp.iloc[-1].isoformat(),
        "duplicate_timestamps": 0,
        "gaps_over_5m": gaps,
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
    with requests.Session() as session:
        session.headers["User-Agent"] = "ict2.0-data-pipeline/" + PIPELINE_VERSION
        for year, month in month_iter(start, end):
            payload = download_month(year, month, session)
            try:
                frame = decode_bi5(payload)
            except Exception as exc:
                raise RuntimeError(f"Could not decode Dukascopy {year}-{month:02d}: {exc}") from exc

            month_start = datetime(year, month, 1, tzinfo=timezone.utc)
            frame["timestamp"] = [month_start + timedelta(milliseconds=int(x)) for x in frame.pop("offset_ms")]
            frame["open"] = frame["open"] / 1_000_000
            frame["high"] = frame["high"] / 1_000_000
            frame["low"] = frame["low"] / 1_000_000
            frame["close"] = frame["close"] / 1_000_000
            frame = frame[(frame.timestamp >= start) & (frame.timestamp < end)]
            frames.append(frame)

    if not frames:
        raise RuntimeError("No monthly data downloaded")

    df = pd.concat(frames, ignore_index=True).sort_values("timestamp")
    df = df.drop_duplicates("timestamp", keep="first").reset_index(drop=True)
    stats = validate(df)

    df.to_parquet(out, index=False, engine="pyarrow")
    digest = sha256(out)
    meta = {
        "pipeline_version": PIPELINE_VERSION,
        "source": "Dukascopy Historical Data",
        "source_base_url": BASE_URL,
        "instrument": INSTRUMENT,
        "timeframe": TIMEFRAME,
        "timezone": TZ,
        "price_side": "BID",
        "requested_start": start.isoformat(),
        "requested_end_exclusive": end.isoformat(),
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "parquet_path": str(out),
        "sha256": digest,
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
