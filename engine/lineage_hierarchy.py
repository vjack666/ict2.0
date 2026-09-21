"""engine/lineage_hierarchy.py — Adaptador único de lineage jerárquico causal (6 TFs).

Reutiliza CausalLink, MarketObject, FVGOBRelation sin duplicar lógica central.
Valida el grafo completo a tiempo T con proyección point-in-time.
Devuelve grafo, raíces, hojas, profundidad, breaks, estados, recuentos y provenance.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping

from engine.lineage import CausalLink, validate_links
from engine.market_object import MarketObject, ObjectType, Role
from engine.relations import FVGOBRelation, relation_links


# ---------------------------------------------------------------------------
# Estados del lineage (gate fail-closed)
# ---------------------------------------------------------------------------

class LineageStatus(str, Enum):
    VALID = "LINEAGE_VALID"
    INCOMPLETE = "LINEAGE_INCOMPLETE"
    INVALID = "LINEAGE_INVALID"
    ORPHAN = "LINEAGE_ORPHAN"
    FUTURE = "LINEAGE_FUTURE"
    CYCLE = "LINEAGE_CYCLE"
    UNRESOLVED = "LINEAGE_UNRESOLVED"
    LEGACY_UNVALIDATED = "LINEAGE_LEGACY_UNVALIDATED"


# ---------------------------------------------------------------------------
# Estructuras de resultado
# ---------------------------------------------------------------------------

@dataclass
class HierarchicalLineage:
    """Resultado único del lineage jerárquico completo.

    Contiene el grafo validado, breaks, huérfanos, ciclos, futuros,
    no resueltos, violaciones temporales, recuentos y provenance por TF.
    """

    status: LineageStatus
    links: list[CausalLink] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    leaves: list[str] = field(default_factory=list)
    depth: int = 0
    breaks: list[str] = field(default_factory=list)
    orphan_ids: list[str] = field(default_factory=list)
    cycle_ids: list[str] = field(default_factory=list)
    future_links: list[tuple[str, str]] = field(default_factory=list)
    unresolved_ids: list[str] = field(default_factory=list)
    temporal_violations: list[str] = field(default_factory=list)
    relation_counts: dict[str, int] = field(default_factory=dict)
    provenance_by_tf: dict[str, list[str]] = field(default_factory=dict)
    objects_by_id: dict[str, MarketObject] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TF hierarchy (6 temporalidades)
# ---------------------------------------------------------------------------

SIX_TFS_ORDERED = ("D1", "H4", "H1", "M15", "M5", "M1")

POI_TFS = {"D1", "H4", "H1"}
REFINEMENT_TFS = {"H1", "M15", "M5", "M1"}
EXECUTION_TFS = {"M15", "M5", "M1"}
CONTEXT_TFS = {"D1", "H4", "H1"}


def _tf_rank(tf: str) -> int:
    """Rank de temporalidad para orden jerárquico (mayor TF = menor rank)."""
    try:
        return SIX_TFS_ORDERED.index(tf)
    except ValueError:
        return 99


# ---------------------------------------------------------------------------
# Construcción del lineage jerárquico
# ---------------------------------------------------------------------------

def build_hierarchical_lineage(
    objects: Mapping[str, MarketObject],
    *,
    relations: Iterable[FVGOBRelation] | None = None,
    causal_links: Iterable[CausalLink] | None = None,
    projection: Mapping[str, MarketObject] | None = None,
    decision_time: Any = None,
    require_all_six_tfs: bool = False,
) -> HierarchicalLineage:
    """Construye y valida el lineage jerárquico completo de 6 TFs.

    Parámetros
    ----------
    objects : dict[str, MarketObject]
        Todos los objetos del universo (o proyección en T).
    relations : iterable[FVGOBRelation], opcional
        Relaciones FVG↔OB del módulo relations.py.
    causal_links : iterable[CausalLink], opcional
        Enlaces causales ya construidos (alternativa a relations).
    projection : dict[str, MarketObject], opcional
        Si se proporciona, el lineage se valida sobre esta proyección
        point-in-time. Los objetos fuera de la proyección se tratan como
        no disponibles (fail-closed).
    decision_time : any, opcional
        Timestamp de decisión para validaciones point-in-time.
    require_all_six_tfs : bool
        Si True, requiere que los 6 TFs estén presentes en el lineage para
        considerarlo completo. Si solo H4+M15 están presentes, el estado
        será LEGACY_UNVALIDATED o INCOMPLETE según el caso.
    """
    # 1. Determinar conjunto de objetos disponibles
    if projection is not None:
        available_ids = set(projection.keys())
        available_objects = dict(projection)
    else:
        available_ids = set(objects.keys())
        available_objects = dict(objects)

    # 2. Construir CausalLinks desde relaciones o usar los proporcionados
    links: list[CausalLink] = []
    if relations is not None:
        fvg_by_id = {o.id: o for o in available_objects.values() if o.type is ObjectType.FVG}
        ob_by_id = {o.id: o for o in available_objects.values() if o.type is ObjectType.ORDER_BLOCK}
        try:
            links = relation_links(relations, fvg_by_id, ob_by_id)
        except ValueError as e:
            return _legacy_unvalidated(
                objects_by_id=available_objects,
                break_msg=f"relations no pueden convertirse a CausalLinks: {e}",
            )
    elif causal_links is not None:
        links = list(causal_links)
    else:
        # Derivar enlaces desde parent_object de los objetos
        links = _derive_links_from_objects(available_objects)

    # 3. Validar links (duplicados, etc.) — usa el validador existente
    try:
        links = validate_links(links)
    except ValueError as e:
        return _legacy_unvalidated(
            objects_by_id=available_objects,
            break_msg=f"links inválidos: {e}",
        )

    # 4. Filtrar links para que solo usen objetos disponibles en proyección
    filtered_links: list[CausalLink] = []
    for link in links:
        if link.parent_id not in available_ids:
            continue  # parent no disponible => no incluir (no inventar)
        if link.child_id not in available_ids:
            continue  # child no disponible => no incluir
        filtered_links.append(link)

    # 5. Validar cada link individualmente
    object_map = available_objects
    breaks = []
    orphan_ids: set[str] = set()
    cycle_ids: set[str] = set()
    future_links: set[tuple[str, str]] = set()
    unresolved_ids: set[str] = set()
    temporal_violations: list[str] = []

    for link in filtered_links:
        parent_obj = object_map.get(link.parent_id)
        child_obj = object_map.get(link.child_id)

        # parent inexistente
        if parent_obj is None:
            unresolved_ids.add(link.parent_id)
            breaks.append(f"parent inexistente: {link.parent_id} -> {link.child_id}")
            continue

        # child inexistente
        if child_obj is None:
            unresolved_ids.add(link.child_id)
            breaks.append(f"child inexistente: {link.parent_id} -> {link.child_id}")
            continue

        # self-link
        if link.parent_id == link.child_id:
            breaks.append(f"self-link detectado: {link.parent_id}")
            continue

        # parent futuro del child (mismo TF: bar_index; cross-TF: timestamp)
        if _is_future_link(parent_obj, child_obj, link):
            future_links.add((link.parent_id, link.child_id))
            temporal_violations.append(
                f"future: {link.parent_id}({parent_obj.origin_tf}) -> {link.child_id}({child_obj.origin_tf})"
            )
            continue

        # parent y child deben estar en misma proyección
        if link.parent_id not in available_ids or link.child_id not in available_ids:
            unresolved_ids.add(link.parent_id)
            unresolved_ids.add(link.child_id)
            continue

    # 6. Detectar ciclos con DFS
    adj: dict[str, list[str]] = defaultdict(list)
    for link in filtered_links:
        adj[link.parent_id].append(link.child_id)

    all_node_ids = set(adj.keys()) | {link.child_id for link in filtered_links}
    cycle_nodes = _detect_cycles(adj, all_node_ids)
    if cycle_nodes:
        cycle_ids = set(cycle_nodes)
        breaks.append(f"ciclos detectados: {sorted(cycle_ids)}")

    # 7. Detectar huérfanos: nodos que no son alcanzables desde raíces
    roots = _find_roots(adj, all_node_ids, object_map)
    reachable = _reachable_from_roots(adj, roots)

    for node_id in all_node_ids:
        if node_id not in reachable and node_id not in roots:
            orphan_ids.add(node_id)

    # 8. Determinar hojas
    leaves = _find_leaves(adj, all_node_ids)

    # 9. Calcular profundidad máxima
    depth = _compute_depth(adj, roots)

    # 10. Recuentos por tipo de relación
    relation_counts: dict[str, int] = defaultdict(int)
    for link in filtered_links:
        relation_counts[link.relation] += 1

    # 11. Provenance por TF (acumulado como listas para consistencia con el campo del dataclass)
    provenance_by_tf: dict[str, list[str]] = defaultdict(list)
    _provenance_seen: set[tuple[str, str]] = set()
    for link in filtered_links:
        parent_tf = object_map.get(link.parent_id)
        child_tf = object_map.get(link.child_id)
        if parent_tf:
            key = (parent_tf.origin_tf, link.parent_id)
            if key not in _provenance_seen:
                _provenance_seen.add(key)
                provenance_by_tf[parent_tf.origin_tf].append(link.parent_id)
        if child_tf:
            key = (child_tf.origin_tf, link.child_id)
            if key not in _provenance_seen:
                _provenance_seen.add(key)
                provenance_by_tf[child_tf.origin_tf].append(link.child_id)

    # 12. Determinar estado final
    status = _determine_status(
        breaks=breaks,
        orphan_ids=orphan_ids,
        cycle_ids=cycle_ids,
        future_links=future_links,
        unresolved_ids=unresolved_ids,
        temporal_violations=temporal_violations,
        roots=roots,
        leaves=leaves,
        all_node_ids=all_node_ids,
        object_map=object_map,
        require_all_six_tfs=require_all_six_tfs,
    )

    return HierarchicalLineage(
        status=status,
        links=filtered_links,
        roots=sorted(roots),
        leaves=sorted(leaves),
        depth=depth,
        breaks=sorted(set(breaks)),
        orphan_ids=sorted(orphan_ids),
        cycle_ids=sorted(cycle_ids),
        future_links=sorted(future_links),
        unresolved_ids=sorted(unresolved_ids),
        temporal_violations=temporal_violations,
        relation_counts=dict(relation_counts),
        provenance_by_tf={tf: sorted(ids) for tf, ids in provenance_by_tf.items()},
        objects_by_id=object_map,
    )


# ---------------------------------------------------------------------------
# Derivación de enlaces desde objetos (parent_object y related_objects)
# ---------------------------------------------------------------------------

def _derive_links_from_objects(objects: Mapping[str, MarketObject]) -> list[CausalLink]:
    """Deriva CausalLinks desde parent_object y related_objects."""
    links: list[CausalLink] = []
    for obj in objects.values():
        parent_id = obj.parent_object
        if parent_id and parent_id in objects:
            parent = objects[parent_id]
            link = _make_link(parent, obj, "PARENT_OBJECT")
            if link:
                links.append(link)

        for related_id in obj.related_objects:
            if related_id and related_id in objects and related_id != obj.id:
                related = objects[related_id]
                # Determinar dirección: quién es parent según bar_index/tiempo
                if _is_parent_of(obj, related):
                    link = _make_link(obj, related, "RELATED_OBJECTS")
                else:
                    link = _make_link(related, obj, "RELATED_OBJECTS")
                if link:
                    links.append(link)

    return links


def _make_link(parent: MarketObject, child: MarketObject, relation: str) -> CausalLink | None:
    """Crea un CausalLink si es válido."""
    try:
        return CausalLink(
            parent_id=parent.id,
            child_id=child.id,
            relation=relation,
            parent_bar=parent.bar_index or 0,
            child_bar=child.bar_index or 0,
            parent_time=parent.creation_time or parent.bar_time,
            child_time=child.creation_time or child.bar_time,
        )
    except ValueError:
        return None


def _is_parent_of(a: MarketObject, b: MarketObject) -> bool:
    """Determina si a es ancestro causal de b (por tiempo/bar)."""
    # Mismo TF: bar_index
    if a.origin_tf == b.origin_tf:
        a_bar = a.bar_index or 0
        b_bar = b.bar_index or 0
        return a_bar < b_bar

    # Cross-TF: timestamp
    a_time = a.creation_time or a.bar_time
    b_time = b.creation_time or b.bar_time
    if a_time is None or b_time is None:
        return False

    if isinstance(a_time, datetime) and isinstance(b_time, datetime):
        return a_time < b_time

    # Strings comparables
    try:
        return str(a_time) < str(b_time)
    except TypeError:
        return False


def _is_future_link(parent: MarketObject, child: MarketObject, link: CausalLink) -> bool:
    """Determina si el link viola causalidad (parent futuro del child)."""
    same_tf = parent.origin_tf == child.origin_tf

    if same_tf:
        # Mismo TF: comparar bar_index
        if link.parent_bar > link.child_bar:
            return True
        # Si son iguales, verificar tiempo
        if link.parent_bar == link.child_bar:
            p_time = parent.creation_time or parent.bar_time
            c_time = child.creation_time or child.bar_time
            if p_time is not None and c_time is not None:
                if isinstance(p_time, datetime) and isinstance(c_time, datetime):
                    if p_time > c_time:
                        return True
                elif str(p_time) > str(c_time):
                    return True
        return False
    else:
        # Cross-TF: timestamp UTC (nunca bar_index entre temporalidades distintas)
        p_time = parent.creation_time or parent.bar_time
        c_time = child.creation_time or child.bar_time
        if p_time is None or c_time is None:
            return False  # No hay tiempo => no se puede validar; no marcar como future

        if isinstance(p_time, datetime) and isinstance(c_time, datetime):
            return p_time > c_time
        try:
            return str(p_time) > str(c_time)
        except TypeError:
            return False


# ---------------------------------------------------------------------------
# Detección de ciclos (DFS)
# ---------------------------------------------------------------------------

def _detect_cycles(adj: dict[str, list[str]], all_nodes: set[str]) -> list[str]:
    """DFS para detectar ciclos. Devuelve lista de nodos en ciclo."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in all_nodes}
    cycle_nodes: list[str] = []

    def dfs(node: str, path: list[str]) -> bool:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                # Ciclo encontrado: extraer nodos del ciclo
                idx = path.index(neighbor)
                cycle_nodes.extend(path[idx:])
                return True
            if color[neighbor] == WHITE:
                if dfs(neighbor, path):
                    return True
        path.pop()
        color[node] = BLACK
        return False

    for node in sorted(all_nodes):
        if color[node] == WHITE:
            dfs(node, [])

    return list(set(cycle_nodes))


