"""ict_backtest/semantic_adapter.py — Adapter between R10.C semantic engine and canonical pipeline.

Converts the output of ``run_semantic`` into the dict format expected by
``canonical.evaluate_signals`` (which iterates ``raw_sigs`` and reads:
direction, entry_at, sweep_at, bos_at, time, entry, zone_authority, poi_present,
breaker_active/type/mitigation_level/strength, ote_confirmed/zone,
smt_divergence_active/direction/strength).

**Design principles:**
- Reuses existing code: ObjectGraph traversal (object_graph), MarketObject
  fields, and the signal fields already computed by run_semantic.
- No logic duplication: the adapter does NOT re-detect BOS/SWEEP or
  recompute zones.  It reads them from the graph and signal dicts.
- Minimal blast radius: does NOT modify run_sequence, canonical, or any
  existing module besides event_engine (which gains entry_at).
"""
from __future__ import annotations

from typing import Any

from ict_backtest.market_object import MarketObject, ObjectType


def adapt_semantic_to_legacy(
    semantic_signals: list[dict],
    objs: list[MarketObject],
    *,
    zone_authority_map: dict[str, Any] | None = None,
    poi_map: dict[str, bool] | None = None,
) -> list[dict]:
    """Convert R10.C semantic signals to the legacy dict format for canonical.py.

    Parameters
    ----------
    semantic_signals : list[dict]
        Output of ``run_semantic``.  Each dict has at minimum:
        id, root_id, type, direction, bar_index, entry_at, time,
        zone_high, zone_low, narrative_active, state.
    objs : list[MarketObject]
        The same object list passed to run_semantic (needed for graph
        traversal to find the BOS parent of each signal).
    zone_authority_map : dict[str, Any] | None
        Optional mapping signal_id -> ZoneAuthority (pre-computed).
    poi_map : dict[str, bool] | None
        Optional mapping signal_id -> bool (POI present, pre-computed).

    Returns
    -------
    list[dict]
        Dicts compatible with the ``raw_sigs`` consumed by
        ``canonical.evaluate_signals``.  Each dict has the fields:
        direction, entry_at, sweep_at, bos_at, time, entry,
        zone_authority, poi_present, breaker_active, breaker_type,
        mitigation_level, breaker_strength, ote_confirmed, ote_zone,
        smt_divergence_active, smt_divergence_direction,
        smt_divergence_strength.
    """
    if not semantic_signals or not objs:
        return []

    # Build quick lookup: signal_id -> MarketObject
    obj_by_id: dict[str, MarketObject] = {o.id: o for o in objs}

    # Build children index from graph (parent -> [children])
    children_of: dict[str, list[MarketObject]] = {}
    for o in objs:
        if o.parent_object:
            children_of.setdefault(o.parent_object, []).append(o)

    zone_auth = zone_authority_map or {}
    poi_present = poi_map or {}

    legacy_signals: list[dict] = []
    for sig in semantic_signals:
        sig_id = sig.get("id", "")
        obj = obj_by_id.get(sig_id)
        if obj is None:
            continue

        # --- Trace causal chain: root (SWEEP) and immediate BOS parent ---
        sweep_at: int | None = None
        bos_at: int | None = None
        bos_obj: MarketObject | None = None

        # Walk parents to find SWEEP (root) and BOS (intermediate)
        visited: set[str] = set()
        current: MarketObject | None = obj
        while current is not None and current.id not in visited:
            visited.add(current.id)
            if current.type == ObjectType.SWEEP:
                sweep_at = current.bar_index
            elif current.type in (ObjectType.BOS, ObjectType.CHOCH):
                if bos_at is None:
                    bos_at = current.bar_index
                    bos_obj = current
            parent_id = current.parent_object
            current = obj_by_id.get(parent_id) if parent_id else None

        # --- Build legacy signal dict ---
        legacy: dict[str, Any] = {
            "direction": sig["direction"],
            "entry_at": sig.get("entry_at", sig["bar_index"]),
            "bar_index": sig["bar_index"],  # backward compat
            "sweep_at": sweep_at,
            "bos_at": bos_at,
            "time": sig.get("time", ""),
            "entry": 0.0,  # placeholder; canonical.py resolves via fill_entry_price
            # Fields propagated from signal object metadata (R3.5)
            "breaker_active": (bos_obj.meta.get("breaker_active") if bos_obj else None),
            "breaker_type": (bos_obj.meta.get("breaker_type") if bos_obj else None),
            "mitigation_level": (bos_obj.meta.get("mitigation_level") if bos_obj else None),
            "breaker_strength": (bos_obj.meta.get("breaker_strength") if bos_obj else None),
            "ote_confirmed": (bos_obj.meta.get("ote_confirmed") if bos_obj else None),
            "ote_zone": (bos_obj.meta.get("ote_zone") if bos_obj else None),
            "smt_divergence_active": (bos_obj.meta.get("smt_divergence_active") if bos_obj else None),
            "smt_divergence_direction": (bos_obj.meta.get("smt_divergence_direction") if bos_obj else None),
            "smt_divergence_strength": (bos_obj.meta.get("smt_divergence_strength") if bos_obj else None),
        }

        # Optional pre-computed metadata
        legacy["zone_authority"] = zone_auth.get(sig_id)
        legacy["poi_present"] = poi_present.get(sig_id)

        legacy_signals.append(legacy)

    return legacy_signals
