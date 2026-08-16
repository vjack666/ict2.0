import sys
sys.path.insert(0, ".")
import pandas as pd
from detectors.trend import detect_trend
from engine.htf_narrative import build_htf_narrative

SYM = "EURUSD"
END = "2026-08-14"
d1 = pd.read_parquet(f"data/raw/{SYM}/{SYM}_D1.parquet")
h4 = pd.read_parquet(f"data/raw/{SYM}/{SYM}_H4.parquet")
m15 = pd.read_parquet(f"data/raw/{SYM}/{SYM}_M15.parquet")
for df in (d1, h4, m15):
    df["time"] = pd.to_datetime(df["time"])

d1c = d1[d1["time"] <= END]
h4c = h4[h4["time"] <= END]
m15c = m15[m15["time"] <= END]

# htf_frames: D1/H4 como contexto padre del M15
htf_frames = {"D1": d1c, "H4": h4c}

narr = build_htf_narrative(m15c.tail(400), lookback=10, htf_frames=htf_frames, use_tools=True)
print("=== MOTOR DE LECTURA (use_tools=True) ===")
print("bias:", narr["bias"])
print("is_favorable:", narr["is_favorable"])
print("zone:", narr["zone"])
print("poi kind:", (narr["poi"] or {}).get("kind"))
print("liquidity side:", (narr["liquidity_target"] or {}).get("side"))
print("summary:", narr["summary"])
print("SMOKE MOTOR OK")
