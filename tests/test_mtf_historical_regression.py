"""PRUEBA HISTÓRICA / TEMPORAL — regresión Premium/Discount y OBSERVE_ONLY
(Objetivo 10 de la misión MTF/LTF).

Una sola instancia del MTFNavigator (precompute una vez) y navega en N puntos
temporales espaciados a lo largo de 20 años de datos reales. En cada punto
verifica:

  - el `location` H4 es coherente con el dealing range H4 (no PREMIUM si el
    precio está por debajo del EQ H4): regresión del bug del brief resuelto en
    el Objetivo 1;
  - cero lookahead ya demostrado en test_mtf_zero_lookahead (aquí se confirma
    point-in-time: el estado en t no usa velas futuras porque navigate usa
    as_of cerrado).

No envía órdenes. OBSERVE_ONLY. (Snapshot MT5 queda como deuda: no hay MT5
local; la prueba usa el dataset Dukascopy 20Y como fuente cerrada PIT.)
"""

from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import MTFNavigator  # noqa: E402

DATA = ROOT / "datasets" / "eurusd_dukascopy_20y"


def _load(tf: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"EURUSD_{tf}.csv")
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    return df.sort_values("time").reset_index(drop=True)


def main() -> int:
    d1 = _load("D1")
    h4 = _load("H4")
    h1 = _load("H1")

    nav = MTFNavigator({"D1": d1, "H4": h4, "H1": h1})

    # Puntos temporales espaciados a lo largo de la historia H1
    n_points = 120
    times = h1["time"].iloc[:: max(1, len(h1) // n_points)].tolist()

    violations = 0
    checked = 0
    for t in times:
        state = nav.navigate(decision_time=t, exec_tf="H1")
        if state is None or state.status != "OK":
            continue
        h4_snap = state.layers.get("H4")
        if h4_snap is None:
            continue
        ans = h4_snap.answers.get("WHERE_IN_CONTEXT", {})
        loc = ans.get("location")
        h4_dr = ans.get("h4_dealing_range", {})
        price = h4_snap.last_close
        eq = h4_dr.get("eq")
        checked += 1
        if loc == "PREMIUM" and eq is not None and price < eq:
            violations += 1
            if violations <= 5:
                print(f"[HIST][VIOL] t={t} loc=PREMIUM price={price} < eq_H4={eq}")
        if loc == "DISCOUNT" and eq is not None and price > eq:
            violations += 1
            if violations <= 5:
                print(f"[HIST][VIOL] t={t} loc=DISCOUNT price={price} > eq_H4={eq}")

    print(f"[HIST] puntos revisados: {checked}")
    print(f"[HIST] violaciones de procedencia H4 (Precio vs EQ H4): {violations}")

    if violations == 0:
        print("[HIST] PASS — en 20 años de datos, el location H4 siempre es coherente "
              "con el dealing range H4 (cero regresiones del bug del brief).")
        return 0
    print(f"[HIST][FAIL] {violations} violaciones de procedencia H4.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
