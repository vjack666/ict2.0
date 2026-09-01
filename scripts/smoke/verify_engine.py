"""Verifica que engine/bias_from_tools.py sigue funcionando tras los cambios.

Corre annotate_with_tools y bias_from_tools sobre 1 mes de M5 sin error y
reporta un resumen. Debe funcionar TANTO si existe el modelo IA como si no
(_load_model cachea None y el score queda geometrico).
"""
from __future__ import annotations
import sys, time
sys.path.insert(0, ".")
import pandas as pd
from engine.bias_from_tools import annotate_with_tools, bias_from_tools

SYM = "EURUSD"
t0 = time.time()
d = pd.read_parquet(f"data/raw/{SYM}/{SYM}_M5.parquet")
d = d.assign(time=pd.to_datetime(d["time"]))
# ~1 mes (8640 velas M5 aprox) al final del historial
m = d.tail(9000).reset_index(drop=True)
print(f"cargado 1 mes M5: {len(m)} barras [{time.time()-t0:.1f}s]")

t1 = time.time()
out = annotate_with_tools(m, symbol=SYM)
print(f"annotate_with_tools OK en {time.time()-t1:.1f}s | columnas={len(out.columns)}")

# verificar campos clave presentes
for col in ("bos_dir", "choch_dir", "choch_real", "choch_score"):
    assert col in out.columns, f"falta columna {col}"
n_choch = int((out["choch_dir"] != 0).sum())
print(f"CHOCH marcados en 1 mes: {n_choch}")

# bias en varios tiempos
ts = [m["time"].iloc[int(p * len(m))] for p in (0.3, 0.6, 0.9)]
for t in ts:
    b = bias_from_tools(out, t)
    print(f"  bias @ {t}: {b}")

# sanity: choch_score rango
sc = out.loc[out["choch_dir"] != 0, "choch_score"]
if len(sc):
    print(f"choch_score min/max: {sc.min():.1f}/{sc.max():.1f} | con IA proba media: "
          f"{out.loc[out['choch_dir']!=0,'choch_ia_prob'].mean():.3f}")
print("VERIFY OK")
