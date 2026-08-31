"""Adaptador read-only de objetos canónicos para la lectura LTF.

Este módulo no define FVG, OB ni Sequence. Ensambla las implementaciones
canónicas existentes para que una lectura as-of(t) pueda entregar al motor
diario:

* ``MarketObject`` FVG/OB confirmados hasta ``decision_time``;
* relaciones FVG↔OB estrictamente causales y sus referencias de lineage;
* touch/mitigation observado después de ``tradable_time``;
* un resumen de ``engine.sequential_events`` con refs y profundidad.

La salida es observacional: no contiene entry, SL, TP, sizing ni órdenes.
"""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.lifecycle import evaluate
from engine.market_object import MarketObject, ObjectState
from engine.relations import relate_fvg_ob
from engine.sequential_events import SeqConfig, run_sequential


def _asof_prefix(frame: pd.DataFrame | None, decision_time: Any) -> pd.DataFrame:
    if frame is None or frame.empty or "time" not in frame.columns:
        return pd.DataFrame()
    tt = pd.to_datetime(decision_time, utc=True, errors="coerce")
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    if pd.isna(tt):
        return pd.DataFrame()
    return frame.loc[times <= tt].copy().reset_index(drop=True)


def _touch_state(obj: MarketObject, frame: pd.DataFrame, decision_time: Any) -> MarketObject:
    """Aplica observación causal de lifecycle sobre el objeto, vela a vela.

    Delega en engine.lifecycle (única autoridad de transición). Antes mutaba
    estado inline; ahora respeta la arquitectura de autoridad única: el feed
    solo ENSAMBLA y deja que lifecycle decida ACTIVE -> PARTIAL -> terminal.
    """
    if frame.empty or obj.tradable_time is None:
        return obj
    tt = pd.to_datetime(decision_time, utc=True, errors="coerce")
    tradable = pd.to_datetime(obj.tradable_time, utc=True, errors="coerce")
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    if pd.isna(tt) or pd.isna(tradable):
        return obj
    # La vela de confirmación crea la zona; no cuenta como retest de la zona.
    hits = frame.loc[(times > tradable) & (times <= tt)].copy()
    # Lifecycle solo puede producir una observacion o transicion cuando la
    # vela cruza la zona o cierra mas alla de su far_side. Las velas restantes
    # son NO_CHANGE y no dejan estado ni historial; filtrarlas conserva
    # exactamente la semantica de ``evaluate`` y evita un coste O(objetos x
    # barras) en la lectura operativa diaria.
    if not hits.empty:
        low = pd.to_numeric(hits["low"], errors="coerce")
        high = pd.to_numeric(hits["high"], errors="coerce")
        close = pd.to_numeric(hits["close"], errors="coerce")
        touched = (low <= obj.zone_high) & (high >= obj.zone_low)
        close_beyond = (
            (close < obj.zone_low) if obj.direction >= 0 else (close > obj.zone_high)
        )
        hits = hits.loc[(touched | close_beyond).fillna(False)].copy()
    hits["__index__"] = hits.index
    # Garantía C1: la barra debe llevar su sello de temporalidad para que
    # evaluate() valide closed_bar['tf'] == authority_tf. Sin esto, la
    # falsificación M15-disfrazado-de-H4 quedaría sin defender en producción.
    hits["tf"] = obj.origin_tf
    for _, row in hits.iterrows():
        evaluate(obj, row.to_dict(), authority_tf=obj.origin_tf, decision_time=row["time"])
    return obj


def _sequence_summary(frame: pd.DataFrame, decision_time: Any, timeframe: str) -> dict[str, Any]:
    prefix = _asof_prefix(frame, decision_time)
    if prefix.empty:
        return {"available": False, "refs": [], "depth": 0, "complete_count": 0, "timeframe": timeframe}
    chains = run_sequential(prefix, SeqConfig(structure_mode="canonical_bos", max_active_chains=128), symbol="", timeframe=timeframe)
    visible = [ch for ch in chains if int(ch.last_bar) < len(prefix)]
    visible.sort(key=lambda ch: (int(ch.last_bar), str(ch.chain_id)))
    return {
        "available": bool(visible),
        "refs": [str(ch.chain_id) for ch in visible],
        "depth": max((len(ch.nodes) for ch in visible), default=0),
        "complete_count": sum(ch.status == "COMPLETE" for ch in visible),
        "timeframe": timeframe,
        "asof_time": pd.to_datetime(prefix["time"], utc=True).max().isoformat(),
    }


