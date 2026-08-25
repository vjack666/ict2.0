"""AUDITORÍA — Procedencia de Premium/Discount (Objetivo 1 / 7 de la misión MTF/LTF).

Demuestra que el `location` que emite MTFNavigator.WHERE_IN_CONTEXT para H4
tiene procedencia demostrable por temporalidad:

  1. Se calcula sobre el DEALING RANGE DEL PROPIO TF (H4), NO sobre el rango D1.
  2. Usa EQ = 50% del rango (banda ambigua +/-12%), NO tercios 0.33/0.67.
  3. Expone h4_dealing_range / d1_dealing_range con sus EQ para auditoría.

La prueba replica el cálculo del dealing range H4 (rolling 50 de high/low, igual
que engine.mtf_navigation._precompute_layers) y clasifica con EQ50%, luego
compara contra lo que devuelve el MTFNavigator. También reporta el caso del
brief: EQ H4 vs cierres recientes, para confirmar que ya NO se reporta Premium
cuando el precio está por debajo del EQ H4.

No envía órdenes; OBSERVE_ONLY.
"""

from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import MTFNavigator, TimeframeLayer  # noqa: E402
from engine.dealing_range_eq import classify_zone  # noqa: E402

DATA = ROOT / "datasets" / "eurusd_dukascopy_20y"
LOOKBACK = 50
_EQ_BAND = 0.12


def _load(tf: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"EURUSD_{tf}.csv")
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    return df.sort_values("time").reset_index(drop=True)


def _dealing_range_independent(df: pd.DataFrame, decision_time: pd.Timestamp) -> dict:
    """Replica engine.mtf_navigation dealing range H4: rolling(50) high/low."""
    times = df["time"]
    win = df.loc[times <= decision_time]
    if len(win) < 3:
        return {"high": None, "low": None, "eq": None}
    i = len(win) - 1
    a = max(0, i - LOOKBACK + 1)
    sub = win.iloc[a : i + 1]
    rh = float(sub["high"].max())
    rl = float(sub["low"].min())
    eq = 0.5 * (rh + rl)
    return {"high": rh, "low": rl, "eq": eq}


def _classify_independent(dr: dict, price: float) -> str:
    if dr["high"] is None or dr["high"] <= dr["low"]:
        return "UNKNOWN"
    eq = dr["eq"]
    rng = dr["high"] - dr["low"]
    band = rng * _EQ_BAND
    if abs(price - eq) <= band:
        return "EQUILIBRIUM"
    return "DISCOUNT" if price < eq else "PREMIUM"


def main() -> int:
    d1 = _load("D1")
    h4 = _load("H4")
    h1 = _load("H1")

    # decision_time = última vela H1 cerrada (as-of cerrado, sin look-ahead)
    decision_time = h1["time"].iloc[-1]

    nav = MTFNavigator({"D1": d1, "H4": h4, "H1": h1})
    state = nav.navigate(decision_time=decision_time, exec_tf="H1")
    if state is None or state.status != "OK":
        print(f"[AUDIT][FAIL] navigate status={getattr(state, 'status', None)}")
        return 1

    h4_snap = state.layers["H4"]
    ans = h4_snap.answers["WHERE_IN_CONTEXT"]
    loc = ans["location"]
    h4_dr = ans["h4_dealing_range"]
    d1_dr = ans["d1_dealing_range"]
    price = h4_snap.last_close

    # Cálculo independiente sobre el mismo as-of
    dr_indep = _dealing_range_independent(h4, decision_time)
    loc_indep = _classify_independent(dr_indep, price)

    print(f"[AUDIT] decision_time={decision_time}")
    print(f"[AUDIT] H4 last_close={price}")
    print(f"[AUDIT] MTFNavigator location={loc}")
    print(f"[AUDIT]   h4_dealing_range high={h4_dr['high']} low={h4_dr['low']} eq={h4_dr['eq']}")
    print(f"[AUDIT]   d1_dealing_range high={d1_dr['high']} low={d1_dr['low']} eq={d1_dr['eq']}")
    print(f"[AUDIT]   location_vs_d1={d1_dr.get('location_vs_d1')}")
    print(f"[AUDIT] Cálculo independiente H4: eq={dr_indep['eq']} location={loc_indep}")
    print(f"[AUDIT] Cierres H4 recientes (últimas 5): "
          f"{[round(x,5) for x in h4['close'].tail(5).tolist()]}")

    # Verificaciones
    ok = True
    if loc != loc_indep:
        print(f"[AUDIT][FAIL] location MTFNavigator ({loc}) != independiente ({loc_indep})")
        ok = False
    if h4_dr["eq"] is None or abs((h4_dr["eq"] or 0) - (dr_indep["eq"] or -1)) > 1e-9:
        print(f"[AUDIT][FAIL] h4_dealing_range.eq ({h4_dr['eq']}) != independiente ({dr_indep['eq']})")
        ok = False
    # El location NO debe ser PREMIUM si el precio está por debajo del EQ H4
    if loc == "PREMIUM" and price < (h4_dr["eq"] or float('inf')):
        print(f"[AUDIT][FAIL] PREMIUM reportado con precio {price} < EQ_H4 {h4_dr['eq']} "
              f"(discrepancia del brief resuelta incorrectamente)")
        ok = False
    if loc == "DISCOUNT" and price > (h4_dr["eq"] or float('-inf')):
        print(f"[AUDIT][FAIL] DISCOUNT reportado con precio {price} > EQ_H4 {h4_dr['eq']}")
        ok = False

    if ok:
        print(f"[AUDIT] PASS — procedencia H4 demostrada: location={loc} "
              f"sobre dealing range H4 (eq={h4_dr['eq']}), separado de D1 (eq={d1_dr['eq']}).")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
