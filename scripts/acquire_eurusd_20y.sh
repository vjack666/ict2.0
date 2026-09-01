#!/usr/bin/env bash
# Regenerate EURUSD 20Y from Dukascopy into data/raw/EURUSD and datasets/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/data/raw/EURUSD"
DS="$ROOT/datasets/eurusd_dukascopy_20y"
mkdir -p "$OUT" "$DS" "$OUT/download"
cd "$OUT"
for tf in h1 h4 d1; do
  npx --yes dukascopy-node -i eurusd -from 2006-01-01 -to 2026-01-01 -t "$tf" -f csv -v true
done
python3 - <<'PY'
import pandas as pd
from pathlib import Path
raw = Path(".")
for tf, pat in [("H1","*h1*"),("H4","*h4*"),("D1","*d1*")]:
    files = list(raw.rglob(f"eurusd-{tf.lower()}*.csv")) + list(raw.glob(f"*{tf.lower()}*bid*.csv"))
    if not files:
        files = list(Path("download").glob(f"*{tf.lower()}*")) if Path("download").exists() else []
    # fallback scan
    if not files:
        files = [p for p in raw.rglob("*.csv") if tf.lower() in p.name.lower()]
    if not files:
        print("MISSING", tf); continue
    p = files[0]
    df = pd.read_csv(p)
    tcol = [c for c in df.columns if c.lower() in ("timestamp","time","date")][0]
    med = float(df[tcol].iloc[len(df)//2])
    unit = "ms" if med > 1e11 else ("s" if med > 1e9 else None)
    times = pd.to_datetime(df[tcol], unit=unit, utc=True) if unit else pd.to_datetime(df[tcol], utc=True)
    out = pd.DataFrame({
        "time": times.dt.tz_localize(None),
        "open": df[[c for c in df.columns if c.lower()=="open"][0]].astype(float),
        "high": df[[c for c in df.columns if c.lower()=="high"][0]].astype(float),
        "low": df[[c for c in df.columns if c.lower()=="low"][0]].astype(float),
        "close": df[[c for c in df.columns if c.lower()=="close"][0]].astype(float),
    }).dropna().sort_values("time").drop_duplicates("time")
    ok = (out.high >= out.low) & (out.high >= out[["open","close"]].max(1)) & (out.low <= out[["open","close"]].min(1))
    out = out[ok].reset_index(drop=True)
    out.to_csv(f"EURUSD_{tf}.csv", index=False)
    print(tf, len(out), out.time.min(), "->", out.time.max())
PY
cp -f EURUSD_*.csv "$DS/" 2>/dev/null || true
echo "Done. CSVs in $OUT and $DS"
