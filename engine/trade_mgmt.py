"""engine/trade_mgmt.py — E1 Trade Management (PERMANENTE).

Rescatado de ict_backtest/trade_mgmt.py (funciones PURAS, no mutan estado).
Unica fuente del motor; el backtest LO CONSUME. Ley: engine/ NUNCA importa ict_backtest/.

Geometria pura (sin indicadores): BE en entry, parcial en tp1 (liquidez internal),
trailing por pasos de risk. El volumen es confirmacion OPCIONAL (no indicador):
tick volume en el toque de tp1/BE para saber si la liquidez se agoto de verdad.
"""

from __future__ import annotations

import pandas as pd

from engine._volume import volume_confirm


def _check_direction(direction: int) -> None:
    if direction not in (1, -1):
        raise ValueError(f"direction invalida: {direction!r} (use +1 long | -1 short)")


def to_breakeven(entry, sl, direction, current_price, be_trigger_r: float = 1.0):
    """Mueve SL a Break-Even (=entry) si el precio avanzo >= be_trigger_r * risk."""
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    advance = (current_price - entry) if direction == 1 else (entry - current_price)
    if advance >= be_trigger_r * risk:
        return float(entry)
    return None


def partial_exit(entry, tp1, direction, current_price, pct: float = 0.5) -> bool:
    """True si el precio toco tp1 (liquidez internal) y corresponde cerrar pct."""
    _check_direction(direction)
    if not (0.0 < pct <= 1.0):
        raise ValueError(f"pct fuera de rango (0,1]: {pct!r}")
    if direction == 1:
        return current_price >= tp1
    return current_price <= tp1


def trailing_stop(entry, sl, direction, current_price, step_r: float = 1.0):
    """SL deslizante que solo mejora (sube en long / baja en short), nunca empeora."""
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        return float(sl)
    step = step_r * risk
    advance = (current_price - entry) if direction == 1 else (entry - current_price)
    steps = int(advance // step)
    if steps <= 0:
        return float(sl)
    if direction == 1:
        candidate = entry + (steps - 1) * step
        return float(max(sl, candidate))
    candidate = entry - (steps - 1) * step
    return float(min(sl, candidate))


def _exit_dict(reason, exit_price, entry, sl, risk, partial_done, partial_price, partial_pct,
               touch_volume_ratio=None):
    if partial_done and partial_price is not None:
        p_partial = (partial_price - entry) / risk if risk > 0 else 0.0
        p_remain = (exit_price - entry) / risk if risk > 0 else 0.0
        pnl_r = partial_pct * p_partial + (1.0 - partial_pct) * p_remain
    else:
        pnl_r = (exit_price - entry) / risk if risk > 0 else 0.0
    return {"exit_reason": reason, "exit_price": float(exit_price),
            "pnl_r": float(pnl_r), "partial_done": bool(partial_done), "risk": float(risk),
            # MDS_VOLUMEN: confirmacion OPCIONAL en el toque de tp1/BE.
            # float o None. NUNCA gate: no decide salida ni parcial.
            "touch_volume_ratio": (
                None if touch_volume_ratio is None else float(touch_volume_ratio)
            )}


def apply_trade_management(
    entry, sl, tp, direction, df: "pd.DataFrame", *,
    partial_pct: float = 0.5, tp1_r: float = 1.0, trail_step_r: float = 1.0, be_buf: float = 0.0,
    volume_window: int | None = None,
) -> dict:
    """Simula la gestion post-entry de un trade sobre la serie df (call-site real).

    Recorre df (precios POST-entry) y aplica: (1) al tocar tp1 cierra partial_pct y
    mueve SL a BE; (2) trailing del SL tras el parcial; (3) cierre en TP/SL/BE/trailing.
    Devuelve exit_reason, exit_price, pnl_r (parcial+remanente), partial_done.

    Ademas anota `touch_volume_ratio` (float|None): ratio de volumen de la vela
    del toque de tp1/BE. Es SOLO confirmacion (MDS_VOLUMEN), NUNCA un filtro:
    None si no hay columna 'volume' o si no hubo toque (regresion cero).
    """
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        raise ValueError(f"risk invalido (entry={entry}, sl={sl})")
    tp1 = entry + tp1_r * risk if direction == 1 else entry - tp1_r * risk
    cur_sl = float(sl)
    cur_tp = float(tp)
    partial_done = False
    partial_price = None
    touch_vol = None
    vol_window = 20 if volume_window is None else int(volume_window)
    closes = df["close"] if "close" in df.columns else df.select_dtypes("number").iloc[:, -1]
    hi_series = df["high"] if "high" in df.columns else None
    lo_series = df["low"] if "low" in df.columns else None
    _EPS = 1e-10
    for i, px in enumerate(closes):
        px = float(px)
        hi = float(hi_series.iloc[i]) if hi_series is not None else px
        lo = float(lo_series.iloc[i]) if lo_series is not None else px
        if not partial_done and partial_exit(entry, tp1, direction, hi, pct=partial_pct):
            partial_done = True
            partial_price = tp1
            # Confirmacion (no gate): volumen de la vela que toca tp1/BE.
            touch_vol = volume_confirm(df, i, vol_window)
            new_be = to_breakeven(entry, sl, direction, px, be_trigger_r=0.0)
            if new_be is not None:
                if direction == 1:
                    cur_sl = max(cur_sl, new_be + be_buf)
                else:
                    cur_sl = min(cur_sl, new_be - be_buf)
            continue
        if partial_done:
            trail = trailing_stop(entry, cur_sl, direction, px, step_r=trail_step_r)
            if direction == 1:
                cur_sl = max(cur_sl, trail)
            else:
                cur_sl = min(cur_sl, trail)
        if direction == 1:
            if hi >= cur_tp - _EPS:
                return _exit_dict("tp", cur_tp, entry, sl, risk, partial_done, partial_price, partial_pct, touch_vol)
            if lo <= cur_sl + _EPS:
                reason = "be" if partial_done and abs(cur_sl - entry) < 1e-12 else "sl"
                return _exit_dict(reason, cur_sl, entry, sl, risk, partial_done, partial_price, partial_pct, touch_vol)
        else:
            if lo <= cur_tp + _EPS:
                return _exit_dict("tp", cur_tp, entry, sl, risk, partial_done, partial_price, partial_pct, touch_vol)
            if hi >= cur_sl - _EPS:
                reason = "be" if partial_done and abs(cur_sl - entry) < 1e-12 else "sl"
                return _exit_dict(reason, cur_sl, entry, sl, risk, partial_done, partial_price, partial_pct, touch_vol)
    last = float(closes.iloc[-1])
    return _exit_dict("open", last, entry, sl, risk, partial_done, partial_price, partial_pct, touch_vol)
