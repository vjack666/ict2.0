"""Ejecución rápida demo — sin path automático, configuración manual."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

# ── root del repo ─────────────────────────────────────────────────────────
REPO = Path(r"C:\Users\v_jac\Desktop\ICT SYSTEM")
sys.path.insert(0, str(REPO))

# ── deps ──────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np
warnings.filterwarnings("ignore")

# ── motor ─────────────────────────────────────────────────────────────────
from engine.bias.narrative import compute_htf_bias, HtfBias, BULLISH, BEARISH, NEUTRAL
from engine.bos.structure import detect_market_structure, StructureConfig

# ── paths ─────────────────────────────────────────────────────────────────
DATA_DIR = REPO / "datasets" / "eurusd_dukascopy_intraday_2006_2010" / "raw"
CSV_PATH = DATA_DIR / "EURUSD_M15_2006.csv.csv"

if not CSV_PATH.exists():
    raise FileNotFoundError(f"CSV no encontrado: {CSV_PATH}")

print("Cargando CSV M15 2006…")
df = pd.read_csv(str(CSV_PATH))
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
df = df.set_index("timestamp").sort_index()
print(f"✓ {len(df):,} velas M15  {df.index[0]} → {df.index[-1]}")

# ── resample a TFs superiores ─────────────────────────────────────────────
def resample_tf(df_in: pd.DataFrame, rule: str) -> pd.DataFrame:
    ohlc = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df_in.resample(rule).agg(ohlc).dropna(how="all")

m15 = df.copy()
h1  = resample_tf(m15, "1h").drop(columns=["volume"], errors="ignore")
h4  = resample_tf(m15, "4h").drop(columns=["volume"], errors="ignore")
d1  = resample_tf(m15, "1D").drop(columns=["volume"], errors="ignore")

print(f"\nTFs generados:")
for tf, txt in [("M15", m15), ("H1", h1), ("H4", h4), ("D1", d1)]:
    print(f"  ✓ {tf}: {len(txt):,} velas")

# ── detectar estructura (M15) ─────────────────────────────────────────────
config = StructureConfig(swing_lookback=2)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from engine.bos.structure import detect_market_structure as _dms
    ms_m15 = _dms(m15, config)
    for col in ["bos_dir", "bos_status", "choch_dir", "choch_status",
                "fvg_bullish", "fvg_bearish", "ob_bullish", "ob_bearish",
                "ob_direction", "liquidity_sweep_up", "liquidity_sweep_down",
                "displacement_bullish", "displacement_bearish"]:
        if col in ms_m15.frame.columns:
            m15[col] = ms_m15.frame[col]

print("\n✓ Estructura detectada en M15 (BOS/CHOCH/FVG/OB/SWEEP copiadas)")

# ── sesgo HTF en cada cierre H4 ───────────────────────────────────────────
def bias_at_h4(h4_ts: pd.Timestamp) -> HtfBias:
    d1_sub = d1.loc[d1.index <= h4_ts]
    h4_sub = h4.loc[h4.index <= h4_ts]
    h1_sub = h1.loc[h1.index <= h4_ts]
    if len(d1_sub) < 2 or len(h4_sub) < 2 or len(h1_sub) < 2:
        return HtfBias(d1=NEUTRAL, h4=NEUTRAL, h1=NEUTRAL)
    return compute_htf_bias(d1_sub, h4_sub, h1_sub)

# Solo probar los primeros 10 cierres H4
h4_ts_list = list(h4.index[:10])
print("\nSesgo HTF en los primeros 10 cierres H4:")
for h4_ts in h4_ts_list:
    b = bias_at_h4(h4_ts)
    print(f"  {h4_ts.strftime('%Y-%m-%d %H:%M')}  bias={b.direction}  D1={b.d1} H4={b.h4} H1={b.h1}")

print("\n✓ Pipeline top-down: HTF bias → estructura M15 → lista de objetos lista")