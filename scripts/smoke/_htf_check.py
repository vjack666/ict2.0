import sys
sys.path.insert(0, ".")
import pandas as pd, numpy as np

d = pd.read_parquet("data/raw/EURUSD/EURUSD_D1.parquet")
d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
cut = pd.Timestamp("2026-08-14", tz="UTC")
d = d[d["time"] <= cut].reset_index(drop=True)
print("D1 velas totales:", len(d), "| ultima:", d["time"].iloc[-1].date())
print("max 2026:", round(d["high"].max(), 5), "| min 2026:", round(d["low"].min(), 5))
ym = d[d["time"].dt.year == 2026]
print("max mayo:", round(ym[ym["time"].dt.month == 5]["high"].max(), 5))
jun = ym[ym["time"].dt.month == 6]
print("min jun:", round(jun["low"].min(), 5), "fecha", jun.loc[jun["low"].idxmin(), "time"].date())
jul = ym[ym["time"].dt.month == 7]
print("min jul:", round(jul["low"].min(), 5), "fecha", jul.loc[jul["low"].idxmin(), "time"].date())
print("cierre 14ago:", round(d["close"].iloc[-1], 5), "| apertura 14ago:", round(d["open"].iloc[-1], 5))
last = d.tail(40)
r = last["high"].max() - last["low"].min()
pos = (last["close"].iloc[-1] - last["low"].min()) / r if r > 0 else 0.5
print("posicion cierre en rango 40 velas D1: %.2f" % pos)
from tools.swing import SwingTool
sw = SwingTool(tf="D1").run(d, symbol="EURUSD")
labs = [(e.signal, round(e.price, 5), e.status) for e in sw[-8:]]
print("ultimos swings D1:", labs)