# ---------------------------------------------------------------------------
# Raíces, hojas, profundidad
# ---------------------------------------------------------------------------

def _find_roots(adj: dict[str, list[str]], all_nodes: set[str], object_map: dict[str, MarketObject]) -> set[str]:
    """Encuentra raíces: nodos sin padre conocido en el grafo."""
    has_parent: set[str] = set()
    for parent_id, children in adj.items():
        for child_id in children:
            has_parent.add(child_id)

    roots: set[str] = set()
    for node_id in all_nodes:
        obj = object_map.get(node_id)
        if obj and obj.parent_object:
            # Nodo con parent_object: no es raíz si el parent está en el grafo
            if obj.parent_object in all_nodes:
                has_parent.add(node_id)
            else:
                # Parent no está en el grafo: puede ser raíz externa
                pass
        if node_id not in has_parent:
            roots.add(node_id)

    return roots


def _reachable_from_roots(adj: dict[str, list[str]], roots: set[str]) -> set[str]:
    """BFS desde raíces para encontrar nodos alcanzables."""
    reachable: set[str] = set()
    queue: list[str] = list(roots)

    while queue:
        node = queue.pop(0)
        if node in reachable:
            continue
        reachable.add(node)
        for child in adj.get(node, []):
            if child not in reachable:
                queue.append(child)

    return reachable


