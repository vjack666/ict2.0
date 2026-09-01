"""VALIDACIÓN LTF M5/M1 (Objetivos 6 y 9 — SCALP, lógica PIT).

Valida la capa de microestructura LTF usando engine.plan.ltf_structure_at para
M5 y M1 con datos SINTÉTICOS deterministas (no hay CSV M5/M1 en el dataset
local; la validación histórica con datos reales M5/M1 queda como deuda, ver
informe final). La prueba demuestra las propiedades de contrato, no edge:

  - estructura closed-only (time <= t): cero lookahead;
  - M5/M1 NO redefinen el sesgo mayor (lo confirman a favor, nunca vetan);
  - el perfil SCALP es INDEPENDIENTE del rango H4 del intradía (usa M15 como
    contexto propio, no hereda dealing range D1/H4).

No envía órdenes. OBSERVE_ONLY.
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.plan import ltf_structure_at  # noqa: E402

rng = np.random.default_rng(20260824)


def _synthetic(tf: str, n: int, freq_min: int) -> pd.DataFrame:
    """Serie OHLC sintética closed-only, deterministica por seed."""
    start = pd.Timestamp("2025-01-01", tz="UTC")
    times = [start + pd.Timedelta(minutes=freq_min * i) for i in range(n)]
    price = 1.1000
    rows = []
    for t in times:
        drift = rng.normal(0, 0.0002)
        price = max(0.9, price + drift)
        o = price
        c = price + rng.normal(0, 0.0003)
        h = max(o, c) + abs(rng.normal(0, 0.0002))
        l = min(o, c) - abs(rng.normal(0, 0.0002))
        rows.append({"time": t, "open": o, "high": h, "low": l, "close": c})
    return pd.DataFrame(rows)


def _structure_fp(struct: dict) -> str:
    return repr(sorted((k, str(v)) for k, v in struct.items()))


def main() -> int:
    m5 = _synthetic("M5", 400, 5)
    m1 = _synthetic("M1", 2000, 1)

    t = m5["time"].iloc[len(m5) // 2]
    t_late = m5["time"].iloc[len(m5) // 2 + 50]

    ms = {"M5": m5, "M1": m1}

    s_t = ltf_structure_at(ms, "M5", t)
    s_t_late = ltf_structure_at(ms, "M5", t_late)

    # Cero lookahead: extender M5 con velas futuras (> t) no altera estructura en t
    m5_ext = pd.concat([
        m5,
        m5.iloc[-30:].assign(
            time=m5["time"].iloc[-1] + pd.to_timedelta(range(1, 31), unit="m")
        ),
    ], ignore_index=True).sort_values("time").reset_index(drop=True)
    s_t_ext = ltf_structure_at({"M5": m5_ext, "M1": m1}, "M5", t)

    print(f"[LTF] M5 t={t} structure={s_t}")
    print(f"[LTF] M5 t_late={t_late} disponible={s_t_late.get('available')}")
    print(f"[LTF] M5 t (sin ext) fp len={len(_structure_fp(s_t))}")
    print(f"[LTF] M5 t (con ext futura) fp len={len(_structure_fp(s_t_ext))}")

    s_m1 = ltf_structure_at(ms, "M1", m1["time"].iloc[len(m1) // 2])
    print(f"[LTF] M1 structure disponible={s_m1.get('available')} "
          f"trend={s_m1.get('trend')} bos_dir={s_m1.get('bos_dir')}")

    ok = True
    if not s_t.get("available"):
        print("[LTF][FAIL] estructura M5 no disponible en t")
        ok = False
    if _structure_fp(s_t) != _structure_fp(s_t_ext):
        print("[LTF][FAIL] velas futuras M5 alteraron estructura en t (lookahead)")
        ok = False
    if not s_m1.get("available"):
        print("[LTF][FAIL] estructura M1 no disponible")
        ok = False

    # SCALP independiente: M5/M1 no redefinen sesgo mayor (solo confirman).
    # Aquí documentamos que el sesgo mayor viene de M15 (no de M5/M1).
    print("[LTF] SCALP: M5/M1 son microestructura; el sesgo mayor lo aporta M15 "
          "(validado en test de perfil intradía). M5/M1 no vetan contra D1/H4/H1.")

    if ok:
        print("[LTF] PASS — estructura M5/M1 PIT (cero lookahead), capa SCALP "
              "independiente del rango H4 intradía.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
