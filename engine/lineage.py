"""engine/lineage.py — Consumidor y compuerta global de trazabilidad causal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from engine.market_object import MarketObject, ObjectState, ObjectType, Role

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


SIX_TF_CHAIN: tuple[str, ...] = ("D1", "H4", "H1", "M15", "M5", "M1")
_TF_DURATION = {
    "D1": pd.Timedelta(days=1),
    "H4": pd.Timedelta(hours=4),
    "H1": pd.Timedelta(hours=1),
    "M15": pd.Timedelta(minutes=15),
    "M5": pd.Timedelta(minutes=5),
    "M1": pd.Timedelta(minutes=1),
}


def build_six_tf_lineage_spine(
    frames: Mapping[str, Any],
    decision_time: object,
    *,
    symbol: str = "",
    required_chain: Sequence[str] = SIX_TF_CHAIN,
) -> tuple[list[MarketObject], dict[str, Any]]:
    """Materializa la espina temporal cerrada usando el reloj real de cada TF."""
    tt = pd.to_datetime(decision_time, utc=True, errors="coerce")
    chain = tuple(str(tf).upper() for tf in required_chain)
    if pd.isna(tt):
        return [], {tf: {"available": False, "closed_only": False} for tf in chain}

    objects: list[MarketObject] = []
    layers: dict[str, Any] = {}
    parent_id: str | None = None

    for tf in chain:
        frame = frames.get(tf)
        duration = _TF_DURATION.get(tf)
        if frame is None or getattr(frame, "empty", True) or "time" not in frame.columns or duration is None:
            layers[tf] = {"available": False, "closed_only": False}
            parent_id = None
            continue

        opens = pd.to_datetime(frame["time"], utc=True, errors="coerce")
        closes = opens + duration
        mask = opens.notna() & (closes <= tt)
        positions = mask.to_numpy().nonzero()[0]
        if len(positions) == 0:
            layers[tf] = {"available": False, "closed_only": False}
            parent_id = None
            continue

        pos = int(positions[-1])
        open_time = opens.iloc[pos]
        close_time = closes.iloc[pos]
        row = frame.iloc[pos]
        try:
            price = float(row.get("close", 0.0))
        except (TypeError, ValueError):
            price = 0.0

        object_id = f"LINEAGE_LAYER_{tf}_{pd.Timestamp(close_time).value}"
        obj = MarketObject(
            id=object_id,
            symbol=symbol,
            type=ObjectType.CONTRACT,
            origin_tf=tf,
            role=Role.CONTEXT,
            direction=0,
            zone_high=price,
            zone_low=price,
            creation_time=close_time,
            state=ObjectState.ACTIVE,
            parent_object=parent_id,
            bar_index=pos,
            bar_time=close_time,
            candidate_bar=pos,
            candidate_time=close_time,
            confirmation_bar=pos,
            confirmation_time=close_time,
            tradable_bar=pos,
            tradable_time=close_time,
            meta={
                "lineage_layer_anchor": True,
                "source_open_time": pd.Timestamp(open_time).isoformat(),
                "source_close_time": pd.Timestamp(close_time).isoformat(),
            },
        )
        objects.append(obj)
        parent_id = obj.id
        layers[tf] = {
            "available": True,
            "closed_only": bool(close_time <= tt),
            "object_id": obj.id,
            "bar_index": pos,
            "open_time": pd.Timestamp(open_time).isoformat(),
            "close_time": pd.Timestamp(close_time).isoformat(),
        }

    return objects, layers


@dataclass(frozen=True)
class SixTFLineageValidationResult:
    valid: bool
    required_chain: tuple[str, ...]
    object_ids: tuple[str, ...]
    missing_tfs: tuple[str, ...]
    errors: tuple[str, ...]
    global_validation: LineageValidationResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "required_chain": list(self.required_chain),
            "object_ids": list(self.object_ids),
            "missing_tfs": list(self.missing_tfs),
            "errors": list(self.errors),
            "global_validation": self.global_validation.to_dict(),
        }


def validate_six_tf_lineage(
    objects: Mapping[str, Any] | Sequence[Any] | Iterable[Any],
    *,
    decision_time: object = None,
    required_chain: Sequence[str] = SIX_TF_CHAIN,
    require_related: bool = True,
) -> SixTFLineageValidationResult:
    """Exige una espina causal directa D1→H4→H1→M15→M5→M1.

    No basta con que las seis temporalidades existan por separado: debe existir
    al menos un camino parent_object continuo cuyo orden de TF coincida
    exactamente con required_chain. La validación global sigue siendo
    obligatoria, por lo que huérfanos, ciclos, referencias relacionadas rotas y
    objetos futuros invalidan también la certificación 6-TF.
    """
    chain = tuple(str(tf).upper() for tf in required_chain)
    if len(chain) < 2 or len(set(chain)) != len(chain):
        raise ValueError("required_chain debe contener TF únicas en orden jerárquico")

    raw_values = list(objects.values()) if isinstance(objects, Mapping) else list(objects or ())
    coerced: list[MarketObject] = []
    for raw in raw_values:
        obj = _coerce_market_object(raw)
        if obj is not None:
            coerced.append(obj)

    global_validation = validate_hierarchical_lineage(
        coerced,
        decision_time=decision_time,
        require_related=require_related,
    )
    by_id = {str(obj.id): obj for obj in coerced}
    present_tfs = {str(obj.origin_tf).upper() for obj in coerced}
    missing_tfs = tuple(tf for tf in chain if tf not in present_tfs)
    errors = list(global_validation.errors)
    if missing_tfs:
        errors.append("temporalidades ausentes: " + ",".join(missing_tfs))

    selected: tuple[str, ...] = ()
    leaf_tf = chain[-1]
    leaves = sorted(
        (obj for obj in coerced if str(obj.origin_tf).upper() == leaf_tf),
        key=lambda obj: str(obj.id),
    )
    for leaf in leaves:
        current = leaf
        reverse_path: list[MarketObject] = []
        ok = True
        for expected_tf in reversed(chain):
            if current is None or str(current.origin_tf).upper() != expected_tf:
                ok = False
                break
            reverse_path.append(current)
            if expected_tf == chain[0]:
                if current.parent_object:
                    ok = False
                break
            parent_id = str(current.parent_object or "")
            parent = by_id.get(parent_id)
            if parent is None:
                ok = False
                break
            current = parent
        if ok and len(reverse_path) == len(chain):
            path = tuple(reversed(reverse_path))
            if tuple(str(obj.origin_tf).upper() for obj in path) == chain:
                selected = tuple(str(obj.id) for obj in path)
                break

    if not selected:
        errors.append("no existe camino parent_object directo " + "→".join(chain))
    else:
        symbols = {
            str(by_id[oid].symbol).upper()
            for oid in selected
            if str(by_id[oid].symbol or "").strip()
        }
        if len(symbols) > 1:
            errors.append("la espina 6-TF mezcla símbolos: " + ",".join(sorted(symbols)))

    return SixTFLineageValidationResult(
        valid=not errors,
        required_chain=chain,
        object_ids=selected,
        missing_tfs=missing_tfs,
        errors=tuple(errors),
        global_validation=global_validation,
    )


def validate_six_tf_persistence_consistency(
    persisted_objects: Mapping[str, Any] | Sequence[Any] | Iterable[Any],
    frames: Mapping[str, Any],
    decision_time: object,
    *,
    symbol: str = "",
    required_chain: Sequence[str] = SIX_TF_CHAIN,
) -> dict[str, Any]:
    """Contrasta la espina 6-TF persistida con la derivada de barras cerradas.

    La validación global del registro completo sigue siendo responsabilidad de
    validate_hierarchical_lineage. Aquí se aíslan únicamente los anchors
    lineage_layer_anchor para comprobar que MarketState no publique una
    espina vieja, alterada o incompleta respecto de los feeds en T.
    """
    raw_values = (
        list(persisted_objects.values())
        if isinstance(persisted_objects, Mapping)
        else list(persisted_objects or ())
    )
    anchors: list[MarketObject] = []
    for raw in raw_values:
        obj = _coerce_market_object(raw)
        if obj is not None and bool((obj.meta or {}).get("lineage_layer_anchor")):
            anchors.append(obj)

    inferred_symbol = str(symbol or "").strip()
    if not inferred_symbol:
        inferred_symbol = next(
            (str(obj.symbol) for obj in anchors if str(obj.symbol or "").strip()),
            "",
        )

    persisted = validate_six_tf_lineage(
        anchors,
        decision_time=decision_time,
        required_chain=required_chain,
        # Anchor.related_objects may point to canonical event objects outside
        # this isolated subset. Those refs are checked by the global registry.
        require_related=False,
    )
    expected_objects, expected_layers = build_six_tf_lineage_spine(
        frames,
        decision_time,
        symbol=inferred_symbol,
        required_chain=required_chain,
    )
    expected = validate_six_tf_lineage(
        expected_objects,
        decision_time=decision_time,
        required_chain=required_chain,
        require_related=False,
    )

    def signature(
        objects: Sequence[MarketObject],
        validation: SixTFLineageValidationResult,
    ) -> list[dict[str, Any]]:
        by_id = {str(obj.id): obj for obj in objects}
        rows: list[dict[str, Any]] = []
        for oid in validation.object_ids:
            obj = by_id.get(str(oid))
            if obj is None:
                continue
            meta = obj.meta or {}
            rows.append({
                "id": str(obj.id),
                "tf": str(obj.origin_tf).upper(),
                "parent_id": str(obj.parent_object or ""),
                "bar_index": obj.bar_index,
                "tradable_time": str(pd.to_datetime(_object_time(obj), utc=True, errors="coerce")),
                "zone_low": obj.zone_low,
                "zone_high": obj.zone_high,
                "symbol": str(obj.symbol or "").upper(),
                "source_open_time": str(meta.get("source_open_time") or ""),
                "source_close_time": str(meta.get("source_close_time") or ""),
            })
        return rows

    persisted_signature = signature(anchors, persisted)
    expected_signature = signature(expected_objects, expected)
    errors: list[str] = []
    if not anchors:
        errors.append("espina 6-TF persistida ausente")
    if not persisted.valid:
        errors.extend(f"persisted:{item}" for item in persisted.errors)
    if not expected.valid:
        errors.extend(f"derived:{item}" for item in expected.errors)
    exact_match = bool(
        persisted.valid
        and expected.valid
        and persisted_signature == expected_signature
    )
    if persisted.valid and expected.valid and not exact_match:
        errors.append("espina 6-TF persistida no coincide con barras cerradas en decision_time")

    return {
        "valid": bool(exact_match and not errors),
        "status": "PASS" if exact_match and not errors else "FAIL",
        "errors": errors,
        "persisted": persisted.to_dict(),
        "derived": expected.to_dict(),
        "persisted_signature": persisted_signature,
        "derived_signature": expected_signature,
        "derived_layers": expected_layers,
    }


__all__ = [
    "CausalLink",
    "LineageValidationResult",
    "SIX_TF_CHAIN",
    "build_six_tf_lineage_spine",
    "SixTFLineageValidationResult",
    "link",
    "trace_setup_lineage",
    "validate_hierarchical_lineage",
    "validate_six_tf_lineage",
    "validate_six_tf_persistence_consistency",
    "validate_links",
]