def _find_leaves(adj: dict[str, list[str]], all_nodes: set[str]) -> set[str]:
    """Nodos que no tienen hijos en el grafo."""
    has_children: set[str] = set()
    for parent_id, children in adj.items():
        for child_id in children:
            has_children.add(parent_id)
    return all_nodes - has_children


def _compute_depth(adj: dict[str, list[str]], roots: set[str]) -> int:
    """Profundidad máxima del DAG desde raíces."""
    if not roots:
        return 0

    # Topological order
    in_degree: dict[str, int] = defaultdict(int)
    all_nodes: set[str] = set()
    for parent_id, children in adj.items():
        all_nodes.add(parent_id)
        for child_id in children:
            all_nodes.add(child_id)
            in_degree[child_id] += 1

    # Inicializar nodos sin incoming edges
    queue: list[str] = [n for n in all_nodes if in_degree[n] == 0]
    depth_map: dict[str, int] = {n: 0 for n in queue}

    max_depth = 0
    while queue:
        node = queue.pop(0)
        current_depth = depth_map.get(node, 0)
        max_depth = max(max_depth, current_depth)
        for child_id in adj.get(node, []):
            in_degree[child_id] -= 1
            new_depth = current_depth + 1
            if child_id not in depth_map or depth_map[child_id] < new_depth:
                depth_map[child_id] = new_depth
            if in_degree[child_id] == 0:
                queue.append(child_id)

    return max_depth


