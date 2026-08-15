"""engine/order_block.py — Order Block anclado a la narrativa HTF (Deuda 2).

CAPA POI del motor ICT: el OB es el punto de interés (POI) que origina el
desplazamiento que rompe estructura (BOS). Sin anclaje al sesgo HTF el OB es
ruido; con anclaje es el POI operable.

Reglas (AGENTS.md):
  - `engine/` es la ÚNICA fuente de decisión y NUNCA importa `ict_backtest/`.
  - Sin indicadores técnicos (no ATR, no EMA). Solo geometría: high/low/open/
    close y proporción de cuerpo (body_ratio = cuerpo / rango).
  - API pura, sin estado mutable global.

Contrato:
  ENT: velas cerradas del TF de ejecución + `HtfBias` (engine.bias.narrative).
  SAL: frame anotado con ob_bullish/ob_bearish/ob_top/ob_bottom/ob_status y la
       columna nueva `ob_anchored_htf`.
  PRE: sin look-ahead más allá de la vela de follow-through (canon del OB:
       el OB solo existe cuando la siguiente vela lo confirma).
  POST: `ob_anchored_htf` es el filtro POI que consume el motor (htf_poi_fn).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"

# Umbral de cuerpo dominante para considerar la vela "de impulso" (geometría pura).
_STRONG_BODY_RATIO = 0.7


def detect_order_blocks(frame: pd.DataFrame) -> pd.DataFrame:
    """Detecta Order Blocks por geometría (reimplementación limpia en engine/).

    OB alcista: última vela BAJISTA de cuerpo dominante cuyo cierre siguiente
    supera su máximo (desplazamiento al alza). OB bajista: espejo.
    """
    data = frame.copy().reset_index(drop=True)

    body = (data["close"] - data["open"]).abs()
    rng = (data["high"] - data["low"]).astype(float)
    # Rango 0 (vela plana) -> ratio 0, no es impulso.
    body_ratio = np.where(rng > 0, body / rng.replace(0.0, np.nan), 0.0)
    body_ratio = pd.Series(body_ratio, index=data.index).fillna(0.0)

    bearish_candle = data["close"] < data["open"]
    bullish_candle = data["close"] > data["open"]
    strong = body_ratio > _STRONG_BODY_RATIO

    # Follow-through: la vela siguiente cierra fuera del rango del OB.
    bull_follow = data["close"].shift(-1) > data["high"]
    bear_follow = data["close"].shift(-1) < data["low"]

    data["ob_bullish"] = (bearish_candle & strong & bull_follow).fillna(False)
    data["ob_bearish"] = (bullish_candle & strong & bear_follow).fillna(False)

    is_ob = data["ob_bullish"] | data["ob_bearish"]
    data["ob_top"] = np.where(is_ob, data["high"], np.nan)
    data["ob_bottom"] = np.where(is_ob, data["low"], np.nan)

    data["ob_status"] = _track_ob_validity(data)
    return data


def _track_ob_validity(data: pd.DataFrame) -> pd.Series:
    """Estado del OB vigente: 'active' hasta que el precio lo invalida por cierre."""
    n = len(data)
    status = pd.Series(["none"] * n, index=data.index, dtype=object)
    close = np.asarray(data["close"], dtype=float)
    ob_bull = np.asarray(data["ob_bullish"], dtype=bool)
    ob_bear = np.asarray(data["ob_bearish"], dtype=bool)
    ob_top = np.asarray(data["ob_top"], dtype=float)
    ob_bottom = np.asarray(data["ob_bottom"], dtype=float)

    last_dir = 0
    last_top = float("nan")
    last_bottom = float("nan")
    active = False
    for i in range(n):
        if ob_bull[i] or ob_bear[i]:
            last_dir = 1 if ob_bull[i] else -1
            last_top, last_bottom = ob_top[i], ob_bottom[i]
            active = True
        if active:
            broke = (
                (last_dir == 1 and close[i] < last_bottom)   # OB alcista roto a la baja
                or (last_dir == -1 and close[i] > last_top)  # OB bajista roto al alza
            )
            if broke:
                status.iloc[i], active = "invalidated", False
            else:
                status.iloc[i] = "active"
    return status


def detect_order_blocks_htf(frame: pd.DataFrame, htf_bias) -> pd.DataFrame:
    """Order Blocks anclados a la narrativa HTF (SPEC POI).

    Añade `ob_anchored_htf`: True solo si la dirección del OB coincide con el
    sesgo HTF (alcista+BULLISH, bajista+BEARISH). Sesgo NEUTRAL -> todo False
    (sin narrativa no hay POI operable: filtro de ruido).
    """
    data = detect_order_blocks(frame)
    direction = getattr(htf_bias, "direction", NEUTRAL) if htf_bias is not None else NEUTRAL

    if direction == BULLISH:
        anchored = data["ob_bullish"]
    elif direction == BEARISH:
        anchored = data["ob_bearish"]
    else:
        anchored = pd.Series(False, index=data.index)

    data["ob_anchored_htf"] = anchored.astype(bool)
    return data


def order_block_for_bos(
    frame: pd.DataFrame,
    bos_event: dict,
    htf_bias,
) -> dict | None:
    """OB que ORIGINÓ el BOS: el más cercano ANTERIOR en la dirección del BOS.

    Args:
        frame: velas cerradas (high/low/open/close).
        bos_event: dict del motor `engine.bos` con 'index' (o 'i') y
                   'direction' ∈ {BULLISH, BEARISH} (o bos_dir ±1).
        htf_bias: `HtfBias` para marcar si el OB está anclado a la narrativa.

    Returns:
        dict con ob_top/ob_bottom/ob_index/ob_status/anchored, o None si no hay
        OB previo en la dirección correcta.
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

    data = detect_order_blocks_htf(frame, htf_bias)
    col = "ob_bullish" if direction == BULLISH else "ob_bearish"

    # Buscar hacia atrás desde la vela del BOS (inclusive) el OB más reciente.
    upper = min(idx, len(data) - 1)
    flags = np.asarray(data[col], dtype=bool)[: upper + 1]
    positions = np.flatnonzero(flags)
    if positions.size == 0:
        return None

    ob_i = int(positions[-1])
    row = data.loc[ob_i]
    return {
        "ob_top": float(row["ob_top"]),
        "ob_bottom": float(row["ob_bottom"]),
        "ob_index": ob_i,
        "ob_status": str(data["ob_status"].iloc[upper]),
        "anchored": bool(row["ob_anchored_htf"]),
    }
