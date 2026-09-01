"""engine/fvg_poi.py — FVG como POI anclado a la narrativa HTF (Deuda 3).

CAPA POI del motor ICT: el Fair Value Gap es la ineficiencia que deja el
desplazamiento; anclado al sesgo HTF se vuelve POI operable, sin anclaje es ruido.

Reglas (AGENTS.md):
  - `engine/` NUNCA importa `ict_backtest/`.
  - Sin indicadores (no ATR/EMA). Solo geometría: high/low/open/close.
  - API pura, sin estado mutable global.

Contrato:
  ENT: velas cerradas del TF de ejecución + `HtfBias` (engine.bias.narrative).
  SAL: frame anotado fvg_bullish/fvg_bearish/fvg_top/fvg_bottom/fvg_mid/
       fvg_size/fvg_fill_status + `fvg_anchored_htf`.
  PRE: FVG de 3 velas (gap entre vela i-2 e i). Sin look-ahead.
  POST: `fvg_anchored_htf` es el filtro POI que consume el motor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def detect_fvg(frame: pd.DataFrame) -> pd.DataFrame:
    """Detecta FVG por geometría pura (reimplementación limpia en engine/).

    FVG alcista en i: low[i] > high[i-2]. FVG bajista: high[i] < low[i-2].
    """
    data = frame.copy().reset_index(drop=True)
    data["fvg_bullish"] = False
    data["fvg_bearish"] = False
    data["fvg_top"] = np.nan
    data["fvg_bottom"] = np.nan
    data["fvg_size"] = 0.0
    data["fvg_mid"] = np.nan
    data["fvg_fill_status"] = "none"

    if len(data) < 3:
        return data

    prev2_high = data["high"].shift(2)
    prev2_low = data["low"].shift(2)

    bull = (data["low"] > prev2_high).fillna(False)
    bear = (data["high"] < prev2_low).fillna(False)
    data["fvg_bullish"] = bull.astype(bool)
    data["fvg_bearish"] = bear.astype(bool)

    # Límites del gap: alcista [high(i-2), low(i)]; bajista [high(i), low(i-2)].
    data["fvg_top"] = np.where(bull, data["low"], np.where(bear, prev2_low, np.nan))
    data["fvg_bottom"] = np.where(bull, prev2_high, np.where(bear, data["high"], np.nan))
    data["fvg_size"] = np.where(
        bull | bear, (data["fvg_top"] - data["fvg_bottom"]).clip(lower=0.0), 0.0
    )
    data["fvg_mid"] = np.where(
        bull | bear, (data["fvg_top"] + data["fvg_bottom"]) / 2.0, np.nan
    )

    data["fvg_fill_status"] = _track_fvg_fill(data)
    return data


def _track_fvg_fill(data: pd.DataFrame) -> pd.Series:
    """Estado de relleno del gap vigente (lista simple: evita issues Arrow 3.x)."""
    n = len(data)
    status: list[str] = ["none"] * n
    low = np.asarray(data["low"], dtype=float)
    high = np.asarray(data["high"], dtype=float)
    bull = np.asarray(data["fvg_bullish"], dtype=bool)
    bear = np.asarray(data["fvg_bearish"], dtype=bool)
    top = np.asarray(data["fvg_top"], dtype=float)
    bottom = np.asarray(data["fvg_bottom"], dtype=float)

    bull_bottom: float | None = None
    bear_top: float | None = None
    bull_unfilled = False
    bear_unfilled = False

    for i in range(n):
        created = False
        if bull[i]:
            bull_bottom = float(bottom[i])
            bull_unfilled = True
            created = True
        if bear[i]:
            bear_top = float(top[i])
            bear_unfilled = True
            created = True

        # Relleno: el precio vuelve a entrar en el gap.
        if bull_unfilled and bull_bottom is not None and low[i] <= bull_bottom:
            bull_unfilled = False
        if bear_unfilled and bear_top is not None and high[i] >= bear_top:
            bear_unfilled = False

        if bull_unfilled:
            status[i] = "bullish_unfilled"
        elif bear_unfilled:
            status[i] = "bearish_unfilled"
        elif created:
            status[i] = "just_created"
    return pd.Series(status, index=data.index, name="fvg_fill_status", dtype=object)


def detect_fvg_htf(frame: pd.DataFrame, htf_bias) -> pd.DataFrame:
    """FVG anclados a la narrativa HTF (SPEC POI).

    Añade `fvg_anchored_htf`: True solo si la dirección del FVG coincide con el
    sesgo HTF. Sesgo NEUTRAL -> todo False (sin narrativa no hay POI operable).
    """
    data = detect_fvg(frame)
    direction = getattr(htf_bias, "direction", NEUTRAL) if htf_bias is not None else NEUTRAL

    if direction == BULLISH:
        anchored = data["fvg_bullish"]
    elif direction == BEARISH:
        anchored = data["fvg_bearish"]
    else:
        anchored = pd.Series(False, index=data.index)

    data["fvg_anchored_htf"] = anchored.astype(bool)
    return data


def fvg_for_bos(frame: pd.DataFrame, bos_event: dict, htf_bias) -> dict | None:
    """FVG que ORIGINÓ el BOS: el más cercano ANTERIOR en la dirección del BOS.

    Espejo de `order_block_for_bos`. Devuelve None si no hay FVG previo válido.
    """
    if bos_event is None:
        return None

    idx = bos_event.get("index", bos_event.get("i"))
    if idx is None:
        return None
    idx = int(idx)

    direction = bos_event.get("direction")
    if direction is None:
        raw = bos_event.get("bos_dir", 0)
        direction = BULLISH if raw == 1 else BEARISH if raw == -1 else None
    if direction not in (BULLISH, BEARISH):
        return None

    data = detect_fvg_htf(frame, htf_bias)
    col = "fvg_bullish" if direction == BULLISH else "fvg_bearish"

    upper = min(idx, len(data) - 1)
    if upper < 0:
        return None
    flags = np.asarray(data[col], dtype=bool)[: upper + 1]
    positions = np.flatnonzero(flags)
    if positions.size == 0:
        return None

    fvg_i = int(positions[-1])
    row = data.loc[fvg_i]
    return {
        "fvg_top": float(row["fvg_top"]),
        "fvg_bottom": float(row["fvg_bottom"]),
        "fvg_index": fvg_i,
        "fvg_status": str(data["fvg_fill_status"].iloc[upper]),
        "anchored": bool(row["fvg_anchored_htf"]),
    }