# ---------------------------------------------------------------------------
# Determinación de estado
# ---------------------------------------------------------------------------

def _determine_status(
    *,
    breaks: list[str],
    orphan_ids: set[str],
    cycle_ids: set[str],
    future_links: set[tuple[str, str]],
    unresolved_ids: set[str],
    temporal_violations: list[str],
    roots: set[str],
    leaves: set[str],
    all_node_ids: set[str],
    object_map: dict[str, MarketObject],
    require_all_six_tfs: bool,
) -> LineageStatus:
    """Determinar el estado del lineage según las reglas fail-closed."""
    # Prioridad: ciclo > futures > unresolved > orphans > breaks > incompleto

    if cycle_ids:
        return LineageStatus.CYCLE

    if future_links or temporal_violations:
        return LineageStatus.FUTURE

    if unresolved_ids:
        return LineageStatus.UNRESOLVED

    if orphan_ids:
        return LineageStatus.ORPHAN

    if breaks:
        return LineageStatus.INVALID

    # Verificar que no haya nodos huérfanos (sin conexión al grafo)
    if all_node_ids and not roots:
        return LineageStatus.ORPHAN

    # Verificar cobertura de 6 TFs
    if require_all_six_tfs:
        present_tfs = set()
        for obj in object_map.values():
            present_tfs.add(obj.origin_tf)
        present_ordered = [tf for tf in SIX_TFS_ORDERED if tf in present_tfs]

        # Si solo H4 y M15 están presentes (sin D1, H1, M5, M1), es legacy
        if present_tfs <= {"H4", "M15"}:
            return LineageStatus.LEGACY_UNVALIDATED

        # Si faltan TFs requeridos pero hay más de solo H4+M15
        if len(present_ordered) < len(SIX_TFS_ORDERED):
            # Verificar si hay al menos POI en HTF + refinamiento LTF
            has_poi_htf = any(
                obj.role is Role.POI and obj.origin_tf in POI_TFS
                for obj in object_map.values()
            )
            has_refinement = any(
                obj.role is Role.REFINEMENT and obj.origin_tf in REFINEMENT_TFS
                for obj in object_map.values()
            )
            if has_poi_htf and has_refinement:
                return LineageStatus.INVALID  # Incompleto pero con estructura

    # Si no hay objetos, es INCOMPLETE
    if not all_node_ids:
        return LineageStatus.INCOMPLETE

    return LineageStatus.VALID


