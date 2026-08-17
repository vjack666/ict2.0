#!/usr/bin/env python3
"""Acquire reproducible EURUSD H1/H4/D1 data from ejtraderLabs and canonicalize it.

M5 is intentionally not part of this pipeline until a stable public source is found.
The higher-timeframe data is suitable for developing and validating timeframe-agnostic
FVG/Order Block primitives, while M5-specific claims remain pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE_URL = "https://raw.githubusercontent.com/ejtraderLabs/historical-data/main/EURUSD"
TIMEFRAMES = {
    "H1": "EURUSDh1.csv",
    "H4": "EURUSDh4.csv",
    "D1": "EURUSDd1.csv",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonicalize(src: Path, tf: str, out: Path) -> dict:
    df = pd.read_csv(src)
    df.columns = [str(c).strip().lower() for c in df.columns]
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{tf}: missing columns: {sorted(missing)}")

    scale = 100000.0 if float(df["open"].median()) > 10 else 1.0
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(df["date"], utc=True),
            "open": pd.to_numeric(df["open"], errors="raise") / scale,
            "high": pd.to_numeric(df["high"], errors="raise") / scale,
            "low": pd.to_numeric(df["low"], errors="raise") / scale,
            "close": pd.to_numeric(df["close"], errors="raise") / scale,
        }
    ).dropna()
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)

    if df.empty:
        raise ValueError(f"{tf}: empty dataset")
    if not df.time.is_monotonic_increasing:
        raise ValueError(f"{tf}: timestamps not ordered")
    if (df.high < df[["open", "close"]].max(axis=1)).any():
        raise ValueError(f"{tf}: high below open/close")
    if (df.low > df[["open", "close"]].min(axis=1)).any():
        raise ValueError(f"{tf}: low above open/close")
    if (df.high < df.low).any():
        raise ValueError(f"{tf}: high below low")

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False, engine="pyarrow")
    digest = sha256(out)
    return {
        "instrument": "EURUSD",
        "timeframe": tf,
        "source": "ejtraderLabs/historical-data",
        "source_url": f"{BASE_URL}/{TIMEFRAMES[tf]}",
        "timezone": "UTC",
        "price_scale_applied": scale,
        "rows": len(df),
        "first_timestamp": df.time.iloc[0].isoformat(),
        "last_timestamp": df.time.iloc[-1].isoformat(),
        "sha256": digest,
        "parquet_path": str(out),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/raw/EURUSD")
    parser.add_argument("--metadata-dir", default="data/metadata")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    meta_dir = Path(args.metadata_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "ict2.0-data-pipeline/1.0"})
    manifest = {
        "schema_version": "1",
        "pipeline": "higher_tf_eurusd",
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "m5_status": "DEFERRED_NO_STABLE_PUBLIC_SOURCE",
        "datasets": {},
    }

    for tf, filename in TIMEFRAMES.items():
        csv_path = out_dir / filename
        response = session.get(f"{BASE_URL}/{filename}", timeout=60)
        response.raise_for_status()
        csv_path.write_bytes(response.content)
        parquet_path = out_dir / f"EURUSD_{tf}.parquet"
        info = canonicalize(csv_path, tf, parquet_path)
        info["csv_sha256"] = sha256(csv_path)
        manifest["datasets"][tf] = info
        print(f"{tf}: {info['rows']} rows | {info['first_timestamp']} -> {info['last_timestamp']}")

    manifest_path = meta_dir / "EURUSD_H1_H4_D1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
