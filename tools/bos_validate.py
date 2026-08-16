"""Validador de BOS (copia aislada de engine/invalidation.py + engine/bos/structure.py).

COPIA PURA para tools/ — NO importa engine/. Valida el ciclo de vida del BOS
por GEOMETRIA SIMPLE, sin indicadores ni HTF:

  - ACTIVE: el precio rompió el nivel (break_bar) y NO lo ha cruzado en
    sentido contrario despues.
  - INVALIDATED: despues de break_bar, el precio cierra de vuelta CRUZANDO
    el nivel roto en contra de la direccion del BOS.

Esto es una version SIMPLIFICADA del validador de engine/ (que usa
confirm_bars consecutivos + quality_score + volumen + reglas HTF congeladas).
La copia se hace a proposito para respetar el aislamiento de tools/ (Task 2):
tools/ no debe absorber engine.invalidation ni engine.bos.structure.

El criterio de invalidacion es el mismo principio de Ley 4 (geometria pura):
un BOS vive hasta que el cierre cruza de vuelta el nivel roto. Sin look-ahead:
solo se mira velas >= break_bar.
"""
from __future__ import annotations

import pandas as pd


def validate_bos_status(
    df: pd.DataFrame,
    break_bar: int,
    price: float,
    direction: int,          # 1 = BOS_UP (rompio swing high), -1 = BOS_DOWN
    confirm_bars: int = 1,   # cuantos cierres consecutivos deben romper al nacer
) -> str:
    """Devuelve 'active' o 'invalidated' para un BOS dado.

    direction=1 (BOS_UP): nivel roto es un swing high; invalidado si un cierre
        posterior cae DEBAJO del nivel.
    direction=-1 (BOS_DOWN): nivel roto es un swing low; invalidado si un cierre
        posterior sube ENCIMA del nivel.

    Sin look-ahead: solo recorre velas desde break_bar en adelante.
    """
    if break_bar < 0 or break_bar >= len(df):
        return "invalidated"
    # confirmacion al nacer: los primeros confirm_bars cierres deben mantener
    # la ruptura (filtra fakeouts de 1 vela).
    seg = df.iloc[break_bar: break_bar + confirm_bars]
    if len(seg) < confirm_bars:
        return "invalidated"
    if direction == 1:
        if not (seg["close"] > price).all():
            return "invalidated"
    else:
        if not (seg["close"] < price).all():
            return "invalidated"

    # despues de la confirmacion, buscar cruce en contra
    tail = df.iloc[break_bar + confirm_bars:]
    if direction == 1:
        crossed = (tail["close"] < price).any()
    else:
        crossed = (tail["close"] > price).any()
    return "invalidated" if crossed else "active"


def apply_validation(
    df: pd.DataFrame,
    events: list,
) -> list:
    """Valida una lista de ToolEvent BOS in-place (setea status).

    `events` son ToolEvent con break_bar, price, signal (BOS_UP/BOS_DOWN).
    Devuelve la misma lista con status actualizado.
    """
    for ev in events:
        if not ev.signal.startswith("BOS_"):
            continue
        direction = 1 if ev.signal == "BOS_UP" else -1
        ev.status = validate_bos_status(df, ev.break_bar, ev.price, direction)
    return events