def _legacy_unvalidated(*, objects_by_id: dict[str, MarketObject], break_msg: str) -> HierarchicalLineage:
    """Estado LEGACY_UNVALIDATED para casos donde no se puede validar."""
    return HierarchicalLineage(
        status=LineageStatus.LEGACY_UNVALIDATED,
        breaks=[break_msg],
        objects_by_id=objects_by_id,
    )


# ---------------------------------------------------------------------------
# Serialización / round-trip
# ---------------------------------------------------------------------------

def lineage_to_dict(lineage: HierarchicalLineage) -> dict[str, Any]:
    """Serializa el lineage a dict JSON-compatible."""
    return {
        "status": lineage.status.value,
        "links": [
            {
                "parent_id": link.parent_id,
                "child_id": link.child_id,
                "relation": link.relation,
                "parent_bar": link.parent_bar,
                "child_bar": link.child_bar,
                "parent_time": _serialize_time(link.parent_time),
                "child_time": _serialize_time(link.child_time),
            }
            for link in lineage.links
        ],
        "roots": lineage.roots,
        "leaves": lineage.leaves,
        "depth": lineage.depth,
        "breaks": lineage.breaks,
        "orphan_ids": lineage.orphan_ids,
        "cycle_ids": lineage.cycle_ids,
        "future_links": [list(fl) for fl in lineage.future_links],
        "unresolved_ids": lineage.unresolved_ids,
        "temporal_violations": lineage.temporal_violations,
        "relation_counts": lineage.relation_counts,
        "provenance_by_tf": lineage.provenance_by_tf,
        "objects_by_id": {
            obj_id: obj.to_dict() for obj_id, obj in lineage.objects_by_id.items()
        },
    }


