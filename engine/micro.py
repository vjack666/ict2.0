"""Microestructura M1 (engine/micro.py).

Tesis (docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md §5): M1 es MICROESTRUCTURA
-- liquidez fina, sweeps y fakeouts de corto plazo. NUNCA redefine el bias:
este modulo solo describe eventos geometricos de M1, no emite direccion HTF.

Ley del motor:
  * Geometria pura: solo OHLC + swings. SIN indicadores (EMA/RSI/ATR).
  * NUNCA importa ict_backtest/.
  * Anti look-ahead estricto: toda decision en la vela i usa unicamente
    velas con posicion <= i.
  * Reusa engine.bias.narrative._swing_points; no duplica logica de swings.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from engine.bias.narrative import _swing_points

__all__ = [
    "normalize_parent_swings",
    "detect_m1_liquidity_sweeps",
    "is_m1_fakeout",
    "m1_micro_momentum",
    "m1_swing_levels",
]


# ---------------------------------------------------------------------------
# Utilidades internas (geometria pura)
# ---------------------------------------------------------------------------


def _ohlc(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.asarray(df["open"], dtype=float),
        np.asarray(df["high"], dtype=float),
        np.asarray(df["low"], dtype=float),
        np.asarray(df["close"], dtype=float),
    )


def _time_at(df: pd.DataFrame, i: int) -> Any:
    if "time" in df.columns:
        return df["time"].iloc[i]
    return df.index[i]


def normalize_parent_swings(parent_swings: Any) -> list[dict[str, Any]]:
    """Normaliza swings padre (M5/M15) a [{'price': float, 'side': 'high'|'low', 'tf': str}].

    Formatos aceptados:
      * lista de dicts con 'price'/'level'/'value' y 'side'/'kind'/'type'.
      * lista de tuplas (side, price) o (price, side).
      * dict {'highs': [...], 'lows': [...]}.
    Cualquier entrada no interpretable se ignora (funcion pura y tolerante).
    """
    out: list[dict[str, Any]] = []
    if parent_swings is None:
        return out

    def _add(side: Any, price: Any, tf: Any = None) -> None:
        try:
            p = float(price)
        except (TypeError, ValueError):
            return
        if not np.isfinite(p):
            return
        s = str(side).lower()
        if s.startswith("h") or s in ("buyside", "bsl", "up", "+1", "1"):
            side_n = "high"
        elif s.startswith("l") or s in ("sellside", "ssl", "down", "-1"):
            side_n = "low"
        else:
            return
        out.append({"price": p, "side": side_n, "tf": tf})

    if isinstance(parent_swings, dict):
        for key, side in (("highs", "high"), ("lows", "low")):
            for v in parent_swings.get(key, []) or []:
                _add(side, v, parent_swings.get("tf"))
        return out

    if isinstance(parent_swings, (str, bytes)) or not isinstance(parent_swings, Iterable):
        return out

    for item in parent_swings:
        if isinstance(item, dict):
            price = item.get("price", item.get("level", item.get("value")))
            side = item.get("side", item.get("kind", item.get("type")))
            _add(side, price, item.get("tf"))
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)) and len(item) >= 2:
            a, b = item[0], item[1]
            if isinstance(a, str):
                _add(a, b, item[2] if len(item) > 2 else None)
            else:
                _add(b, a, item[2] if len(item) > 2 else None)
    return out


def m1_swing_levels(m1_df: pd.DataFrame, upto: int | None = None) -> dict[str, float | None]:
    """Ultimo swing high/low CONFIRMADO en M1 usando solo velas <= upto."""
    n = len(m1_df)
    if n == 0:
        return {"swing_high": None, "swing_low": None}
    end = n - 1 if upto is None else min(int(upto), n - 1)
    if end < 0:
        return {"swing_high": None, "swing_low": None}
    closed = m1_df.iloc[: end + 1]
    sh, sl = _swing_points(closed, lookback=2)
    sh_v = sh.dropna()
    sl_v = sl.dropna()
    return {
        "swing_high": float(sh_v.iloc[-1]) if len(sh_v) else None,
        "swing_low": float(sl_v.iloc[-1]) if len(sl_v) else None,
    }


# ---------------------------------------------------------------------------
# 1) Liquidez fina: sweeps de M1 contra swings de M5/M15
# ---------------------------------------------------------------------------


def detect_m1_liquidity_sweeps(
    m1_df: pd.DataFrame,
    parent_swings: Any,
    *,
    tolerance: float = 0.0,
    max_index: int | None = None,
) -> list[dict[str, Any]]:
    """Detecta sweeps de liquidez fina de M1 contra niveles de swing M5/M15.

    Un SWEEP es geometria pura: la vela M1 PERFORA el nivel padre con su mecha
    y CIERRA de vuelta al lado original (rechazo). No usa indicadores.

      * buyside sweep : high[i] > level + tol  y  close[i] < level  -> 'bearish'
      * sellside sweep: low[i]  < level - tol  y  close[i] > level  -> 'bullish'

    Anti look-ahead: cada evento en la vela i depende solo de la vela i
    (y de niveles padre que el llamador debe haber calculado con datos <= i).

    Returns:
        Lista de dicts ordenada por indice:
        {index, time, side, level, direction, penetration, close, tf}
        side='buyside'|'sellside'; direction=-1 (bajista) | +1 (alcista).
    """
    levels = normalize_parent_swings(parent_swings)
    if len(m1_df) == 0 or not levels:
        return []

    _o, high, low, close = _ohlc(m1_df)
    n = len(m1_df)
    end = n - 1 if max_index is None else min(int(max_index), n - 1)
    tol = float(tolerance)

    events: list[dict[str, Any]] = []
    for i in range(0, end + 1):
        for lv in levels:
            level = lv["price"]
            if lv["side"] == "high":
                if high[i] > level + tol and close[i] < level:
                    events.append(
                        {
                            "index": i,
                            "time": _time_at(m1_df, i),
                            "side": "buyside",
                            "level": level,
                            "direction": -1,
                            "penetration": float(high[i] - level),
                            "close": float(close[i]),
                            "tf": lv.get("tf"),
                        }
                    )
            else:
                if low[i] < level - tol and close[i] > level:
                    events.append(
                        {
                            "index": i,
                            "time": _time_at(m1_df, i),
                            "side": "sellside",
                            "level": level,
                            "direction": 1,
                            "penetration": float(level - low[i]),
                            "close": float(close[i]),
                            "tf": lv.get("tf"),
                        }
                    )
    events.sort(key=lambda e: (e["index"], e["side"], e["level"]))
    return events


# ---------------------------------------------------------------------------
# 2) Fakeout: breakout de estructura M1 que no se sostiene
# ---------------------------------------------------------------------------


def is_m1_fakeout(m1_df: pd.DataFrame, i: int, lookback: int = 5) -> bool:
    """True si la vela i es un FAKEOUT del rango M1 previo (geometria pura).

    Rango previo = max(high)/min(low) de las `lookback` velas ANTERIORES a i
    (posiciones i-lookback .. i-1). La vela i rompe ese rango con la mecha pero
    CIERRA de vuelta dentro del rango => el breakout no se sostiene.

    Anti look-ahead: nunca mira velas con posicion > i.
    """
    n = len(m1_df)
    if n == 0:
        return False
    i = int(i)
    lookback = int(lookback)
    if i <= 0 or i >= n or lookback < 1 or i - lookback < 0:
        return False

    _o, high, low, close = _ohlc(m1_df)
    win_high = float(np.max(high[i - lookback : i]))
    win_low = float(np.min(low[i - lookback : i]))

    broke_up = high[i] > win_high and close[i] < win_high
    broke_down = low[i] < win_low and close[i] > win_low
    return bool(broke_up or broke_down)


def m1_micro_momentum(m1_df: pd.DataFrame, i: int, window: int = 3) -> int:
    """Momentum fino OPCIONAL, geometria pura: +1 / -1 / 0.

    Cuerpos consecutivos en la misma direccion + cierre progresando en esa
    direccion sobre las ultimas `window` velas (posiciones i-window+1 .. i).
    Sin medias ni osciladores. Anti look-ahead: nunca mira mas alla de i.
    """
    n = len(m1_df)
    i = int(i)
    window = int(window)
    if n == 0 or i < 0 or i >= n or window < 1 or i - window + 1 < 0:
        return 0

    op, _h, _l, close = _ohlc(m1_df)
    sl = slice(i - window + 1, i + 1)
    bodies = close[sl] - op[sl]
    if np.all(bodies > 0) and close[i] > close[i - window + 1]:
        return 1
    if np.all(bodies < 0) and close[i] < close[i - window + 1]:
        return -1
    return 0
