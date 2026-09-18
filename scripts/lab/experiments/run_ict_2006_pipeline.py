"""Orquestación ICT pipeline 2006 EURUSD M15 — replay canónico, sin modificar motor."""
import sys, os
sys.path.insert(0, os.getcwd())
import pandas as pd
from pathlib import Path
from backtest.replay import ReplayConfig, run_visual_replay
from engine.sequence import SequenceConfig

DATA_DIR = Path("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006")
CSV_FILES = sorted(DATA_DIR.glob("*.csv"))
print("Archivos CSV 2006:", len(CSV_FILES))

frames_dict = {}
for f in CSV_FILES:
    df = pd.read_csv(f)
    # Renombrar timestamp (ms unix) → time (datetime UTC); si ya está 'time', usar directo
    if "timestamp" in df.columns:
        df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"])
    elif "time" not in df.columns:
        raise KeyError(f"{f.name}: sin columna time ni timestamp")
    # Asegurar time como datetime UTC
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.sort_values("time").reset_index(drop=True)
    # Seleccionar OHLC mínimos + time; ignorar volume si existe
    keep = [c for c in ["time","open","high","low","close"] if c in df.columns]
    df = df[keep].copy()
    # Resample M15→M15 no es necesario; guardamos como M15 base.
    # Para multitimeframe construimos H1, H4, D1 desde M15 concatenado
    # Pero run_visual_replay espera cada tf como DataFrame; construimos dict con M15, H1, H4, D1
    # Usamos el archivo como mes; concatenamos todos para tener serie completa de 2006
    # (los 12 archivos cubren todo 2006 consecutivamente)
    key = f.name.replace(".csv","")
    frames_dict[key] = df

# Concatenar todos los meses M15 en orden cronológico para multitimeframe único
m15_df = pd.concat(frames_dict.values(), ignore_index=True)
m15_df = m15_df.sort_values("time").reset_index(drop=True)
# Quitar duplicados de tiempo (posibles solapamientos mes-mes)
m15_df = m15_df.drop_duplicates(subset=["time"], keep="first")

# Resample M15 → H1, H4, D1
m15_df.set_index("time", inplace=True)
h1 = m15_df.resample("1h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna(subset=["open"])
h4 = m15_df.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna(subset=["open"])
d1 = m15_df.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna(subset=["open"])
# Restaurar índices como columna time
for df in (h1,h4,d1):
    df.reset_index(inplace=True)
    df["time"] = pd.to_datetime(df["time"], utc=True)

# Dict con tf como claves canónicas: M15, H1, H4, D1
raw_frames = {
    "M15": m15_df.reset_index(),
    "H1": h1,
    "H4": h4,
    "D1": d1,
}
# Corregir M15 time
raw_frames["M15"]["time"] = pd.to_datetime(raw_frames["M15"]["time"], utc=True)

print("M15 filas:", len(raw_frames["M15"]))
print("H1 filas:", len(raw_frames["H1"]), "| H4:", len(raw_frames["H4"]), "| D1:", len(raw_frames["D1"]))

# Verificar columnas requeridas
for tf, df in raw_frames.items():
    missing = set(["time","open","high","low","close"]) - set(df.columns)
    if missing:
        raise KeyError(f"{tf} falta: {missing}")

# Config replay canónico
config = ReplayConfig(
    symbol="EURUSD",
    timeframe="M15",
    use_multitf_context=True,
    sequence=SequenceConfig(counter_trend=False),
)

print("Ejecutando run_visual_replay ...")
artifact = run_visual_replay(raw_frames, config)
print("Artifact generado. señales:", len(artifact.signals), "| trades:", len(artifact.trades))

# Construir CSV
rows = []
for s in artifact.signals:
    rows.append({
        "time": s.get("time") or s.get("timestamp"),
        "direction": s.get("direction") or s.get("dir") or s.get("side"),
        "entry": s.get("entry") or s.get("price"),
        "sl": s.get("sl") or s.get("stop_loss"),
        "tp": s.get("tp") or s.get("take_profit"),
        "htf_aligned": s.get("htf_aligned") or s.get("htf_context") or s.get("htf_trend"),
        "sb_confirmed": s.get("sb_confirmed") or s.get("structure_confirmed") or False,
    })

csv_path = Path("reports/ict_pipeline_2006_signals.csv")
csv_path.parent.mkdir(parents=True, exist_ok=True)
df_out = pd.DataFrame(rows)
df_out.to_csv(csv_path, index=False)
print("CSV guardado:", csv_path, "filas:", len(df_out))

# Estadísticas
n_signals = len(artifact.signals)
# Desglose long/short por direction
longs = sum(1 for r in rows if str(r.get("direction")).lower() in ("long","buy","up"))
shorts = sum(1 for r in rows if str(r.get("direction")).lower() in ("short","sell","down"))
# Win rate si outcome disponible en trades
outcomes = [t.get("outcome") for t in artifact.trades if t.get("outcome") is not None]
win_rate = None
if outcomes:
    wins = sum(1 for o in outcomes if str(o).lower() in ("win","won","profit","positive"))
    win_rate = wins / len(outcomes)

print("\n=== RESULTADO ICT PIPELINE 2006 ===")
print("Señales encontradas:", n_signals)
print("Long:", longs, "| Short:", shorts)
print("Trades (con outcome):", len(outcomes))
if win_rate is not None:
    print(f"Win rate: {win_rate:.2%} ({sum(1 for o in outcomes if str(o).lower() in ('win','won','profit','positive'))}/{len(outcomes)})")
else:
    print("Win rate: no disponible (sin outcome en artifact.trades)")
print("CSV:", csv_path.resolve())
# Mostrar primeras filas CSV
if not df_out.empty:
    print(df_out.head(3).to_string(index=False))
