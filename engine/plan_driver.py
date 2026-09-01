"""ict_backtest/plan_driver.py — Fase 5: score de alineacion multi-TF.

El plan es HERRAMIENTA DE ANALISIS, no gate (decision de Ruben 2026-07-19:
M5/M1 son BONUS, no condicion; el umbral lo fija el mercado con evidencia,
no antes). score_plan MIDE la alineacion de cada senal y la adjunta como
AlignmentReport. NO descarta senales.

Pesos (alineacion, no filtro):
  D1  context ok      +1.0
  H4  bias ok         +1.0
  H1  POI armado      +1.0
  M15 setup completo  +1.0
  M5  confirmacion    +0.5  (bonus)
  M1  trigger fino    +0.5  (bonus)

Score maximo ~5.0. Una senal sin M5/M1 queda en 4.0 y SIGUE siendo
valida para analisis (no se borra). Solo falta contexto base (D1/H4/H1)
o setup (M15) cuando esas capas no aportan -> score bajo, se marca.

Funcion PURA: recibe objetos/senales ya filtrados a barras cerradas <= t
(closed-only anti look-ahead, el loop driver se encarga de eso). No accede
a discos ni a bar_index. No altera el conteo de senales de run_sequence.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.market_object import ObjectType
from engine.plan_emitters import (
    emit_d1,
    emit_h4,
    emit_h1,
    emit_m15,
    emit_m5,
    emit_m1,
    _field,
)
from engine.plan_fsm import PlanFSM, PlanState, PlanVerdict, _objs_before

@dataclass
class AlignmentReport:
    """Desglose de alineacion multi-TF para una senal. score es la suma."""

    score: float
    d1: bool
    h4: bool
    h1: bool
    m15: bool
    m5: bool
    m1: bool
    m15_anchored: bool = False
    po3_complete: bool = False

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "d1": self.d1,
            "h4": self.h4,
            "h1": self.h1,
            "m15": self.m15,
            "m5": self.m5,
            "m1": self.m1,
            "m15_anchored": self.m15_anchored,
            "po3_complete": self.po3_complete,
        }


def _confirm(confirm: dict | None, direction: int) -> bool:
    if not confirm:
        return False
    return bool(confirm.get("confirmed")) and confirm.get("direction") == direction


def build_confirm_from_tf(df, t, direction: int) -> dict:
    """Confirma un TF (M5/M1) desde su market_structure, closed-only.

    Mira barras con time <= t (anti look-ahead). Si hay BOS o CHOCH activo
    en la MISMA direccion que el setup, confirma. Funcion pura.
    """
    if df is None or len(df) == 0:
        return {"direction": direction, "confirmed": False}
    t = pd.to_datetime(t)
    past = df[df["time"] <= t]
    if len(past) == 0:
        return {"direction": direction, "confirmed": False}
    dir_col = past["bos_dir"].iloc[-1] if "bos_dir" in past else 0
    choch_col = past["choch_dir"].iloc[-1] if "choch_dir" in past else 0
    confirmed = (dir_col == direction) or (choch_col == direction)
    return {"direction": direction, "confirmed": bool(confirmed)}


def score_plan(
    signal: dict,
    *,
    d1_objs: list,
    h4_objs: list,
    h1_objs: list,
    m15_signal: dict,
    m5_confirm: dict | None = None,
    m1_trigger: dict | None = None,
    m15_anchored: bool = False,
    po3_complete: bool = False,
) -> AlignmentReport:
    """Mide la alineacion multi-TF de una senal. NO filtra.

    Cada capa suma si su emisor emite el veredicto esperado. M5/M1 son
    bonus (+0.5) solo si confirman en la MISMA direccion que el setup.
    m15_anchored (+0.5, Brecha B) bonifica el POI anclado a narrativa HTF.
    po3_complete (+0.5, Brecha E) bonifica PO3 A/M/D alineado en la direccion.
    """
    direction = signal.get("direction", 0)
    score = 0.0

    d1 = emit_d1(d1_objs)
    d1_ok = d1 is not None and d1.verdict is PlanVerdict.CONTEXT_OK
    if d1_ok:
        score += 1.0

    h4 = emit_h4(h4_objs)
    h4_ok = h4 is not None and h4.verdict is PlanVerdict.CONTEXT_OK
    if h4_ok:
        score += 1.0

    h1 = emit_h1(h1_objs)
    h1_ok = h1 is not None and h1.verdict is PlanVerdict.ZONE_ARMED
    if h1_ok:
        score += 1.0

    m15 = emit_m15([m15_signal])
    m15_ok = m15 is not None and m15.verdict in (
        PlanVerdict.SETUP_LIVE,
        PlanVerdict.STRUCTURE_OK,
    )
    if m15_ok:
        score += 1.0

    base_ok = d1_ok and h4_ok and h1_ok

    m5 = _confirm(m5_confirm, direction)
    if m5 and base_ok:
        # Bonus solo si hay contexto superior (el plan existe para refinar)
        score += 0.5

    m1 = _confirm(m1_trigger, direction)
    if m1 and base_ok:
        score += 0.5

    if m15_anchored and base_ok:
        # Brecha B: POI anclado a narrativa HTF = bonus (+0.5), no condicion
        score += 0.5

    if po3_complete and base_ok:
        # Brecha E: PO3 A/M/D alineado en la direccion = bonus (+0.5)
        score += 0.5

    return AlignmentReport(
        score=score,
        d1=d1_ok,
        h4=h4_ok,
        h1=h1_ok,
        m15=m15_ok,
        m5=m5,
        m1=m1,
        m15_anchored=m15_anchored,
        po3_complete=po3_complete,
    )


def plan_step(fsm: PlanFSM, sig: dict, objs_by_tf: dict) -> PlanState:
    """Evalúa el estado del PLAN para UNA señal en su t (contexto cerrado <= t).

    La FSM se RESETEA por señal: el gate decide sobre el contexto HTF/M15
    cerrado en el momento t de la señal, no acumulando entre señales. Esto
    es coherente con "la tesis dicta el contexto en t" y con AC2 (el gate
    puede vetar cualquier señal individualmente según su propio contexto).

    Reusa _objs_before (anti look-ahead cross-TF por bar_time) y los emit_*.
    """
    fsm.reset()
    t = _field(sig, "time")
    d1 = _objs_before(objs_by_tf, "D1", t)
    h4 = _objs_before(objs_by_tf, "H4", t)
    h1 = _objs_before(objs_by_tf, "H1", t)
    m15 = _objs_before(objs_by_tf, "M15", t)
    m5 = _objs_before(objs_by_tf, "M5", t)
    m1 = _objs_before(objs_by_tf, "M1", t)

    ev = emit_d1(d1)
    if ev is not None:
        fsm.transition(ev)
    ev = emit_h4(h4)
    if ev is not None:
        fsm.transition(ev)
    ev = emit_h1(h1)
    if ev is not None:
        fsm.transition(ev)
    ev = emit_m15([sig])
    if ev is not None:
        fsm.transition(ev)
    # M5/M1 son exec TF: confirman en la MISMA dirección (no cambian plan).
    direction = _field(sig, "direction", 0)
    m5_confirm = build_confirm_from_tf(_to_df(m5), t, direction)
    ev = emit_m5(sig, m5_confirm)
    if ev is not None:
        fsm.transition(ev)
    m1_trigger = build_confirm_from_tf(_to_df(m1), t, direction)
    ev = emit_m1(sig, m1_trigger)
    if ev is not None:
        fsm.transition(ev)
    return fsm.state


def run_plan_fsm(
    signals: list,
    *,
    objs_by_tf: dict | list,
    threshold: PlanState = PlanState.STRUCTURE_OK,
) -> dict:
    """A1 Opción B — compuerta de ejecución FSM sobre señales YA generadas.

    Dueño de UNA sola instancia PlanFSM que vive durante TODO el backtest
    (no se resetea por señal). Por cada señal, en su t=signal.time, toma los
    MarketObjects cerrados <= t por TF y alimenta los emisores; fsm.transition.

    run_sequence NO se toca: recibe TODAS las señales (AC1). Solo decide
    cuáles SE OPERAN (AC2). Cada señal descartada reporta el estado FSM
    explícito que provocó el veto (AC3).

    Args:
        signals: lista de señales (dict ICTSignal) de run_sequence.
        objs_by_tf: MarketObjects por TF (``{tf: [MarketObject]}``), O una
            lista paralela a ``signals`` (``[ {tf: [...]}, ... ]``) para
            tests/demo sintéticos donde no hay eje temporal global.
        threshold: estado mínimo para operar (default STRUCTURE_OK).

    Devuelve:
        {
          "all_signals":  [todas las señales, igual al baseline],
          "trade_signals": [señales que la FSM deja operar],
          "vetoes": [{"signal_index", "state"} por cada descarte],
        }
    """
    fsm = PlanFSM()
    all_signals: list = []
    trade_signals: list = []
    vetoes: list = []

    for i, sig in enumerate(signals):
        all_signals.append(sig)
        # MarketObjects de ESTA señal (lista paralela) o globales (dict).
        objs = objs_by_tf[i] if isinstance(objs_by_tf, list) else objs_by_tf

        state = plan_step(fsm, sig, objs)
        if _state_rank(state) >= _state_rank(threshold):
            trade_signals.append(sig)
        else:
            vetoes.append({"signal_index": i, "state": state.value})

    return {
        "all_signals": all_signals,
        "trade_signals": trade_signals,
        "vetoes": vetoes,
    }


# Orden de autoridad del plan (para comparar umbrales).
_STATE_ORDER = {
    PlanState.NO_TRADE: 0,
    PlanState.CONTEXT_OK: 1,
    PlanState.ZONE_ARMED: 2,
    PlanState.SETUP_LIVE: 3,
    PlanState.STRUCTURE_OK: 4,
    PlanState.ENTRY_READY: 5,
    PlanState.IN_TRADE: 6,
    PlanState.CLOSED: 7,
}


def _state_rank(state: PlanState) -> int:
    return _STATE_ORDER.get(state, 0)


def _to_df(objs: list):
    """Convierte lista de MarketObjects a df mínimo para build_confirm_from_tf.

    build_confirm_from_tf espera columnas 'bos_dir'/'choch_dir'. Los objetos
    los mapeamos: BOS/CHOCH ACTIVE => dir en la columna correspondiente.
    """
    if not objs:
        return None
    import pandas as pd

    rows = []
    for o in objs:
        bos_dir = o.direction if o.type is ObjectType.BOS else 0
        choch_dir = o.direction if o.type is ObjectType.CHOCH else 0
        rows.append({"time": getattr(o, "bar_time", None), "bos_dir": bos_dir, "choch_dir": choch_dir})
    return pd.DataFrame(rows)