def lineage_from_dict(data: dict[str, Any]) -> HierarchicalLineage:
    """Deserializa un dict JSON-compatible a HierarchicalLineage."""
    links = []
    for link_data in data.get("links", []):
        try:
            link = CausalLink(
                parent_id=link_data["parent_id"],
                child_id=link_data["child_id"],
                relation=link_data["relation"],
                parent_bar=link_data["parent_bar"],
                child_bar=link_data["child_bar"],
                parent_time=_parse_time(link_data.get("parent_time")),
                child_time=_parse_time(link_data.get("child_time")),
            )
            links.append(link)
        except (KeyError, ValueError):
            continue

    objects_by_id = {}
    for obj_data in data.get("objects_by_id", {}).values():
        try:
            objects_by_id[obj_data["id"]] = MarketObject.from_dict(obj_data)
        except (KeyError, ValueError, TypeError):
            continue

    # Validar links deserializados
    try:
        links = validate_links(links)
    except ValueError:
        links = []

    status_str = data.get("status", LineageStatus.INCOMPLETE.value)
    try:
        status = LineageStatus(status_str)
    except ValueError:
        status = LineageStatus.INCOMPLETE

    return HierarchicalLineage(
        status=status,
        links=links,
        roots=data.get("roots", []),
        leaves=data.get("leaves", []),
        depth=data.get("depth", 0),
        breaks=data.get("breaks", []),
        orphan_ids=data.get("orphan_ids", []),
        cycle_ids=data.get("cycle_ids", []),
        future_links=[tuple(fl) for fl in data.get("future_links", [])],
        unresolved_ids=data.get("unresolved_ids", []),
        temporal_violations=data.get("temporal_violations", []),
        relation_counts=data.get("relation_counts", {}),
        provenance_by_tf=data.get("provenance_by_tf", {}),
        objects_by_id=objects_by_id,
    )


