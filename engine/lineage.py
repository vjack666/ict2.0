"""engine/lineage.py — Consumidor y compuerta global de trazabilidad causal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from engine.market_object import MarketObject

_CHAIN_ORDER = ["LIQUIDITY", "SWEEP", "DISPLACE", "BOS", "POI", "REFINEMENT", "RETURN"]


def _coerce_market_object(value: Any) -> MarketObject | None:
    if isinstance(value, MarketObject):
        return value
    if isinstance(value, Mapping):
        try:
            return MarketObject.from_dict(dict(value))
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _object_time(obj: MarketObject) -> object:
    for attr in ("tradable_time", "confirmation_time", "bar_time", "candidate_time", "creation_time"):
        value = getattr(obj, attr, None)
        if value is not None:
            return value
    return None


def _normalized_time(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (int, float, datetime)):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime()
        except Exception:
            pass
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return datetime.fromisoformat(value.isoformat().replace("Z", "+00:00"))
        except Exception:
            return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value


def _time_gt(left: object, right: object) -> bool:
    left_n = _normalized_time(left)
    right_n = _normalized_time(right)
    try:
        return bool(left_n > right_n)
    except TypeError as exc:
        raise ValueError(f"timestamps no comparables: {left!r} vs {right!r}") from exc


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
        child_tf = obj.get("origin_tf")
        parent_tf = parent_obj.get("origin_tf")
        if child_tf and parent_tf and child_tf == parent_tf and child_idx is not None and parent_idx is not None:
            if int(parent_idx) > int(child_idx):
                result["temporal_ok"] = False
                result["breaks"].append(f"{role}: parent.bar_index={parent_idx} > child.bar_index={child_idx}")
        parent_time = parent_obj.get("tradable_time") or parent_obj.get("confirmation_time") or parent_obj.get("bar_time")
        child_time = obj.get("tradable_time") or obj.get("confirmation_time") or obj.get("bar_time")
        if parent_time is not None and child_time is not None:
            try:
                if _time_gt(parent_time, child_time):
                    result["temporal_ok"] = False
                    result["breaks"].append(f"{role}: parent_time={parent_time} > child_time={child_time}")
            except ValueError as exc:
                result["temporal_ok"] = False
                result["breaks"].append(str(exc))
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
    parent_bar: int | None
    child_bar: int | None
    parent_time: object = None
    child_time: object = None
    parent_tf: str | None = None
    child_tf: str | None = None

    def __post_init__(self) -> None:
        if not self.parent_id or not self.child_id:
            raise ValueError("CausalLink requiere parent_id y child_id")
        if self.parent_id == self.child_id:
            raise ValueError("Un objeto no puede ser su propio ancestro")
        comparable_bar_space = not self.parent_tf or not self.child_tf or self.parent_tf == self.child_tf
        if comparable_bar_space and self.parent_bar is not None and self.child_bar is not None:
            if self.parent_bar > self.child_bar:
                raise ValueError("El parent no puede aparecer después del child")
        if self.parent_time is not None and self.child_time is not None:
            if _time_gt(self.parent_time, self.child_time):
                raise ValueError("El parent_time no puede ser posterior al child_time")


@dataclass(frozen=True)
class LineageValidationResult:
    valid: bool
    object_count: int
    link_count: int
    roots: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    links: tuple[CausalLink, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "object_count": self.object_count,
            "link_count": self.link_count,
            "roots": list(self.roots),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "links": [
                {
                    "parent_id": item.parent_id,
                    "child_id": item.child_id,
                    "relation": item.relation,
                    "parent_bar": item.parent_bar,
                    "child_bar": item.child_bar,
                    "parent_time": str(item.parent_time) if item.parent_time is not None else None,
                    "child_time": str(item.child_time) if item.child_time is not None else None,
                    "parent_tf": item.parent_tf,
                    "child_tf": item.child_tf,
                }
                for item in self.links
            ],
        }


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
        parent_tf=getattr(parent, "origin_tf", None),
        child_tf=getattr(child, "origin_tf", None),
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


def validate_hierarchical_lineage(
    objects: Mapping[str, Any] | Sequence[Any] | Iterable[Any],
    *,
    decision_time: object = None,
    root_ids: Iterable[str] | None = None,
    require_related: bool = True,
) -> LineageValidationResult:
    """Valida el grafo global de MarketObjects de forma fail-closed."""
    raw_values = list(objects.values()) if isinstance(objects, Mapping) else list(objects or ())
    by_id: dict[str, MarketObject] = {}
    errors: list[str] = []
    warnings: list[str] = []

    for raw in raw_values:
        obj = _coerce_market_object(raw)
        if obj is None:
            errors.append("objeto de lineage no convertible a MarketObject")
            continue
        oid = str(obj.id or "")
        if not oid:
            errors.append("MarketObject con id vacío")
            continue
        if oid in by_id:
            errors.append(f"id duplicado en grafo: {oid}")
            continue
        by_id[oid] = obj

    roots_requested = tuple(str(x) for x in (root_ids or ()) if x)
    for root_id in roots_requested:
        if root_id not in by_id:
            errors.append(f"root_id huérfano: {root_id}")

    links: list[CausalLink] = []
    for child in by_id.values():
        child_time = _object_time(child)
        if decision_time is not None:
            if child_time is None:
                errors.append(f"{child.id}: sin timestamp causal para decision_time")
            else:
                try:
                    if _time_gt(child_time, decision_time):
                        errors.append(f"{child.id}: objeto futuro respecto a decision_time")
                except ValueError as exc:
                    errors.append(f"{child.id}: {exc}")

        parent_id = str(child.parent_object) if child.parent_object else ""
        if parent_id:
            parent = by_id.get(parent_id)
            if parent is None:
                errors.append(f"{child.id}: parent_object huérfano={parent_id}")
            else:
                try:
                    links.append(CausalLink(
                        parent_id=parent.id,
                        child_id=child.id,
                        relation="PARENT_OBJECT",
                        parent_bar=parent.bar_index,
                        child_bar=child.bar_index,
                        parent_time=_object_time(parent),
                        child_time=child_time,
                        parent_tf=parent.origin_tf,
                        child_tf=child.origin_tf,
                    ))
                except ValueError as exc:
                    errors.append(f"{child.id}: {exc}")

        if require_related:
            for related_id in child.related_objects:
                if str(related_id) not in by_id:
                    errors.append(f"{child.id}: related_object huérfano={related_id}")

    try:
        links = validate_links(links)
    except ValueError as exc:
        errors.append(str(exc))

    color: dict[str, int] = {oid: 0 for oid in by_id}
    stack: list[str] = []

    def visit(oid: str) -> None:
        if color[oid] == 2:
            return
        if color[oid] == 1:
            cycle = stack[stack.index(oid):] + [oid] if oid in stack else stack + [oid]
            errors.append("ciclo parent_object: " + " -> ".join(cycle))
            return
        color[oid] = 1
        stack.append(oid)
        parent_id = by_id[oid].parent_object
        if parent_id and str(parent_id) in by_id:
            visit(str(parent_id))
        stack.pop()
        color[oid] = 2

    for oid in by_id:
        if color[oid] == 0:
            visit(oid)

    natural_roots = tuple(sorted(oid for oid, obj in by_id.items() if not obj.parent_object))
    if by_id and not natural_roots:
        errors.append("grafo sin raíz causal")

    return LineageValidationResult(
        valid=not errors,
        object_count=len(by_id),
        link_count=len(links),
        roots=natural_roots,
        errors=tuple(errors),
        warnings=tuple(warnings),
        links=tuple(links),
    )


__all__ = [
    "CausalLink",
    "LineageValidationResult",
    "link",
    "trace_setup_lineage",
    "validate_hierarchical_lineage",
    "validate_links",
]
