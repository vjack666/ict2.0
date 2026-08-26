"""Adaptador mínimo Wyckoff por barra para EXP-WYCKOFF-ICT-01 (preflight).

Determinista, solo-lectura, point-in-time. No usa outcomes, PnL, entradas,
stops, OTE, optimización ni información futura. Cada snapshot usa únicamente
barras con close_time <= t.

Estados congelados (WyckoffPhaseState): PRO_TREND, COUNTERTREND, TRANSITION,
NEUTRAL.

NO modifica engine/. Envuelve engine/Wyckoff/build_wyckoff_snapshot (que ya
recorta por time <= decision_time). Para acotar el costo de factibilidad se
limita el prefijo a las últimas `window` barras <= t (la fase Wyckoff es
local; el recorte sigue siendo subconjunto del pasado, cumple close_time <= t).
"""
from __future__ import annotations

import pandas as pd
from engine.Wyckoff.adapter import build_wyckoff_snapshot


def _truncate(frames_full: dict, t, window: int | None = 1500) -> dict:
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    out = {}
    for tf, df in frames_full.items():
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        pref = df.loc[times <= tt]
        if window is not None and len(pref) > window:
            pref = pref.iloc[-window:]
        out[tf] = pref.copy().reset_index(drop=True)
    return out


def wyckoff_state_at(
    frames_full: dict,
    nav,
    t,
    *,
    window: int | None = 1500,
    authority_tf: str = "H1",
    layers: tuple[str, ...] = ("H1", "H4", "D1"),
    ict_direction: int | None = None,
):
    """Devuelve WyckoffPhaseState (str) en el instante t, solo pasado.

    `nav` es un MTFNavigator construido sobre frames_full (para el Context State
    ICT / direction_hint en t). Si ict_direction es None, se deriva del
    constraints.direction_hint del MarketState en t.
    """
    st = nav.navigate(t, exec_tf=authority_tf)
    trunc = _truncate(frames_full, t, window=window)
    snap = build_wyckoff_snapshot(
        trunc,
        t,
        context_state=st,
        ict_direction=ict_direction,
        authority_tf=authority_tf,
        layers=layers,
    )
    return snap


__all__ = ["wyckoff_state_at"]
