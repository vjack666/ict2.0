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
    mode: str = "sustained", # "sustained" (tesis) | "strict" (sensibilidad)
    sustain_bars: int = 3,   # cierres consecutivos en contra para invalidar
) -> str:
    """Devuelve 'active' o 'invalidated' para un BOS dado.

    mode="strict" (criterio original): cualquier cierre posterior que cruce el
        nivel invalida. Muy sensible a ruido de 1 vela en M5 (-> 99% invalidated).
    mode="sustained" (default, tesis SPEC §8 / ICT_RULEBOOK): el BOS vive hasta
        que la ESTRUCTURA se niega de verdad — N cierres CONSECUTIVOS en contra
        (reclaim sostenido), no un wick/ruido de 1 vela. Un cruce aislado que
        vuelve no mata el BOS.

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
        wrong = tail["close"] < price
    else:
        wrong = tail["close"] > price

    if mode == "strict":
        # cualquier cruce posterior invalida (original, sensible a ruido M5)
        return "invalidated" if wrong.any() else "active"

    # mode == "sustained": solo invalida tras N cierres CONSECUTIVOS en contra.
    # Se acota el horizonte a MAX_TAIL velas (un reclaim sostenido en M5 ocurre
    # pronto; si no se invalida en ese horizonte, el BOS sigue vigente como
    # estructura). Evita O(n_bos * n_total) y hace el calculo trivial.
    MAX_TAIL = 200
    w = wrong.to_numpy()[:MAX_TAIL]
    run = 0
    for v in w:
        run = run + 1 if v else 0
        if run >= sustain_bars:
            return "invalidated"
    return "active"


def apply_validation(
    df: pd.DataFrame,
    events: list,
    mode: str = "sustained",
    sustain_bars: int = 3,
) -> list:
    """Valida una lista de ToolEvent BOS in-place (setea status).

    `events` son ToolEvent con break_bar, price, signal (BOS_UP/BOS_DOWN).
    Devuelve la misma lista con status actualizado.
    """
    for ev in events:
        if not ev.signal.startswith("BOS_"):
            continue
        direction = 1 if ev.signal == "BOS_UP" else -1
        ev.status = validate_bos_status(
            df, ev.break_bar, ev.price, direction,
            mode=mode, sustain_bars=sustain_bars,
        )
    return events