def build_canonical_objects(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
    *,
    timeframes: tuple[str, ...] = ("D1", "H4", "H1", "M15"),
    symbol: str = "",
) -> dict[str, Any]:
    """Ensambla objetos canónicos closed-only sin avanzar su lifecycle.

    Esta es la interfaz de composición para consumidores que necesitan
    construir un ``engine.market_state.MarketState`` event-sourced. Los
    detectores siguen siendo los únicos que crean FVG/OB y ``relate_fvg_ob``
    sigue siendo la única autoridad de lineage; la función solo coordina esas
    APIs y deja las transiciones para ``engine.lifecycle``/``MarketState``.
    """
    normalized_tfs = tuple(dict.fromkeys(tf.upper() for tf in timeframes))
    objects_by_tf: dict[str, list[MarketObject]] = {}
    relations: list[Any] = []
    for tf in normalized_tfs:
        frame = _asof_prefix(frames.get(tf), decision_time)
        rows = frame.to_dict("records")
        fvgs = detect_fvg(rows, timeframe=tf, symbol=symbol)
        obs = detect_order_blocks(rows, timeframe=tf, symbol=symbol)
        objects_by_tf[tf] = [*fvgs, *obs]
        # Keep relation work bounded per timeframe. The relation layer itself
        # owns the strict causal rule; cross-TF setup composition remains a
        # separate consumer concern and must not create an O(N^2) operational
        # scan across every object in every timeframe.
        relations.extend(relate_fvg_ob(fvgs, obs, causal_mode="strict"))

    by_id = {
        obj.id: obj
        for objects in objects_by_tf.values()
        for obj in objects
    }
    for rel in relations:
        fvg = by_id[rel.fvg_id]
        ob = by_id[rel.ob_id]
        fvg.parent_object = ob.id
        if fvg.id not in ob.related_objects:
            ob.related_objects.append(fvg.id)
        fvg.meta.setdefault("lineage_refs", []).append(ob.id)
        ob.meta.setdefault("lineage_refs", []).append(fvg.id)

    return {
        "objects_by_tf": objects_by_tf,
        "objects": sorted(by_id.values(), key=lambda obj: (str(obj.tradable_time), str(obj.id))),
        "relations": [
            {
                "fvg_id": r.fvg_id,
                "ob_id": r.ob_id,
                "relation": r.relation,
                "direction": r.direction,
                "bars_apart": r.bars_apart,
            }
            for r in relations
        ],
    }


def build_ltf_canonical_feed(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
    *,
    exec_tf: str = "M15",
    sequence_tf: str = "H1",
    symbol: str = "",
    include_sequence: bool = True,
    touch_lifecycle: bool = True,
) -> dict[str, Any]:
    """Construye la entrada canónica read-only del motor diario.

    ``frames`` puede contener features, siempre que conserve OHLC y ``time``.
    Todos los detectores reciben exclusivamente el prefijo ``time <= t``.
    """
    exec_tf = exec_tf.upper()
    sequence_tf = sequence_tf.upper()
    frame = _asof_prefix(frames.get(exec_tf), decision_time)
    if frame.empty:
        return {
            "source": "engine.detectors + engine.relations + engine.sequential_events",
            "decision_time": pd.to_datetime(decision_time, utc=True, errors="coerce").isoformat(),
            "zones": {exec_tf: []},
            "sequence": {"available": False, "refs": [], "depth": 0, "complete_count": 0, "timeframe": sequence_tf},
            "lineage_refs": [],
        }

    assembled = build_canonical_objects(
        {exec_tf: frame}, decision_time, timeframes=(exec_tf,), symbol=symbol
    )
    by_id = {obj.id: obj for obj in assembled["objects"]}
    relations = [
        relate_fvg_ob(
            [by_id[r["fvg_id"]]], [by_id[r["ob_id"]]], causal_mode="strict"
        )[0]
        for r in assembled["relations"]
    ]
    fvgs = [obj for obj in assembled["objects"] if obj.type.value == "FVG"]
    obs = [obj for obj in assembled["objects"] if obj.type.value == "ORDER_BLOCK"]

    objects = [*fvgs, *obs]
    if touch_lifecycle:
        objects = [_touch_state(obj, frame, decision_time) for obj in objects]
    objects.sort(key=lambda obj: (str(obj.tradable_time), str(obj.id)))
    sequence = _sequence_summary(frames.get(sequence_tf), decision_time, sequence_tf) if include_sequence else {
        "available": False, "refs": [], "depth": 0, "complete_count": 0, "timeframe": sequence_tf,
    }
    lineage_refs = sorted({ref for obj in objects for ref in [obj.parent_object, *obj.related_objects] if ref})
    return {
        "source": "engine.detectors + engine.relations + engine.sequential_events",
        "decision_time": pd.to_datetime(decision_time, utc=True, errors="coerce").isoformat(),
        "zones": {exec_tf: objects},
        "relations": [
            {"fvg_id": r.fvg_id, "ob_id": r.ob_id, "relation": r.relation, "direction": r.direction, "bars_apart": r.bars_apart}
            for r in relations
        ],
        "sequence": sequence,
        "lineage_refs": lineage_refs,
    }


__all__ = ["build_canonical_objects", "build_ltf_canonical_feed"]
