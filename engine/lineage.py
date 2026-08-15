"""engine/lineage.py — Consumidor puro de trazabilidad causal (SDD_M2_LINEAGE).

Reconstruye la cadena causal de UN setup a partir de la señal ya emitida por
el motor (`run_sequence_traced`): resuelve cada `parent_object` a su objeto real
y comprueba que la cadena LIQUIDITY -> SWEEP -> DISPLACE -> BOS -> POI/REFINEMENT
-> RETURN está enlazada por ORIGEN (parent_object), NO por proximidad temporal.

Esto es exactamente la dimensión CAUSALITY de SDD_GOVERNANCE §4 sobre el producto
real. Es CONSUMIDOR PURO: NO importa ict_backtest/, NO decide, NO detecta. Solo
lee `signal["event_ids"]` + `signal["event_objects"]` y audita el linaje.

Ley: no introduce indicadores; el nivel ya es OHLC-derivable en el motor.
Sin WR/PF/edge; sin LTF/Macro. Solo REPRESENTACIÓN + TRAZABILIDAD.
"""

from __future__ import annotations

from typing import Any

# Orden canónico de la cadena ICT/SMC (tesis). El POI es opcional (anclado solo
# si el HTF lo tiene; si no, REFINEMENT cuelga directo del BOS).
_CHAIN_ORDER = ["LIQUIDITY", "SWEEP", "DISPLACE", "BOS", "POI", "REFINEMENT", "RETURN"]


def trace_setup_lineage(signal: dict) -> dict:
    """Audita el linaje causal de una señal del motor.

    Args:
        signal: dict emitido por ``run_sequence_traced`` con las claves
            ``event_ids`` (rol -> id) y ``event_objects`` (id -> dict de
            MarketObject, incluyendo ``parent_object`` y ``bar_index``).

    Returns:
        dict con las dimensiones de SDD_GOVERNANCE §4:
            linked         : bool  — toda la cadena enlazada por parent_object
            chain          : [id]  — ids en orden LIQUIDITY..RETURN (solo los presentes)
            breaks         : [str] — descripción de cada eslabón roto
            parent_resolved: bool  — todo parent_object apunta a id existente
            temporal_ok    : bool  — parent.bar_index <= child.bar_index siempre
    """
    event_ids: dict = signal.get("event_ids", {}) or {}
    event_objects: dict = signal.get("event_objects", {}) or {}

    result: dict[str, Any] = {
        "linked": False,
        "chain": [],
        "breaks": [],
        "parent_resolved": True,
        "temporal_ok": True,
    }

    if not event_objects:
        result["breaks"].append("event_objects ausente en la señal")
        return result

    # Cadena en el orden canónico, solo roles presentes en esta señal.
    chain = [event_ids[r] for r in _CHAIN_ORDER if r in event_ids]
    result["chain"] = chain

    # 1) Resolubilidad de padres: cada parent_object debe apuntar a un id real.
    for role in _CHAIN_ORDER:
        cid = event_ids.get(role)
        if cid is None:
            continue
        obj = event_objects.get(cid)
        if obj is None:
            result["parent_resolved"] = False
            result["breaks"].append(f"{role}: id {cid} no existe en event_objects")
            continue
        parent = obj.get("parent_object") or ""
        if parent and parent not in event_objects:
            result["parent_resolved"] = False
            result["breaks"].append(
                f"{role}: parent_object={parent} no resoluble en event_objects"
            )

    # 2) Orden temporal por origen: parent.bar_index <= child.bar_index.
    for role in _CHAIN_ORDER:
        cid = event_ids.get(role)
        if cid is None:
            continue
        obj = event_objects.get(cid)
        if obj is None:
            continue
        parent = obj.get("parent_object") or ""
        if not parent:
            continue  # raíz (LIQUIDITY) no tiene padre
        parent_obj = event_objects.get(parent)
        if parent_obj is None:
            continue  # ya reportado en resolubilidad
        child_idx = obj.get("bar_index")
        parent_idx = parent_obj.get("bar_index")
        if child_idx is None or parent_idx is None:
            continue
        if int(parent_idx) > int(child_idx):
            result["temporal_ok"] = False
            result["breaks"].append(
                f"{role}: parent.bar_index={parent_idx} > child.bar_index={child_idx}"
            )

    # 3) linked = cadena continua por parent_object (cada eslabón salvo raíz
    #    apunta al rol inmediatamente anterior en la cadena canónica).
    linked = result["parent_resolved"]
    for idx, role in enumerate(_CHAIN_ORDER):
        cid = event_ids.get(role)
        if cid is None:
            continue
        obj = event_objects.get(cid)
        if obj is None:
            linked = False
            break
        if role == "LIQUIDITY":
            if obj.get("parent_object"):
                # LIQUIDITY es raíz: no debe tener padre.
                result["breaks"].append("LIQUIDITY con parent_object (debe ser raíz)")
                linked = False
            continue
        # el padre esperado es el rol anterior presente en la señal
        prev_role = None
        for r in reversed(_CHAIN_ORDER[:idx]):
            if r in event_ids:
                prev_role = r
                break
        if prev_role is None:
            continue
        expected_parent = event_ids.get(prev_role)
        if obj.get("parent_object") != expected_parent:
            linked = False
            result["breaks"].append(
                f"{role}: parent_object={obj.get('parent_object')} != "
                f"id de {prev_role}={expected_parent}"
            )

    result["linked"] = bool(linked) and result["parent_resolved"] and result["temporal_ok"]
    return result
