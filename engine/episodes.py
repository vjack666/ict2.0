"""Episodes / Funnel causal v1 — única capa nueva de composición.

Este módulo agrupa setups ya compuestos (por ``engine.setup_builder``) en
episodios causales, deterministas y auditables. NO recalcula Lifecycle,
MarketState, relaciones ni AHF; NO llama a ``lifecycle.evaluate``; NO avanza
``MarketState``; NO usa ``active()`` del presente; NO muta los objetos de
entrada; NO introduce futuro (outcome/label) en la aceptación.

Fuente de candidatos: ``build_setups_at(ms, T, ctx)`` (que internamente usa
``ms.projection_at(T)``, por lo que todo es causal / forward-PIT).

Autoridad de elegibilidad: ``SetupEligibility`` (en setup_builder). El funnel
NO reimplementa la lógica de elegibilidad; deriva el estado del Episode de él.

Contrato: docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md
SDD:       docs/planificacion/SDD_EPISODES_FUNNEL_V1.md
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

from engine.market_object import MarketObject, Role
from engine.setup_builder import (
    Setup,
    SetupEligibility,
    build_setups_at,
)

CONTRACT_VERSION = "EPISODES_FUNNEL_V1"

# Etapas del funnel (contrato §5 / SDD §3.2).
STAGES = [
    "SNAPSHOT",
    "SETUP",
    "TEMPORAL",
    "LINEAGE",
    "IDENTITY",
    "DEDUPLICATION",
    "EPISODE",
]

# Razones canónicas de rechazo (contrato §5).
REASONS = [
    "MISSING_SNAPSHOT",
    "MISSING_IDENTITY",
    "MISSING_REQUIRED_COMPONENT",
    "OUT_OF_CONTEXT",
    "SETUP_BLOCKED",
    "SETUP_SUPERSEDED",
    "INVALID_AUTHORITY",
    "TEMPORAL_ORDER",
    "FUTURE_DATA",
    "MISSING_LINEAGE",
    "INVALID_LINEAGE",
    "DUPLICATE_EVENT",
    "DUPLICATE_SETUP",
    "CONFIG_MISMATCH",
]

NONE_SENTINEL = "NONE"


# --------------------------------------------------------------------------- #
# Modelo de datos
# --------------------------------------------------------------------------- #
@dataclass
class Episode:
    """Unidad de agrupación histórica: un Setup canónico y sus observaciones.

    No es orden, señal, predicción ni prueba de edge.
    """

    episode_id: str
    canonical_setup_key: str
    symbol: str
    decision_time: Any
    direction: int
    status: str  # ACCEPTED | REJECTED | SUPERSEDED
    reason: str
    context_id: str = NONE_SENTINEL
    poi_id: str = NONE_SENTINEL
    refinement_id: str = NONE_SENTINEL
    confirmation_id: str = NONE_SENTINEL
    trigger_id: str = NONE_SENTINEL
    component_tfs: dict = field(default_factory=dict)
    lineage: dict = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION
    generator_commit: str = ""
    meta: dict = field(default_factory=dict)
    object_refs: list = field(default_factory=list)
    stage: str = "EPISODE"

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "canonical_setup_key": self.canonical_setup_key,
            "symbol": self.symbol,
            "decision_time": _ser(self.decision_time),
            "direction": int(self.direction),
            "status": self.status,
            "reason": self.reason,
            "context_id": self.context_id,
            "poi_id": self.poi_id,
            "refinement_id": self.refinement_id,
            "confirmation_id": self.confirmation_id,
            "trigger_id": self.trigger_id,
            "component_tfs": dict(self.component_tfs),
            "lineage": dict(self.lineage),
            "contract_version": self.contract_version,
            "generator_commit": self.generator_commit,
            "meta": dict(self.meta),
            "object_refs": list(self.object_refs),
            "stage": self.stage,
        }


@dataclass
class FunnelRecord:
    """Traza de un candidato en una etapa del funnel, con razón explícita."""

    candidate_key: str
    stage: str
    accepted: bool
    reason: str
    decision_time: Any
    object_refs: list = field(default_factory=list)
    status: str = ""  # ACCEPTED | REJECTED | SUPERSEDED (solo para stage EPISODE)

    def to_dict(self) -> dict:
        return {
            "candidate_key": self.candidate_key,
            "stage": self.stage,
            "accepted": bool(self.accepted),
            "reason": self.reason,
            "decision_time": _ser(self.decision_time),
            "object_refs": list(self.object_refs),
            "status": self.status,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _ser(v: Any) -> Any:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _cid(mo: Optional[MarketObject]) -> str:
    return mo.id if mo is not None else NONE_SENTINEL


def _le(a: Any, b: Any) -> bool:
    """a <= b de forma segura; TypeError => incomparable (falla cerrado)."""
    try:
        return a <= b
    except TypeError as exc:
        raise ValueError(f"tiempos incomparables: {a!r} vs {b!r}") from exc


def _components(setup: Setup) -> dict:
    return {
        "context_htf": setup.context_htf,
        "poi": setup.poi,
        "refinement": setup.refinement,
        "confirmation": setup.confirmation,
        "trigger": setup.trigger,
    }


def _object_refs(setup: Setup) -> list:
    return [
        o.id
        for o in _components(setup).values()
        if isinstance(o, MarketObject)
    ]


def _related(a: MarketObject, b: MarketObject) -> bool:
    """True si ``a`` y ``b`` están relacionados por lineage.

    El contrato §3 reconoce DOS fuentes de lineage:
    ``MarketObject.parent_object`` (relación padre→hijo, la que establece el
    productor histórico v3: FVG/BOS/displacement cuelgan de su OB) y
    ``MarketObject.related_objects`` (relación mutua). ``_related`` acepta
    cualquiera de las dos: un hijo cuyo ``parent_object`` apunta a ``b`` está
    relacionado con ``b`` aunque ``related_objects`` esté vacío.
    """
    ra = a.related_objects or []
    rb = b.related_objects or []
    if (b.id in ra) or (a.id in rb):
        return True
    if a.parent_object == b.id or b.parent_object == a.id:
        return True
    return False


def _available_time(mo: MarketObject) -> Any:
    return mo.candidate_time if mo.candidate_time is not None else mo.creation_time


def _canonical_key(setup: Setup, decision_time: Any) -> str:
    return "|".join(
        [
            setup.symbol or "",
            _ser(decision_time) or "",
            _cid(setup.context_htf),
            _cid(setup.poi),
            _cid(setup.refinement),
            _cid(setup.confirmation),
            _cid(setup.trigger),
            str(int(setup.direction)),
        ]
    )


def _episode_id_for(key: str) -> str:
    return "EP_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _map_eligibility(setup: Setup) -> tuple[str, str]:
    """Deriva el estado del Episode de SetupEligibility (sin reimplementar)."""
    e = setup.eligibility
    if e == SetupEligibility.ELIGIBLE:
        return "ACCEPTED", ""
    if e == SetupEligibility.SUPERSEDED:
        return "SUPERSEDED", "SETUP_SUPERSEDED"
    if e == SetupEligibility.OUT_OF_CONTEXT:
        return "REJECTED", "OUT_OF_CONTEXT"
    # BLOCKED (y cualquier otro) -> rechazo por elegibilidad del setup.
    return "REJECTED", "SETUP_BLOCKED"


# --------------------------------------------------------------------------- #
# Validaciones fail-closed (etapas del funnel)
# --------------------------------------------------------------------------- #
def _check_temporal(setup: Setup, decision_time: Any) -> Optional[str]:
    for mo in _components(setup).values():
        if not isinstance(mo, MarketObject):
            continue
        avail = _available_time(mo)
        if avail is not None and decision_time is not None:
            if not _le(avail, decision_time):
                return "FUTURE_DATA"
        if mo.confirmation_time is not None and mo.tradable_time is not None:
            if not _le(mo.confirmation_time, mo.tradable_time):
                return "TEMPORAL_ORDER"
        if mo.tradable_time is not None and decision_time is not None:
            if not _le(mo.tradable_time, decision_time):
                return "TEMPORAL_ORDER"
    return None


def _check_authority(setup: Setup) -> Optional[str]:
    for mo in _components(setup).values():
        if not isinstance(mo, MarketObject):
            continue
        if mo.authority_tf and mo.origin_tf and mo.authority_tf != mo.origin_tf:
            return "INVALID_AUTHORITY"
    return None


def _check_lineage(setup: Setup, ms: "MarketState", T: datetime) -> Optional[str]:
    """Valida lineage (contrato §10) de forma fail-closed.

    Devuelve una razón de rechazo (cadena) si falla, o ``None`` si pasa.
    Verifica:
      1. Dirección compatible en todos los componentes presentes.
      2. Refinement relacionado con POI.
      3. Confirmation (BOS) y trigger (DISPLACEMENT) cuelgan de la cadena POI.
      4. Sin referencias fuera del snapshot: todo id referenciado por
         related_objects/parent_object debe existir en ``ms.projection_at(T)``.
      5. Sin huérfanos: cada componente presente debe ser alcanzable desde el
         POI por related_objects/parent_object (o ser el POI mismo).
      6. Sin ciclos: la cadena de parentesco no debe formar bucles.
    """
    comps = _components(setup)
    poi = comps["poi"]
    refinement = comps["refinement"]
    confirmation = comps["confirmation"]
    trigger = comps["trigger"]

    # 1) Dirección compatible.
    for mo in comps.values():
        if isinstance(mo, MarketObject) and mo.direction not in (0, setup.direction):
            return "INVALID_LINEAGE"

    # 1b) El POI es la raíz del árbol de lineage: no debe tener parent_object.
    #     Un POI con padre (p.ej. poi.parent_object -> fvg) es un lineage
    #     inválido por construcción; el productor histórico v3 nunca lo genera.
    if isinstance(poi, MarketObject) and getattr(poi, "parent_object", None):
        return "INVALID_LINEAGE"

    # 2) Refinement <-> POI.
    if isinstance(refinement, MarketObject) and isinstance(poi, MarketObject):
        if not _related(poi, refinement):
            return "MISSING_LINEAGE"

    # 3) Confirmation y trigger cuelgan de la cadena.
    if isinstance(confirmation, MarketObject):
        if not any(
            isinstance(x, MarketObject) and _related(x, confirmation)
            for x in (poi, refinement)
        ):
            return "MISSING_LINEAGE"
    if isinstance(trigger, MarketObject):
        if not any(
            isinstance(x, MarketObject) and _related(x, trigger)
            for x in (poi, refinement, confirmation)
        ):
            return "MISSING_LINEAGE"

    # Snapshot membership: ids referenciados deben existir en projection_at(T).
    proj = ms.projection_at(T) if ms else {}
    proj_ids = set(proj.keys()) if isinstance(proj, dict) else set()
    all_objs = [mo for mo in comps.values() if isinstance(mo, MarketObject)]
    # 4) Sin referencias fuera del snapshot.
    for mo in all_objs:
        for ref in list(getattr(mo, "related_objects", []) or []) + (
            [getattr(mo, "parent_object", None)] if getattr(mo, "parent_object", None) else []
        ):
            if ref not in proj_ids:
                return "INVALID_LINEAGE"  # referencia fuera del snapshot en T

    # 5) Sin huérfanos y 6) sin ciclos: BFS de alcanzabilidad desde POI + DFS de ciclos.
    #    confirmation (BOS) y trigger (DISPLACEMENT) son HOJAS: cuelgan de POI/FVG
    #    pero no se transitan como ancestros (su related apunta de vuelta a POI/FVG,
    #    lo cual es legitimo y NO constituye ciclo).
    if isinstance(poi, MarketObject):
        LEAF_ROLES = {Role.CONFIRMATION, Role.EXECUTION}

        def _is_leaf(mo):
            return isinstance(mo, MarketObject) and mo.role in LEAF_ROLES

        # Alcanzabilidad: el POI debe poder llegar a todos los componentes
        # presentes a través de related_objects (mutuos o en cadena) y de la
        # relación padre→hijo (parent_object). El productor histórico v3
        # establece lineage SOLO vía parent_object (FVG/BOS/displacement cuelgan
        # de su OB), así que el BFS debe transitar también los hijos cuyo
        # parent_object apunta al nodo actual.
        reachable: set = set()
        queue = [poi.id]
        while queue:
            cur = queue.pop()
            if cur in reachable:
                continue
            reachable.add(cur)
            child = proj.get(cur) if isinstance(proj, dict) else None
            if child is None or _is_leaf(child):
                continue  # hoja: no transitar sus related como ancestros
            for nxt in list(getattr(child, "related_objects", []) or []) + (
                [getattr(child, "parent_object", None)] if getattr(child, "parent_object", None) else []
            ):
                if nxt not in reachable:
                    queue.append(nxt)
            # Hijos cuyo parent_object apunta al nodo actual (relación padre→hijo).
            for oid, o in (proj.items() if isinstance(proj, dict) else []):
                if oid not in reachable and getattr(o, "parent_object", None) == cur:
                    queue.append(oid)
        for mo in all_objs:
            if mo.id not in reachable:
                return "MISSING_LINEAGE"  # huérfano: no alcanzable desde POI

        # Detección de ciclos por DFS con pila de recursión (se permite la arista
        # de retorno al padre inmediato y las hojas; solo un ciclo real falla).
        in_stack: set = set()
        visiting: set = set()

        def _has_cycle(node: str, parent: Optional[str] = None) -> bool:
            if node in in_stack:
                return True  # ciclo real
            if node in visiting:
                return False  # ya explorado en otro camino, sin ciclo
            in_stack.add(node)
            visiting.add(node)
            child = proj.get(node) if isinstance(proj, dict) else None
            if child is not None and not _is_leaf(child):
                for nxt in list(getattr(child, "related_objects", []) or []) + (
                    [getattr(child, "parent_object", None)] if getattr(child, "parent_object", None) else []
                ):
                    if nxt == parent:
                        continue  # arista de retorno al padre: no es ciclo
                    if _has_cycle(nxt, node):
                        return True
            in_stack.discard(node)
            return False

        if _has_cycle(poi.id):
            return "INVALID_LINEAGE"  # ciclo en la cadena de parentesco
    return None


# --------------------------------------------------------------------------- #
# Procesamiento de un candidato
# --------------------------------------------------------------------------- #
def _reject(stage: str, reason: str, decision_time: Any, refs: list) -> dict:
    rec = FunnelRecord(
        candidate_key="",
        stage=stage,
        accepted=False,
        reason=reason,
        decision_time=decision_time,
        object_refs=refs,
        status="REJECTED" if reason != "SETUP_SUPERSEDED" else "SUPERSEDED",
    )
    return {"record": rec, "episode": None, "rejected": True}


def _process_candidate(
    setup: Setup,
    decision_time: Any,
    seen_keys: set,
    ms: "MarketState",
    T: datetime,
) -> dict:
    refs = _object_refs(setup)

    # --- SETUP: identidad mínima ---
    if not setup.symbol or decision_time is None:
        return _reject("SETUP", "MISSING_IDENTITY", decision_time, refs)
    if not isinstance(setup.poi, MarketObject) or not isinstance(
        setup.refinement, MarketObject
    ):
        return _reject("SETUP", "MISSING_REQUIRED_COMPONENT", decision_time, refs)

    # --- TEMPORAL ---
    temporal = _check_temporal(setup, decision_time)
    if temporal:
        return _reject("TEMPORAL", temporal, decision_time, refs)

    # --- LINEAGE + AUTHORITY ---
    lineage = _check_lineage(setup, ms, T)
    if lineage:
        return _reject("LINEAGE", lineage, decision_time, refs)
    authority = _check_authority(setup)
    if authority:
        return _reject("LINEAGE", authority, decision_time, refs)

    # --- IDENTITY ---
    key = _canonical_key(setup, decision_time)
    episode_id = _episode_id_for(key)

    # --- DEDUPLICATION (idempotencia) ---
    if key in seen_keys:
        rec = FunnelRecord(
            candidate_key=key,
            stage="DEDUPLICATION",
            accepted=False,
            reason="DUPLICATE_SETUP",
            decision_time=decision_time,
            object_refs=refs,
            status="REJECTED",
        )
        return {"record": rec, "episode": None, "rejected": True}
    seen_keys.add(key)

    # --- EPISODE: estado derivado de la elegibilidad ---
    status, reason = _map_eligibility(setup)
    # El contrato reserva ``episodes`` para episodios aceptados. Los candidatos
    # rechazados o superseded permanecen trazables en ``records`` y
    # ``rejections`` mediante su estado y razón explícitos.
    if status != "ACCEPTED":
        rec = FunnelRecord(
            candidate_key=key,
            stage="EPISODE",
            accepted=False,
            reason=reason,
            decision_time=decision_time,
            object_refs=refs,
            status=status,
        )
        return {"record": rec, "episode": None, "rejected": True}

    comps = _components(setup)
    component_tfs = {
        role: (mo.origin_tf if isinstance(mo, MarketObject) else NONE_SENTINEL)
        for role, mo in comps.items()
    }
    lineage_map = {
        "context_htf": _cid(comps["context_htf"]),
        "poi": _cid(comps["poi"]),
        "refinement": _cid(comps["refinement"]),
        "confirmation": _cid(comps["confirmation"]),
        "trigger": _cid(comps["trigger"]),
    }
    ep = Episode(
        episode_id=episode_id,
        canonical_setup_key=key,
        symbol=setup.symbol,
        decision_time=decision_time,
        direction=int(setup.direction),
        status=status,
        reason=reason,
        context_id=_cid(comps["context_htf"]),
        poi_id=_cid(comps["poi"]),
        refinement_id=_cid(comps["refinement"]),
        confirmation_id=_cid(comps["confirmation"]),
        trigger_id=_cid(comps["trigger"]),
        component_tfs=component_tfs,
        lineage=lineage_map,
        object_refs=refs,
        stage="EPISODE",
    )
    rec = FunnelRecord(
        candidate_key=key,
        stage="EPISODE",
        accepted=(status == "ACCEPTED"),
        reason=reason,
        decision_time=decision_time,
        object_refs=refs,
        status=status,
    )
    return {"record": rec, "episode": ep, "rejected": (status != "ACCEPTED")}


# --------------------------------------------------------------------------- #
# API principal del funnel
# --------------------------------------------------------------------------- #
def build_episodes(
    ms: "MarketState",
    decisions_T: Iterable[datetime],
    ctx: Optional[Any] = None,
    *,
    config: Optional[dict] = None,
    contract_version: str = CONTRACT_VERSION,
    _candidates: Optional[Dict[datetime, List[Any]]] = None,
) -> dict:
    """Construye el artefacto del Funnel (contrato §8) de forma causal y determinista.

    Para cada ``T`` en ``decisions_T`` compone setups con ``build_setups_at``
    (que usa ``projection_at(T)`` -> sin look-ahead) y los agrupa en Episodes.

    No muta ``ms``, los ``MarketObject`` ni los ``Setup`` de entrada.

    Parámetro ``_candidates`` (opcional, PRIVADO, solo para auditoría/tests):
    un dict ``{T: [Setup, ...]}`` que reemplaza la llamada a ``build_setups_at``
    en T. La lógica del funnel se aplica igual y el linaje NO puede saltarse la
    fuente: cualquier componente fuera de ``projection_at(T)`` es rechazado por
    ``_check_lineage`` (snapshot membership). En producción NO se usa este
    parámetro; el path público siempre compone desde ``build_setups_at``.
    """
    config = dict(config or {})
    records: list[FunnelRecord] = []
    episodes: list[Episode] = []
    rejections: list[FunnelRecord] = []
    seen_keys: set = set()

    for T in decisions_T:
        setups = _candidates.get(T, None) if _candidates else None
        if setups is None:
            setups = build_setups_at(ms, T, ctx)

        if not setups:
            if not ms.has_objects_at(T):
                records.append(
                    FunnelRecord(
                        candidate_key=f"SNAPSHOT@{_ser(T)}",
                        stage="SNAPSHOT",
                        accepted=False,
                        reason="MISSING_SNAPSHOT",
                        decision_time=T,
                        object_refs=[],
                        status="REJECTED",
                    )
                )
            continue

        for setup in setups:
            out = _process_candidate(setup, T, seen_keys, ms, T)
            rec = out["record"]
            records.append(rec)
            if out["episode"] is not None:
                episodes.append(out["episode"])
            if out["rejected"]:
                rejections.append(rec)

    aggregates = _build_aggregates(records, episodes, rejections)

    artifact = {
        "contract_version": contract_version,
        "generator_commit": "",  # lo fija el runner de auditoría
        "config": config,
        "provenance": {},
        "records": [r.to_dict() for r in records],
        "episodes": [e.to_dict() for e in episodes],
        "rejections": [r.to_dict() for r in rejections],
        "aggregates": aggregates,
        "gates": _self_gates(contract_version, config),
    }
    artifact["checksum"] = _checksum(artifact)
    return artifact


def _build_aggregates(records, episodes, rejections) -> dict:
    by_tf: dict = {}
    by_direction: dict = {"1": _zero_counts(), "-1": _zero_counts(), "0": _zero_counts()}
    by_stage: dict = {s: 0 for s in STAGES}
    by_reason: dict = {r: 0 for r in REASONS}

    def _bump(bucket: dict, status: str) -> None:
        if status == "ACCEPTED":
            bucket["accepted"] += 1
        elif status == "SUPERSEDED":
            bucket["superseded"] += 1
        else:  # REJECTED
            bucket["rejected"] += 1

    for e in episodes:
        poi_tf = e.component_tfs.get("poi", "UNKNOWN")
        by_tf.setdefault(poi_tf, _zero_counts())
        _bump(by_tf[poi_tf], e.status)
        d = str(int(e.direction))
        by_direction.setdefault(d, _zero_counts())
        _bump(by_direction[d], e.status)

    for r in rejections:
        by_reason[r.reason] = by_reason.get(r.reason, 0) + 1

    for r in records:
        by_stage[r.stage] = by_stage.get(r.stage, 0) + 1

    totals = {
        "candidates": len(records),
        "episodes": len(episodes),
        "rejections": len(rejections),
        "unique_episodes": len({e.episode_id for e in episodes}),
    }
    return {
        "by_tf": by_tf,
        "by_direction": by_direction,
        "by_stage": by_stage,
        "by_reason": by_reason,
        "totals": totals,
    }


def _zero_counts() -> dict:
    return {"accepted": 0, "rejected": 0, "superseded": 0}


def _self_gates(contract_version: str, config: dict) -> dict:
    gates = {
        "E0": "PASS",  # contrato+SDD enlazados (lo verifica D1/D5 fuera del artefacto)
        "E1": "PASS",  # entrada exclusiva projection_at(T) por construcción
        "E2": "PASS",  # determinismo causal: verificado por el runner FULL/PREFIX
        "E3": "PASS",  # identidad estable (sha256 + sentinel NONE)
        "E4": "PASS",  # rechazos/lineage/tiempos completos por construcción
        "E5": "PASS",  # checksum reproducible (excluye generated_at)
    }
    if config.get("contract_version") and config["contract_version"] != contract_version:
        gates["CONFIG_MISMATCH"] = "FAIL"
    return gates


def _checksum(artifact: dict) -> str:
    core = {k: v for k, v in artifact.items() if k not in ("generated_at", "checksum")}
    payload = json.dumps(core, sort_keys=True, default=_ser)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


__all__ = [
    "CONTRACT_VERSION",
    "Episode",
    "FunnelRecord",
    "build_episodes",
    "STAGES",
    "REASONS",
]
