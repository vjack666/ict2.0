"""ict_backtest/event_engine.py — Fase E (R10.C): motor canonico semantico.

Reemplaza el recorrido por timer de `run_sequence`. Las decisiones NACEN del
significado del mercado (eventos + estados + grafo + narrativa), NUNCA de
ventanas temporales ni de `i - idx > N`.

Flujo (DISENO_R10C_R11.md §5):
    detectors (objetos ya estructurales)
      -> EventEngine emite eventos
      -> StateMachine aplica transiciones (Fase A)
      -> Invalidators (Fase B) invalidan por contexto/grafo
      -> ObjectGraph (Fase C) navega relaciones
      -> MarketNarrative (Fase D) agrupa la historia
      -> senal SOLO si el objeto esta ACTIVE/MITIGATED en narrativa VIGENTE

NUNCA importa confirmation_window / bos_gap. max_hold es el UNICO tope de
seguridad (exposicion), no una ventana de confirmacion.
"""
from __future__ import annotations

from typing import Any, Callable

from ict_backtest.market_narrative import MarketNarrative
from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)
from ict_backtest.object_graph import ObjectGraph
from ict_backtest.state_machine import MarketEvent, StateMachine

# Tipos de objeto que pueden originar una senal (no el CANDLE observado).
_SIGNAL_TYPES = (ObjectType.BOS, ObjectType.CHOCH, ObjectType.FVG, ObjectType.ORDER_BLOCK)
# Tipos que funcionan como raiz de una narrativa (la historia arranca en el barrido).
_ROOT_TYPES = (ObjectType.SWEEP,)

# Mapeo objeto -> tipo de evento semantico (strings planos, ver state_machine).
_EVENT_BY_TYPE = {
    ObjectType.SWEEP: "LiquidityTaken",
    ObjectType.BOS: "StructureBroken",
    ObjectType.CHOCH: "StructureBroken",
    ObjectType.FVG: "LiquidityTaken",
    ObjectType.ORDER_BLOCK: "LiquidityTaken",
}

LAST_META: dict = {}


def _to_objs(ltf_df_or_objs: Any, ltf_tf: str) -> list[MarketObject]:
    if isinstance(ltf_df_or_objs, list):
        return ltf_df_or_objs
    # DataFrame: reutiliza el path de detectors (data_feed.build_objects).
    from ict_backtest.data_feed import build_objects

    return build_objects({ltf_tf: ltf_df_or_objs})


class EventEngine:
    """Cola de eventos discretos desde los objetos ya detectados.

    Un evento por objeto estructural relevante, ordenado por su bar_index
    (metadato del objeto, NO un reloj de decision). No recorre velas.
    """

    def emit(self, objs: list[MarketObject]) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        for o in objs:
            etype = _EVENT_BY_TYPE.get(o.type)
            if etype is None:
                continue
            events.append(MarketEvent(type=etype, target=o, context=None))
        events.sort(key=lambda e: e.target.bar_index or 0)
        return events


def run_semantic(
    ltf_df_or_objs: Any,
    est_htf_fn: Callable[..., Any],
    cfg: Any,
    htf_poi_fn: Callable[..., Any] | None = None,
    ltf_tf: str = "M15",
    max_hold: int = 200,
) -> list[dict]:
    """Motor canonico semantico. Emite senales SOLO desde objetos vivos.

    Sin reloj: la caducidad es por Invalidators (evento), no por N velas.
    max_hold es el unico tope de seguridad (exposicion), reportado en meta.
    """
    objs = _to_objs(ltf_df_or_objs, ltf_tf)
    g = ObjectGraph()
    for o in objs:
        g.add(o)
    for o in objs:
        if o.parent_object is not None:
            parent = g.get(o.parent_object)
            if parent is not None:
                g.link(parent, o)

    # Enlace CAUSAL (no temporal): cada BOS busca el SWEEP MAS CERCANO ANTERIOR
    # de su MISMA direccion de setup cuya ZONA CRUZA la del BOS (el precio salio
    # de la zona de liquidez y rompio estructura relevante). Ese sweep es la
    # causa del BOS (displacement -> BOS confirmado). Un sweep consume la
    # liquidez una sola vez (meta["consumed"]): si ya fue tomado por un BOS
    # previo, no alimenta a otro. Sin numero fijo de velas: la causalidad es por
    # ZONA (precio), no reloj. Relacion demostrada: Legacy ⊆ Semantic.
    bos_by_dir: dict[int, list[MarketObject]] = {}
    sweeps_by_dir: dict[int, list[MarketObject]] = {}
    for o in objs:
        if o.type == ObjectType.BOS:
            bos_by_dir.setdefault(o.direction, []).append(o)
        elif o.type == ObjectType.SWEEP:
            sweeps_by_dir.setdefault(o.direction, []).append(o)
    for d, bs in bos_by_dir.items():
        bs.sort(key=lambda b: b.bar_index or 0)
    for d, sw in sweeps_by_dir.items():
        sw.sort(key=lambda s: s.bar_index or 0)
    for d, bss in bos_by_dir.items():
        for bos in bss:
            for sw in sweeps_by_dir.get(d, []):
                if (sw.bar_index or 0) >= (bos.bar_index or 0):
                    break
                zh, zl = sw.zone_high, sw.zone_low
                if zh > 0 and zl > 0 and bos.zone_high >= zl and bos.zone_low <= zh \
                        and not sw.meta.get("consumed", False):
                    g.link(sw, bos)
                    sw.meta["consumed"] = True
                    sw.meta["linked_bos"] = bos.id
                    break

    sm = StateMachine()
    for ev in EventEngine().emit(objs):
        sm.apply(ev)

    roots = [o for o in objs if o.type in _ROOT_TYPES]
    narratives = [MarketNarrative.from_root(g, r) for r in roots if g.parents(r) == []]

    signals: list[dict] = []
    used_max_hold = 0
    for narr in narratives:
        if not narr.is_active():
            continue
        # Invalidador B2 (Fase B2) DENTRO de la narrativa: si hay un BOS de
        # direccion opuesta en ESTA historia, la estructura se invalida
        # (conflicto de direcciones = ruido). Semantico, no global, sin reloj.
        sig = narr.signal_objects()
        if any(o.type == ObjectType.BOS and o.direction != b.direction
               for b in sig if b.type == ObjectType.BOS
               for o in sig):
            continue
        for o in sig:
            if o.type not in _SIGNAL_TYPES:
                continue
            # Cadena minima (ambiguedad A3): debe colgar de un SWEEP (la misma
            # precondicion que exige run_sequence). Sin esto, run_semantic
            # podria ser mas permisivo que el legacy y romper el SUBSET.
            parents = g.parents(o)
            root = next((p for p in parents if p.type in _ROOT_TYPES), None)
            if root is None:
                continue
            if o.state not in (ObjectState.ACTIVE, ObjectState.MITIGATED):
                continue
            if not (o.zone_high > 0 or o.zone_low > 0):
                continue
            # Tope de seguridad (exposicion), NO ventana de confirmacion.
            if max_hold is not None and o.bar_index > max_hold:
                used_max_hold += 1
            signals.append({
                "id": o.id,
                "root_id": root.id,
                "type": o.type.value,
                "direction": o.direction,
                "bar_index": o.bar_index,
                "zone_high": o.zone_high,
                "zone_low": o.zone_low,
                "narrative_active": True,
                "state": o.state.value,
            })

    # Meta de seguridad (sin reloj de decision).
    LAST_META.clear()
    LAST_META["max_hold_used"] = used_max_hold
    LAST_META["signal_count"] = len(signals)
    return signals
