"""ict_backtest/plan_attach.py — Brecha A1: loop driver nivel 2 (modo OBSERVE).

Por cada senal de generate_sequence_signals, calcula el AlignmentReport multi-TF
(D1/H4/H1/M15/M5/M1) usando objetos/estructuras cerradas en sig.time y lo ADJUNTA
a la senal. NO filtra: el bot opera IGUAL; el reporte solo califica (Brecha D).

Funcion PURA: recibe la senal + dict {tf: [MarketObject]} (ya construido por
build_objects) + swing HTF para dealing range. Reusa emit_* (plan_emitters),
classify_zone (dealing_range), build_confirm_from_tf
(plan_driver), score_plan (plan_driver).

El backtest real (run_backtest.py) lo llamara solo con flag --attach-plan.
"""

from __future__ import annotations

from engine.dealing_range_eq import classify_zone, zone_ok_for_direction
from engine.market_object import MarketObject, ObjectType, Role
from engine.plan_driver import (
    build_confirm_from_tf,
    score_plan,
)
from engine.plan_emitters import (
    emit_d1,
    emit_h4,
    emit_h1,
    emit_m15,
    emit_m5,
    emit_m1,
)
# _objs_before vive en plan_fsm (sin ciclo de import) y se reexporta aquí
# para mantener la API pública usada por scripts/tests.
from engine.plan_fsm import _objs_before  # noqa: F401

_TF_ORDER = ("D1", "H4", "H1", "M15", "M5", "M1")


def attach_alignment(
    signal: dict,
    objs_by_tf: dict[str, list[MarketObject]],
    swing: tuple[float, float] | None = None,
) -> dict:
    """Adjunta AlignmentReport a la senal. Devuelve la senal con signal['alignment'].

    - emit_* deciden veredicto por capa (closed-only via _objs_before).
    - classify_zone marca zona premium/discount del POI M15 (Brecha C).
    - build_confirm_from_tf confirma M5/M1 desde su market_structure.
    - score_plan suma (bonus M5/M1/ancla/zona), NO filtra.
    """
    direction = signal.get("direction", 0)
    # t para anti-look-ahead DEBE ser el timestamp (bar_time de los objetos
    # es timestamp). Priorizamos 'time'; 'bar_index' solo como fallback si no
    # hay time (caso test aislado). Usar bar_index como t rompe la comparacion
    # cross-TF en _objs_before (pd.to_datetime(int) != timestamp).
    t = signal.get("time")
    if t is None:
        t = signal.get("bar_index")
    # padre = objetos HTF (D1/H4/H1) ya cerrados en t (derivado de objs_by_tf)
    parent_objs = {tf: _objs_before(objs_by_tf, tf, t) for tf in ("D1", "H4", "H1")}

    d1_objs = _objs_before(objs_by_tf, "D1", t)
    h4_objs = _objs_before(objs_by_tf, "H4", t)
    h1_objs = _objs_before(objs_by_tf, "H1", t)
    m15_objs = _objs_before(objs_by_tf, "M15", t)

    # ancla narrativa (Brecha B) sobre los FVG/OB M15.
    # El backtest NO tiene logica propia de POI: el ancla real la da el
    # motor (engine.poi_anchor) via anchored_pd_zones en el context stack.
    # Aqui solo marcamos si hay objetos LTF candidatos (sin ancla propia).
    anchored_m15 = m15_objs
    m15_anchored = any(
        o.type in (ObjectType.FVG, ObjectType.ORDER_BLOCK) for o in m15_objs
    )

    # zona premium/discount (Brecha C) del primer POI M15 anclado/valido
    zone_ok = _zone_ok_for_m15(anchored_m15, swing)

    m15_signal = signal  # emit_m15 espera la senal del LTF
    m5_confirm = _confirm_objs(objs_by_tf, "M5", t, direction)
    m1_trigger = _confirm_objs(objs_by_tf, "M1", t, direction)

    rep = score_plan(
        signal,
        d1_objs=d1_objs, h4_objs=h4_objs, h1_objs=h1_objs,
        m15_signal=m15_signal, m5_confirm=m5_confirm, m1_trigger=m1_trigger,
        m15_anchored=m15_anchored,
    )
    # bonifica zona correcta (Brecha C) como +0.5 extra si hay contexto base
    base_ok = rep.d1 and rep.h4 and rep.h1
    if zone_ok and base_ok:
        rep.score += 0.5

    out = dict(signal)
    out["alignment"] = rep.as_dict()
    return out



def _zone_ok_for_m15(m15_objs, swing) -> bool:
    if not swing:
        return False
    for o in m15_objs:
        if o.type in (ObjectType.FVG, ObjectType.ORDER_BLOCK) and o.zone_high:
            cls = classify_zone(o.zone_high, o.zone_low, swing[0], swing[1])
            return zone_ok_for_direction(cls, o.direction)
    return False


def _confirm_objs(objs_by_tf, tf, t, direction) -> dict:
    objs = _objs_before(objs_by_tf, tf, t)
    if not objs:
        return {"direction": direction, "confirmed": False}
    # usa el ultimo objeto del TF como estado de confirmacion
    last = objs[-1]
    confirmed = last.type in (ObjectType.BOS, ObjectType.CHOCH) and last.direction == direction
    return {"direction": direction, "confirmed": bool(confirmed)}
