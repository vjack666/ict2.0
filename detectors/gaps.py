"""
NWOG / NDOG — port de LuxAlgo ICT Concepts a Python.

NWOG (New Week Opening Gap): caja entre el cierre del viernes y la apertura del lunes.
NDOG (New Day Opening Gap): caja entre el cierre del dia anterior y la apertura del dia.

Devuelve lista de dicts: {kind, x0, x1, top, bot} para pintar como cajas punteadas.
usa 'time' del parquet para los limites.
"""
from __future__ import annotations

import pandas as pd


def detect_nwog_ndog(df: pd.DataFrame, max_nwog: int = 3, max_ndog: int = 1) -> list[dict]:
    out = []
    t = df["time"]
    if "dayofweek" not in df.columns:
        dow = pd.to_datetime(t).dt.dayofweek
    else:
        dow = df["dayofweek"]

    # NDOG: cambio de dia
    prev_close = df["close"].shift(1)
    day_change = dow != dow.shift(1)
    for i in df.index[day_change.fillna(False)]:
        if i == df.index[0]:
            continue
        op = df.loc[i, "open"]
        cp = prev_close.loc[i]
        out.append({
            "kind": "NDOG",
            "x0": t.loc[i],
            "x1": t.loc[i],
            "top": max(op, cp),
            "bot": min(op, cp),
        })

    # NWOG: viernes -> lunes
    fri_mask = dow == 4  # Friday
    for i in df.index[fri_mask]:
        fri_close = df.loc[i, "close"]
        # buscar lunes posterior
        mon = df[(dow == 0) & (t > t.loc[i])]
        if len(mon) == 0:
            continue
        j = mon.index[0]
        mon_open = df.loc[j, "open"]
        out.append({
            "kind": "NWOG",
            "x0": t.loc[i],
            "x1": t.loc[j],
            "top": max(fri_close, mon_open),
            "bot": min(fri_close, mon_open),
        })

    # limitar visibles (mas recientes)
    nwog = [x for x in out if x["kind"] == "NWOG"][-max_nwog:]
    ndog = [x for x in out if x["kind"] == "NDOG"][-max_ndog:]
    return nwog + ndog
