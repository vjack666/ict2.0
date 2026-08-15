"""E1 — Trade Management: funciones PURAS de gestion post-entry.

Modulo NUEVO y aislado (no edita canonical/engine/sequence/poi_filter ni datos).
Todas las funciones devuelven SOLO calculo; no mutan estado global.

Tipos ICTSignal/ICTTrade viven en ict_backtest.engine; aqui trabajamos con
primitivos (entry/sl/tp/direction/current_price) para maxima pureza y testeo.

Convencion direccion: +1 long, -1 short (igual que ICTSignal.direction).
"""
from __future__ import annotations

import pandas as pd

def _check_direction(direction: int) -> None:
    if direction not in (1, -1):
        raise ValueError(f"direction invalida: {direction!r} (use +1 long | -1 short)")


def to_breakeven(
    entry: float,
    sl: float,
    direction: int,
    current_price: float,
    be_trigger_r: float = 1.0,
) -> float | None:
    """Mueve SL a Break-Even (=entry) si el precio avanzo >= be_trigger_r * risk.

    risk = |entry - sl|. Long: avance = current - entry; Short: entry - current.
    Devuelve el nuevo SL (=entry) si se alcanzo el trigger; si no, None (no mover).
    Sin estructura a favor (risk<=0) => None (dejar SL original).
    """
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    advance = (current_price - entry) if direction == 1 else (entry - current_price)
    if advance >= be_trigger_r * risk:
        return float(entry)
    return None


def partial_exit(
    entry: float,
    tp1: float,
    direction: int,
    current_price: float,
    pct: float = 0.5,
) -> bool:
    """True si el precio toco tp1 (liquidez internal) y corresponde cerrar pct.

    Long: current >= tp1. Short: current <= tp1.
    pct debe estar en (0, 1]. No calcula el cierre; solo señala si corresponde.
    """
    _check_direction(direction)
    if not (0.0 < pct <= 1.0):
        raise ValueError(f"pct fuera de rango (0,1]: {pct!r}")
    if direction == 1:
        return current_price >= tp1
    return current_price <= tp1