def _serialize_time(t: Any) -> str | None:
    """Serializa tiempo a string ISO."""
    if t is None:
        return None
    if isinstance(t, datetime):
        return t.isoformat()
    return str(t)


def _parse_time(s: Any) -> Any:
    """Parsea string ISO a datetime si es posible."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return s
    return s


# ---------------------------------------------------------------------------
# Validación de lineage a tiempo T
# ---------------------------------------------------------------------------

def validate_lineage_at(
    objects: Mapping[str, MarketObject],
    *,
    causal_links: Iterable[CausalLink] | None = None,
    relations: Iterable[FVGOBRelation] | None = None,
    decision_time: Any = None,
    market_state: Any | None = None,
    require_all_six_tfs: bool = False,
) -> HierarchicalLineage:
    """Valida el lineage a tiempo T usando proyección point-in-time.

    Si market_state se proporciona, se usa su proyección_at(decision_time)
    para obtener los objetos disponibles en T.
    """
    # Determinar proyección
    if market_state is not None and decision_time is not None:
        try:
            projection = market_state.projection_at(decision_time)
        except Exception:
            projection = None
    else:
        projection = None

    if projection is None:
        projection = objects

    return build_hierarchical_lineage(
        dict(projection) if projection else dict(objects),
        relations=relations,
        causal_links=causal_links,
        projection=projection,
        decision_time=decision_time,
        require_all_six_tfs=require_all_six_tfs,
    )


# ---------------------------------------------------------------------------
# Integración con el motor diario
# ---------------------------------------------------------------------------

def lineage_result_to_snapshot_summary(lineage: HierarchicalLineage) -> dict[str, Any]:
    """Convierte un HierarchicalLineage a resumen para snapshot del motor diario."""
    return {
        "status": lineage.status.value,
        "lineage_validated": lineage.status == LineageStatus.VALID,
        "roots": lineage.roots,
        "leaves": lineage.leaves,
        "depth": lineage.depth,
        "breaks": lineage.breaks,
        "orphan_ids": lineage.orphan_ids,
        "cycle_ids": lineage.cycle_ids,
        "future_links": [list(fl) for fl in lineage.future_links],
        "unresolved_ids": lineage.unresolved_ids,
        "temporal_violations": lineage.temporal_violations,
        "relation_counts": lineage.relation_counts,
        "provenance_by_tf": lineage.provenance_by_tf,
        "tfs_present": sorted(lineage.provenance_by_tf.keys()),
        "six_tfs_complete": (
            lineage.status == LineageStatus.VALID
            and set(lineage.provenance_by_tf.keys()) == set(SIX_TFS_ORDERED)
        ),
    }


# ---------------------------------------------------------------------------
# Verificación de lineage incompleto para gate fail-closed
# ---------------------------------------------------------------------------

def lineage_is_complete_enough_for_publication(lineage: HierarchicalLineage) -> bool:
    """Determina si el lineage es suficiente para publicar una señal.

    Fail-closed: si el lineage no es VALID con estructura completa,
    no se publica como válido.
    """
    if lineage.status != LineageStatus.VALID:
        return False

    # Debe tener estructura mínima: POI + refinamiento
    has_poi = any(
        obj.role is Role.POI
        for obj in lineage.objects_by_id.values()
    )
    has_refinement = any(
        obj.role is Role.REFINEMENT
        for obj in lineage.objects_by_id.values()
    )
    if not (has_poi and has_refinement):
        return False

    # Debe tener al menos una relación válida
    if not lineage.links:
        return False

    return True
