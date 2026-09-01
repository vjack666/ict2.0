"""Trae y organiza los parquet de forex del disco a ICT SYSTEM/data/.

Fuentes conocidas (acotadas para no recorrer todo el home):
- Desktop/GRID SCAPL 2/datasets/mt5_clean/*.parquet  (OHLC crudo: timestamp,open,high,low,close,tick_volume,spread)
- Desktop/legacy_smc_backup/src/_legacy_data/data_raw/*.parquet (OHLC crudo: time,open,...)
- Desktop/legacy_smc_backup/src/_legacy_data/data_mt5/*.parquet
- Desktop/SMC-SYSTEMS/data/raw/*.parquet
- Desktop/SMC-SYSTEMS/data/ml/**/*.parquet  (features ya procesadas -> carpeta ml/)

Estructura destino (ordenada):
- data/raw/<SYMBOL>/<SYMBOL>_<TF>.parquet   (OHLC crudo; normaliza col tiempo a 'time')
- data/ml/<SYMBOL|grupo>/<nombre>.parquet    (features ya procesadas)

Conflicto mismo (symbol,tf) en raw: se queda el de mas filas.
"""
import os, glob, shutil
import pandas as pd

ROOT = r"C:/Users/v_jac/Desktop/ICT SYSTEM"
DEST = os.path.join(ROOT, "data")

RAW_SOURCES = [
    r"C:/Users/v_jac/Desktop/GRID SCAPL 2/datasets/mt5_clean",
    r"C:/Users/v_jac/Desktop/legacy_smc_backup/src/_legacy_data/data_raw",
    r"C:/Users/v_jac/Desktop/legacy_smc_backup/src/_legacy_data/data_mt5",
    r"C:/Users/v_jac/Desktop/SMC-SYSTEMS/data/raw",
]
ML_SOURCES = [
    r"C:/Users/v_jac/Desktop/SMC-SYSTEMS/data/ml",
    r"C:/Users/v_jac/Desktop/GRID SCAPL 2/datasets",  # structural_*.parquet (ML/derived)
]

SYMS = ["EURUSD","AUDUSD","GBPUSD","NZDUSD","USDCAD","USDCHF","USDJPY","XAUUSD"]
TFS  = ["M1","M3","M5","M15","H1","H4","D1"]


def sym_tf_from_name(fname):
    base = os.path.splitext(os.path.basename(fname))[0].upper()
    sym = next((s for s in SYMS if s in base), None)
    # ordenar TFs por longitud DESC para que M15 no matchee como M1
    for tf in sorted(TFS, key=len, reverse=True):
        # borde: el TF debe estar al final o tras '_' y no seguido de digito
        import re
        if re.search(r"(?:^|_)%s(?:\.|$|\D)" % tf, base):
            return sym, tf
    return sym, None


def normalize_time(df):
    for c in ("timestamp","time","Time","datetime","date"):
        if c in df.columns:
            if c != "time":
                df = df.rename(columns={c: "time"})
            break
    return df


raw_best = {}   # (sym,tf) -> (nrows, src)
raw_copied = []

# --- RAW ---
for src in RAW_SOURCES:
    if not os.path.isdir(src):
        continue
    for f in glob.glob(os.path.join(src, "*.parquet")):
        name = os.path.basename(f)
        if "STRUCTURAL" in name.upper() or "ML_" in name.upper() or name.startswith("v"):
            continue  # features, no raw
        sym, tf = sym_tf_from_name(f)
        if not sym or not tf:
            continue
        try:
            n = len(pd.read_parquet(f))
        except Exception as e:
            print("SKIP (no lee) ", f, e); continue
        key = (sym, tf)
        cur = raw_best.get(key)
        if cur is None or n > cur[0]:
            raw_best[key] = (n, f)

for (sym, tf), (n, f) in sorted(raw_best.items()):
    d = os.path.join(DEST, "raw", sym)
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f"{sym}_{tf}.parquet")
    df = normalize_time(pd.read_parquet(f))
    df.to_parquet(out, index=False)
    raw_copied.append((sym, tf, n, out))
    print(f"[RAW] {sym} {tf}  {n} filas  <- {os.path.basename(f)}")

# --- ML / DERIVED ---
ml_copied = []
for src in ML_SOURCES:
    if not os.path.isdir(src):
        continue
    for f in glob.glob(os.path.join(src, "**", "*.parquet"), recursive=True):
        name = os.path.basename(f).lower()
        if "pyarrow" in f.lower():
            continue
        if "structural" in name or name.startswith("v") or "ml_" in name or "dataset" in name:
            # carpeta ml/
            grp = os.path.basename(os.path.dirname(f)).lower()
            d = os.path.join(DEST, "ml", grp if grp not in ("ml","datasets") else "")
            d = os.path.join(DEST, "ml")
            os.makedirs(d, exist_ok=True)
            out = os.path.join(d, os.path.basename(f))
            if not os.path.exists(out):
                shutil.copy2(f, out)
                ml_copied.append(out)
                print(f"[ML ] {os.path.basename(f)}")

print("\n=== RESUMEN ===")
print(f"RAW copiados: {len(raw_copied)}  (símbolos: {sorted(set(s for s,_,_,_ in raw_copied))})")
print(f"ML/derived copiados: {len(ml_copied)}")
print(f"Total data/: {len(glob.glob(os.path.join(DEST,'**','*.parquet'), recursive=True))} parquet")
