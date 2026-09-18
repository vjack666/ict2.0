"""Pipeline ICT 2006 EURUSD M15 — ejecución rápida, sin bloqueos largos."""
import sys, os
sys.path.insert(0, os.getcwd())

from pathlib import Path
import pandas as pd
from engine.sequence import SequenceConfig
from backtest.replay import ReplayConfig, run_visual_replay

DATA_DIR = Path("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006")
CSV_FILES = sorted(DATA_DIR.glob("*.csv"))

# Leer todos los CSV, construir solo M15 concatenado (reducir carga)
dfs = []
for f in CSV_FILES:
    df = pd.read_csv(f)
    if "timestamp" in df.columns:
        df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"])
    elif "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    else:
        raise KeyError(f"{f.name}: falta time o timestamp")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[[c for c in ["time","open","high","low","close"] if c in df.columns]].copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    for col in ("open","high","low","close"):
        df[col] = pd.to_numeric(df[col], errors="raise").astype(float)
    dfs.append(df)

m15_all = pd.concat(dfs, ignore_index=True).sort_values("time").drop_duplicates(subset=["time"], keep="first")
print("Total filas M15 2006:", len(m15_all))
# Usar solo primeros 5000 registros para evitar timeout en replay (patrón canónico verificado)
m15_all = m15_all.iloc[:5000].reset_index(drop=True)
print("Usando submuestra M15 (primeros 5000 registros):", len(m15_all))

raw_frames = {
    "M15": m15_all,
}
# También agregar H1/H4/D1 resampleados desde esta submuestra (rápido)
m15_all.set_index("time", inplace=True)
for tf_name, freq in [("H1","1h"),("H4","4h"),("D1","D")]:
    res = m15_all.resample(freq).agg({"open":"first","high":"max","low":"min","close":"last"}).dropna(subset=["open"])
    res.reset_index(inplace=True)
    res["time"] = pd.to_datetime(res["time"], utc=True)
    raw_frames[tf_name] = res

# Asegurar M15 con time restaurado como columna
m15_tmp = m15_all.copy().reset_index()
raw_frames["M15"] = m15_tmp[["time","open","high","low","close"]].copy()
raw_frames["M15"]["time"] = pd.to_datetime(raw_frames["M15"]["time"], utc=True)

print("Frames:", {k: len(v) for k,v in raw_frames.items()})

config = ReplayConfig(
    symbol="EURUSD",
    timeframe="M15",
    use_multitf_context=True,
    sequence=SequenceConfig(counter_trend=False),
)

print("Ejecutando run_visual_replay ...")
artifact = run_visual_replay(raw_frames, config)
print("Artifact generado. Señales:", len(artifact.signals), "| Trades:", len(artifact.trades))

# CSV
rows = []
for s in artifact.signals:
    rows.append({
        "time": s.get("time"),
        "direction": s.get("direction"),
        "entry": s.get("entry"),
        "sl": s.get("sl") or s.get("stop_loss"),
        "tp": s.get("tp") or s.get("take_profit"),
        "htf_aligned": s.get("htf_aligned"),
        "sb_confirmed": s.get("sb_confirmed") or s.get("structure_confirmed"),
    })

csv_path = Path("reports/ict_pipeline_2006_signals.csv")
csv_path.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(csv_path, index=False)
print("CSV:", csv_path.resolve(), "filas:", len(rows))

longs = sum(1 for r in rows if r.get("direction") == 1)
shorts = sum(1 for r in rows if r.get("direction") == -1)
neutrals = sum(1 for r in rows if r.get("direction") == 0)

# Win rate
outcomes = [t.get("outcome") for t in artifact.trades if t.get("outcome") is not None]
win_rate = None
if outcomes:
    wins = sum(1 for o in outcomes if str(o).lower() in ("tp","win","won","profit","positive","completed"))
    win_rate = wins / len(outcomes)

print("\n=== RESULTADO ICT PIPELINE 2006 ===")
print("Señales:", len(artifact.signals))
print("Dirección — Long:", longs, "| Short:", shorts, "| Neutral:", neutrals)
print("Trades (con outcome):", len(outcomes))
print("Win rate:", f"{win_rate:.2%}" if win_rate is not None else "No disponible (sin outcomes)")
print("CSV:", csv_path.resolve())
if rows:
    print("Primeras filas:")
    for r in rows[:3]:
        print(r)
