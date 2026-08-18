"""engine/lineage.py — Consumidor puro de trazabilidad causal (SDD_M2_LINEAGE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

_CHAIN_ORDER = ["LIQUIDITY", "SWEEP", "DISPLACE", "BOS", "POI", "REFINEMENT", "RETURN"]


def trace_setup_lineage(signal: dict) -> dict:
    """Audita el linaje causal de una señal del motor."""
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
    result["chain"] = [event_ids[r] for r in _CHAIN_ORDER if r in event_ids]
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
            result["breaks"].append(f"{role}: parent_object={parent} no resoluble en event_objects")
    for role in _CHAIN_ORDER:
        cid = event_ids.get(role)
        if cid is None:
            continue
        obj = event_objects.get(cid)
        if obj is None:
            continue
        parent = obj.get("parent_object") or ""
        parent_obj = event_objects.get(parent)
        if not parent or parent_obj is None:
            continue
        child_idx = obj.get("bar_index")
        parent_idx = parent_obj.get("bar_index")
        if child_idx is not None and parent_idx is not None and int(parent_idx) > int(child_idx):
            result["temporal_ok"] = False
            result["breaks"].append(f"{role}: parent.bar_index={parent_idx} > child.bar_index={child_idx}")
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
                result["breaks"].append("LIQUIDITY con parent_object (debe ser raíz)")
                linked = False
            continue
        prev_role = next((r for r in reversed(_CHAIN_ORDER[:idx]) if r in event_ids), None)
        if prev_role is None:
            continue
        expected_parent = event_ids.get(prev_role)
        if obj.get("parent_object") != expected_parent:
            linked = False
            result["breaks"].append(
                f"{role}: parent_object={obj.get('parent_object')} != id de {prev_role}={expected_parent}"
            )
    result["linked"] = bool(linked) and result["parent_resolved"] and result["temporal_ok"]
    return result


@dataclass(frozen=True)
class CausalLink:
    parent_id: str
    child_id: str
    relation: str
    parent_bar: int
    child_bar: int
    parent_time: object = None
    child_time: object = None

    def __post_init__(self) -> None:
        if not self.parent_id or not self.child_id:
            raise ValueError("CausalLink requiere parent_id y child_id")
        if self.parent_id == self.child_id:
            raise ValueError("Un objeto no puede ser su propio ancestro")
        if self.parent_bar > self.child_bar:
            raise ValueError("El parent no puede aparecer después del child")
        if self.parent_time is not None and self.child_time is not None:
            try:
                if self.parent_time > self.child_time:
                    raise ValueError("El parent_time no puede ser posterior al child_time")
            except TypeError as exc:
                raise ValueError("parent_time y child_time deben ser comparables") from exc


def link(parent: Any, child: Any, relation: str) -> CausalLink:
    if parent.bar_index is None or child.bar_index is None:
        raise ValueError("Los objetos deben tener bar_index para crear lineage causal")
    return CausalLink(
        parent_id=parent.id,
        child_id=child.id,
        relation=relation,
        parent_bar=parent.bar_index,
        child_bar=child.bar_index,
        parent_time=parent.bar_time or parent.creation_time,
        child_time=child.bar_time or child.creation_time,
    )


def validate_links(links: Iterable[CausalLink]) -> list[CausalLink]:
    result = list(links)
    seen: set[tuple[str, str, str]] = set()
    for item in result:
        key = (item.parent_id, item.child_id, item.relation)
        if key in seen:
            raise ValueError("No se permiten enlaces causales duplicados")
        seen.add(key)
    return result
