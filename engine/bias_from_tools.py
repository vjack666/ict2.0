"""engine/bias_from_tools.py — Adaptador Task 5b: sesgo del motor USANDO
las herramientas corregidas de tools/ (Fase 1).

PROPOSITO:
  El motor de lectura (engine/plan.py) calcula el sesgo desde un df anotado
  con columnas bos_dir/bos_status/choch_dir/choch_status (via
  engine.bos.detect_market_structure, motor viejo).
  Este adaptador produce ESE MISMO formato de df anotado pero usando las
  herramientas corregidas y certificadas de tools/ (Swing persistente,
  BOS hijo de swing, filtro tesis, CHOCH con fallback de swings).
  Asi la mejora de Fase 1 SIRVE para uso real del motor, no queda aislada.

RESPESTA AISLAMIENTO (Ley Task 2):
  engine/ importa tools/ (permitido: el orquestador consume tools).
  tools/ NO importa engine/ (invariante).

USO:
  from engine.bias_from_tools import annotate_with_tools, bias_from_tools
  df_annot = annotate_with_tools(raw_m5, symbol="EURUSD")
  bias = bias_from_tools(df_annot, t=some_time)   # compatible con _bias_from_frame
  # o integrado en plan.py:
  from engine.bias_from_tools import bias_from_tools
  # usar en vez de _bias_from_frame para frames anotados por tools.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.choch import CHOCHTool
from tools.bos_filter import filter_bos_thesis


def annotate_with_tools(df: pd.DataFrame, symbol: str = "EURUSD",
                        max_idle_bars: int = 0, require_htf_alignment: bool = False,
                        htf_frames: dict | None = None) -> pd.DataFrame:
    """Devuelve df con columnas bos_dir/bos_status/choch_dir/choch_status
    calculadas por las herramientas corregidas de tools/.

    El df resultante es compatible con engine.plan._bias_from_frame.
    """
    out = df.copy().reset_index(drop=True)
    out["bos_dir"] = 0
    out["bos_status"] = "none"
    out["bos_real"] = False
    out["bos_level"] = np.nan
    out["choch_dir"] = 0
    out["choch_status"] = "none"
    out["choch_proj_level"] = np.nan

    sw = SwingTool(lookback=5)
    swe = sw.run(out, symbol=symbol)
    sids = {e.origin_bar: e.id for e in swe}

    bo = BOSTool(lookback=5)
    boe = bo.run(out, symbol=symbol, context={"swing_ids": sids})
    boe = apply_validation(out, boe)
    boe = filter_bos_thesis(out, boe, htf_frames=htf_frames, confirm_bars=2,
                            max_idle_bars=max_idle_bars,
                            require_htf_alignment=require_htf_alignment)
    for e in boe:
        i = e.break_bar if e.break_bar is not None else e.bar_index
        if i is None or i < 0 or i >= len(out):
            continue
        out.loc[i, "bos_dir"] = 1 if e.signal == "BOS_UP" else -1
        # bos_real = paso el filtro tesis (calidad, no solo geometria)
        out.loc[i, "bos_real"] = bool(e.extra.get("thesis_valid", False))
        out.loc[i, "bos_level"] = float(e.price) if e.price is not None else np.nan
        out.loc[i, "bos_status"] = "active" if getattr(e, "status", "") != "invalidated" else "invalidated"

    ch = CHOCHTool()
    che = ch.run(out, symbol=symbol, context={"swings": swe, "boses": boe})
    che = filter_bos_thesis(out, che, htf_frames=htf_frames, confirm_bars=2,
                            max_idle_bars=max_idle_bars,
                            require_htf_alignment=require_htf_alignment)
    for e in che:
        i = e.break_bar if e.break_bar is not None else e.bar_index
        if i is None or i < 0 or i >= len(out):
            continue
        out.loc[i, "choch_dir"] = 1 if e.signal == "CHOCH_UP" else -1
        out.loc[i, "choch_status"] = "active" if getattr(e, "status", "") != "invalidated" else "invalidated"
        if e.price is not None:
            out.loc[i, "choch_proj_level"] = float(e.price)

    return out


def bias_from_tools(df: pd.DataFrame, t: Any) -> str:
    """Sesgo por estructura (igual firma/semantica que engine.plan._bias_from_frame)
    pero sobre df anotado por las herramientas corregidas de tools/.

    CHOCH activo manda sobre BOS activo; sin ninguno => RANGING.
    """
    if df is None or len(df) == 0 or "time" not in df.columns:
        return "RANGING"
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    if pd.isna(tt):
        return "RANGING"
    sub = df.loc[times <= tt]
    if len(sub) == 0:
        return "RANGING"
    has_real = "bos_real" in sub.columns
    last_bos_idx = last_bos_dir = 0
    last_choch_idx = last_choch_dir = 0
    for i in range(len(sub)):
        bd = sub["bos_dir"].iloc[i]
        if bd not in (0, "0", None) and str(sub["bos_status"].iloc[i]) == "active" \
           and (not has_real or bool(sub["bos_real"].iloc[i])):
            last_bos_idx, last_bos_dir = i, int(bd)
        cd = sub["choch_dir"].iloc[i]
        if cd not in (0, "0", None) and str(sub["choch_status"].iloc[i]) == "active":
            # T9.7 (tesis S7.0): CHOCH solo cuenta si el BOS contrario que
            # rompio era REAL (bos_real). Replica la regla del motor viejo
            # para que la mejora de calidad (filtro tesis -> bos_real) se
            # propague al sesgo de forma consistente.
            if has_real:
                opp = -int(cd)
                cand = sub.iloc[:i]
                hit = cand[
                    (cand["bos_dir"] == opp)
                    & (cand["bos_status"] == "active")
                    & (cand["bos_real"].fillna(False).astype(bool))
                ]
                if len(hit) == 0:
                    continue
            last_choch_idx, last_choch_dir = i, int(cd)
    if last_choch_dir != 0:
        return "BULLISH" if last_choch_dir > 0 else "BEARISH"
    if last_bos_dir != 0:
        return "BULLISH" if last_bos_dir > 0 else "BEARISH"
    return "RANGING"