def trailing_stop(
    entry: float,
    sl: float,
    direction: int,
    current_price: float,
    step_r: float = 1.0,
) -> float:
    """SL deslizante que solo mejora (sube en long / baja en short), nunca empeora.

    risk = |entry - sl|. Cada step_r de favor arrastra el SL step_r*risk hacia el
    precio. Devuelve max(sl, candidato) en long y min(sl, candidato) en short.
    Si no hay avance suficiente o risk<=0, devuelve el SL original.
    """
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        return float(sl)
    step = step_r * risk
    advance = (current_price - entry) if direction == 1 else (entry - current_price)
    steps = int(advance // step)  # nro de steps completos de favor
    if steps <= 0:
        return float(sl)
    if direction == 1:
        candidate = entry + (steps - 1) * step
        return float(max(sl, candidate))
    candidate = entry - (steps - 1) * step
    return float(min(sl, candidate))


def apply_trade_management(
    entry: float,
    sl: float,
    tp: float,
    direction: int,
    df: "pd.DataFrame",
    *,
    partial_pct: float = 0.5,
    tp1_r: float = 1.0,
    trail_step_r: float = 1.0,
    be_buf: float = 0.0,
) -> dict:
    """Simula la gestion post-entry de un trade sobre la serie ``df`` (call-site real).

    Recorre ``df`` (precios POST-entry, en orden cronologico) y aplica, en orden:
      1) Si el precio toca tp1 (= entry +/- tp1_r*risk segun direccion) -> cierra
         `partial_pct` del lote y mueve el SL restante a Break-Even (entry +/- be_buf).
      2) Tras el parcial, aplica trailing stop por steps de `trail_step_r*risk`
         (solo mejora el SL).
      3) Cierre final cuando el precio toca TP, el SL (BE o trailing) o agota df.

    Devuelve dict con:
      - exit_reason: "tp" | "sl" | "be" | "trailing" | "open"
      - exit_price: float (precio de salida del REMANENTE)
      - pnl_r: float (PnL total en R: parcial + remanente, ponderado por pct)
      - partial_done: bool

    Es el CALL-SITE REAL que el backtest usara para gestionar senales de
    evaluate_signals. NO es backtest de PF (no itera senales ni calcula metricas
    agregadas); solo simula UN trade dada su gestion. Funcion pura: no muta df.

    TDD: tests/test_e1_applied_trade_mgmt.py (parcial+TP, BE, SL directo).
    """
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        raise ValueError(f"risk invalido (entry={entry}, sl={sl})")

    tp1 = entry + tp1_r * risk if direction == 1 else entry - tp1_r * risk
    # SL vigente (puede moverse a BE luego del parcial).
    cur_sl = float(sl)
    cur_tp = float(tp)
    partial_done = False
    partial_price = None

    closes = df["close"] if "close" in df.columns else None
    if closes is None:
        # fallback a la ultima columna numerica
        closes = df.select_dtypes("number").iloc[:, -1]
    hi_series = df["high"] if "high" in df.columns else None
    lo_series = df["low"] if "low" in df.columns else None
    _EPS = 1e-10  # tolerancia a deriva de flotantes en touches exactos

    for i, px in enumerate(closes):
        px = float(px)
        hi = float(hi_series.iloc[i]) if hi_series is not None else px
        lo = float(lo_series.iloc[i]) if lo_series is not None else px

        # 1) Disparo de parcial + BE al TOCAR tp1 (high/low, no solo close).
        if not partial_done and partial_exit(entry, tp1, direction, hi, pct=partial_pct):
            partial_done = True
            partial_price = tp1  # ejecuta al nivel tocado
            new_be = to_breakeven(entry, sl, direction, px, be_trigger_r=0.0)
            if new_be is not None:
                if direction == 1:
                    cur_sl = max(cur_sl, new_be + be_buf)
                else:
                    cur_sl = min(cur_sl, new_be - be_buf)
            continue  # el parcial ocurre en esta vela; el remanente sigue.

        # 2) Trailing del SL tras el parcial.
        if partial_done:
            trail = trailing_stop(entry, cur_sl, direction, px, step_r=trail_step_r)
            if direction == 1:
                cur_sl = max(cur_sl, trail)
            else:
                cur_sl = min(cur_sl, trail)

        # 3) Chequeo de salida del remanente (touch por high/low).
        if direction == 1:
            if hi >= cur_tp - _EPS:
                return _exit_dict("tp", cur_tp, entry, sl, risk, partial_done, partial_price, partial_pct)
            if lo <= cur_sl + _EPS:
                reason = "be" if partial_done and abs(cur_sl - entry) < 1e-12 else "sl"
                return _exit_dict(reason, cur_sl, entry, sl, risk, partial_done, partial_price, partial_pct)
        else:
            if lo <= cur_tp + _EPS:
                return _exit_dict("tp", cur_tp, entry, sl, risk, partial_done, partial_price, partial_pct)
            if hi >= cur_sl - _EPS:
                reason = "be" if partial_done and abs(cur_sl - entry) < 1e-12 else "sl"
                return _exit_dict(reason, cur_sl, entry, sl, risk, partial_done, partial_price, partial_pct)

    # Agoto el df sin tocar TP ni SL -> queda "open" en el ultimo close.
    last = float(closes.iloc[-1])
    return _exit_dict("open", last, entry, sl, risk, partial_done, partial_price, partial_pct)


def _exit_dict(reason, exit_price, entry, sl, risk, partial_done, partial_price, partial_pct):
    """Calcula pnl_r ponderado (parcial + remanente) y arma el dict de salida."""
    if partial_done and partial_price is not None:
        # Parcial: pct del lote en partial_price; remanente (1-pct) en exit_price.
        p_partial = (partial_price - entry) / risk if risk > 0 else 0.0
        p_remain = (exit_price - entry) / risk if risk > 0 else 0.0
        pnl_r = partial_pct * p_partial + (1.0 - partial_pct) * p_remain
    else:
        pnl_r = (exit_price - entry) / risk if risk > 0 else 0.0
    return {
        "exit_reason": reason,
        "exit_price": float(exit_price),
        "pnl_r": float(pnl_r),
        "partial_done": bool(partial_done),
        "risk": float(risk),
    }
