"""Modelo de datos del Setup Builder (SDD §13.2).

Este módulo define ÚNICAMENTE la entidad de datos ``Setup`` y su estado de
elegibilidad ``SetupEligibility``. NO contiene lógica de composición: la
construcción de un setup a partir de MarketObjects (contexto, POI,
refinamiento, confirmación, trigger) la realiza otro agente / módulo.

Invariantes del modelo (ver brief de Agente 1):
- El ``Setup`` NO altera ``object_state`` de ningún ``MarketObject`` que
  referencia; solo lectura. La línea de linaje (``used_by_setup``) vive en
  ``POI.meta``, no en el ``Setup``.
- Serialización JSON-safe con ``to_dict`` / ``from_dict`` y un
  ``_normalize_meta`` idéntico en espíritu al de ``engine.market_object``.
- No importa ``backtest/``; no toca ``lifecycle.py`` ni ``market_state.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
import uuid

from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.relations import relate_fvg_ob

if TYPE_CHECKING:  # evita acoplar en runtime con market_state (regla de arquitectura)
    from engine.market_state import MarketState


class SetupEligibility(str, Enum):
    """Estado de elegibilidad de un setup compuesto.

    Es un ``str`` Enum para que su valor serialice directamente a JSON y sea
    legible en la bitácora / trazabilidad.
    """

    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    OUT_OF_CONTEXT = "OUT_OF_CONTEXT"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class Setup:
    """Entidad de datos de un setup ICT/SMC ya compuesto.

    El modelo es una instantánea inmutable de la intención de operación:
    referencia los MarketObjects que la componen (contexto HTF, POI,
    refinamiento, confirmación y trigger) y declara su elegibilidad.

    No se incluye ``used_by_setup`` como campo propio: la línea de linaje
    vive en ``POI.meta['used_by_setup']`` (lista de ids de setups que usan
    ese POI) y se expone de solo lectura vía la propiedad ``used_by_setup``.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    direction: int = 0  # 1 / -1 / 0 (undefined)
    context_htf: Optional[MarketObject] = None
    poi: Optional[MarketObject] = None
    refinement: Optional[MarketObject] = None
    confirmation: Optional[MarketObject] = None
    trigger: Optional[MarketObject] = None
    eligibility: SetupEligibility = SetupEligibility.ELIGIBLE
    reason: str = ""
    created_at: Any = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction debe ser -1, 0 o 1")
        if not isinstance(self.eligibility, SetupEligibility):
            self.eligibility = SetupEligibility(self.eligibility)

    # --- linaje (solo lectura; vive en POI.meta) ---
    @property
    def used_by_setup(self) -> list[str]:
        """Ids de setups que reutilizan el POI (lee ``POI.meta``, NO muta)."""
        if self.poi is None:
            return []
        val = self.poi.meta.get("used_by_setup")
        return list(val) if isinstance(val, (list, tuple, set)) else []

    @staticmethod
    def _normalize_meta(meta: dict) -> dict:
        """Convierte meta a JSON-safe para garantizar round-trip SAVE->LOAD.

        Espejo de ``MarketObject._normalize_meta``: JSON no soporta ``set``,
        así que cualquier set se serializa como lista ordenada; los dict
        internos con valores set también se normalizan.
        """
        out: dict = {}
        for k, v in meta.items():
            if isinstance(v, set):
                out[k] = sorted(v)
            elif isinstance(v, dict):
                out[k] = {kk: (sorted(vv) if isinstance(vv, set) else vv) for kk, vv in v.items()}
            else:
                out[k] = v
        return out

    def to_dict(self) -> dict:
        def _obj(o: Optional[MarketObject]) -> Optional[dict]:
            return o.to_dict() if isinstance(o, MarketObject) else None

        created = self.created_at
        if created is None:
            created_ser = None
        elif hasattr(created, "isoformat"):
            created_ser = created.isoformat()
        else:
            created_ser = str(created)

        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": int(self.direction),
            "context_htf": _obj(self.context_htf),
            "poi": _obj(self.poi),
            "refinement": _obj(self.refinement),
            "confirmation": _obj(self.confirmation),
            "trigger": _obj(self.trigger),
            "eligibility": (
                self.eligibility.value
                if isinstance(self.eligibility, SetupEligibility)
                else self.eligibility
            ),
            "reason": self.reason,
            "created_at": created_ser,
            "meta": self._normalize_meta(self.meta),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Setup":
        def _obj(o):
            return MarketObject.from_dict(o) if isinstance(o, dict) else None

        return cls(
            id=d.get("id", ""),
            symbol=d.get("symbol", ""),
            direction=int(d.get("direction", 0)),
            context_htf=_obj(d.get("context_htf")),
            poi=_obj(d.get("poi")),
            refinement=_obj(d.get("refinement")),
            confirmation=_obj(d.get("confirmation")),
            trigger=_obj(d.get("trigger")),
            eligibility=SetupEligibility(d.get("eligibility", SetupEligibility.ELIGIBLE)),
            reason=d.get("reason", ""),
            created_at=d.get("created_at"),
            meta=dict(d.get("meta", {})),
        )


# ---------------------------------------------------------------------------
# Composición de Setups (SDD §13.5) — build_setups_at
# ---------------------------------------------------------------------------
# Esta sección COMPONE setups a partir de un MarketState en T. Es de solo
# lectura: NO ejecuta lifecycle, NO avanza barras, NO muta object_state ni
# POI.meta (la línea de linaje ``used_by_setup`` vive en POI.meta y la fija el
# caller explícito, no este compositor).
#
# Contrato de entrada:
#   ms  : MarketState (proyección event-sourced, causal / forward-PIT).
#   t   : punto en el tiempo (timestamp comparable con ``creation_time``).
#   ctx : descriptor de contexto HTF. Puede ser:
#           - un MarketObject (contexto HTF; el sesgo se infiere de su direction), o
#           - un dict con claves opcionales:
#               htf_bias: 'bullish'|'bearish'|'neutral'|'none' (o int de dirección
#                         / strings 'up'|'down'|'long'|'short').
#               context_htf / htf_context: MarketObject a incrustar como context_htf.
#         Si no se provee un sesgo bullish explícito, el setup se marca BLOCKED.
#   max_bars_apart : ventana causal para relate_fvg_ob (default 240, cómoda para
#                    cruces H4↔M15 donde los bar_index no son de la misma escala).
# ---------------------------------------------------------------------------

# HTF admitidos como POI (espejo de engine.market_object._POI_TFS).
_POI_TFS = frozenset({"D1", "H4", "H1"})
# LTF que pueden refinar un POI HTF (espejo de la jerarquía de market_state).
_LTF_TFS = frozenset({"H1", "M15", "M5", "M1"})


def _normalize_bias(bias) -> str:
    """Normaliza un sesgo HTF a uno de {'bullish','bearish','neutral','none'}.

    Acepta MarketObject, int/float (direccion), str (nombre de sesgo) o dict
    con claves 'htf_bias'/'bias' (cadena) o 'direction' (entero). Esto permite
    que ``build_setups_at`` reciba ``ctx={'htf_bias': ...}`` y que
    ``classify_eligibility`` comparara ``setup.direction`` con el sesgo (H3).
    """
    if isinstance(bias, MarketObject):
        d = int(bias.direction)
    elif isinstance(bias, dict):
        b = bias.get("htf_bias") or bias.get("bias")
        if isinstance(b, str):
            s = b.strip().lower()
            if s in ("bullish", "bearish", "neutral", "none", "na"):
                return s
            if s in ("up", "long"):
                return "bullish"
            if s in ("down", "short"):
                return "bearish"
            return "neutral"
        d = bias.get("direction")
        if isinstance(d, (int, float)):
            return "bullish" if int(d) > 0 else ("bearish" if int(d) < 0 else "neutral")
        return "neutral"
    elif isinstance(bias, (int, float)):
        d = int(bias)
    elif isinstance(bias, str):
        s = bias.strip().lower()
        if s in ("bullish", "bearish", "neutral", "none", "na"):
            return s
        if s in ("up", "long"):
            return "bullish"
        if s in ("down", "short"):
            return "bearish"
        return "neutral"
    else:
        return "neutral"
    return "bullish" if d > 0 else ("bearish" if d < 0 else "neutral")


def _resolve_htf_context(ctx):
    """Devuelve ``(context_object | None, bias_normalizado)`` a partir de ``ctx``."""
    if isinstance(ctx, MarketObject):
        return ctx, _normalize_bias(ctx)
    if isinstance(ctx, dict):
        obj = ctx.get("context_htf") or ctx.get("htf_context")
        obj = obj if isinstance(obj, MarketObject) else None
        return obj, _normalize_bias(ctx.get("htf_bias", "neutral"))
    # ctx ausente/desconocido -> sin contexto, sesgo neutral (no bullish => BLOCKED).
    return None, "neutral"


def _fvg_refines_ob(ms: "MarketState", fvg: MarketObject, ob: MarketObject) -> bool:
    """¿El FVG LTF refina efectivamente al OB HTF vía contención MTF canónica?

    Combina las dos navegaciones MTF del MarketState:
      * ``ltf_refines_htf(fvg)`` -> el padre de contexto del FVG debe ser el OB.
      * ``htf_contains_ltf(ob)`` -> el OB debe contener al FVG (padre o related).
    Más un enlace explícito cruzado en ``related_objects`` como red de seguridad.
    """
    # 1) Navegación MTF directa: el FVG declara al OB como padre de contexto.
    parent = ms.ltf_refines_htf(fvg.id)
    if parent is not None and parent.id == ob.id:
        return True
    # 2) El OB HTF contiene al FVG LTF (cubre parent_object y related_objects).
    if any(c.id == fvg.id for c in ms.htf_contains_ltf(ob.id)):
        return True
    # 3) Enlace explícito cruzado en related_objects.
    if ob.id in fvg.related_objects or fvg.id in ob.related_objects:
        return True
    return False


def _is_related(a: MarketObject, other_id: str) -> bool:
    """¿``a`` referencia a ``other_id`` por parent_object o related_objects?

    Los enlaces de linaje (parent/related) son INMUTABLES (sello de nacimiento),
    por lo que evaluarlos sobre la proyección histórica o sobre el objeto vivo
    da el mismo resultado: no hay riesgo de look-ahead al usarlos.
    """
    return (a.parent_object == other_id) or (other_id in a.related_objects)


def _find_confirmation(existing: list, direction: int, ob: MarketObject,
                       fvg: MarketObject) -> Optional[MarketObject]:
    """Busca el BOS de confirmation en el snapshot en T (canónico H2).

    El confirmation es un ``ObjectType.BOS`` de la MISMA dirección del setup y
    relacionado con el POI (OB) o el refinamiento (FVG). Devuelve la primera
    proyección que cumpla, o ``None`` si el contrato no puede completarse.
    """
    for o in existing:
        if o.type is not ObjectType.BOS:
            continue
        if int(o.direction) != int(direction):
            continue
        if (_is_related(o, ob.id) or _is_related(ob, o.id)
                or _is_related(o, fvg.id) or _is_related(fvg, o.id)):
            return o
    return None


def _find_trigger(existing: list, direction: int, ob: MarketObject,
                  fvg: MarketObject) -> Optional[MarketObject]:
    """Busca el trigger de ejecución en el snapshot en T (canónico H2).

    El trigger es un ``ObjectType.DISPLACEMENT`` (o un FVG de ejecución,
    ``Role.EXECUTION``) de la MISMA dirección y relacionado con el
    refinamiento (FVG) o el POI (OB).
    """
    for o in existing:
        is_disp = o.type is ObjectType.DISPLACEMENT
        is_exec_fvg = (o.type is ObjectType.FVG and o.role is Role.EXECUTION)
        if not (is_disp or is_exec_fvg):
            continue
        if int(o.direction) != int(direction):
            continue
        if (_is_related(o, fvg.id) or _is_related(fvg, o.id)
                or _is_related(o, ob.id) or _is_related(ob, o.id)):
            return o
    return None


def build_setups_at(
    ms: "MarketState",
    t,
    ctx,
    *,
    max_bars_apart: int = 240,
) -> list["Setup"]:
    """Compone setups ICT/SMC COMPLETOS en T a partir de un MarketState (solo lectura).

    Ensambla, para cada par ``(OB HTF ACTIVE como POI, FVG LTF ACTIVE que lo
    refina)`` que satisface la relación canónica FVG↔OB, un ``Setup`` COMPLETO
    con la cadena canónica de componentes:

        context_htf  <- contexto HTF provisto en ``ctx`` (D1/H4)
        poi          <- Order Block HTF (POI)
        refinement   <- FVG LTF que refina al POI
        confirmation <- BOS relacionado (ObjectType.BOS)
        trigger      <- DISPLACEMENT (o FVG de ejecución) relacionado
        direction    <- dirección del par (1 bullish / -1 bearish)

    Correcciones H2+H3 (Codex):
      * H2: ahora BUSCA y ASIGNA ``confirmation`` y ``trigger`` en el snapshot.
        Si el contrato exige setup completo y falta alguno => BLOCKED.
      * H3: la elegibilidad final compara ``setup.direction`` con el sesgo HTF
        (bearish bajo bullish => BLOCKED). Toda la lógica de elegibilidad está
        CENTRALIZADA en ``classify_eligibility``; este compositor NO la duplica.
      * Causalidad: usa ``ms.projection_at(T)`` (proyecciones históricas
        congeladas en T) — NUNCA ``ms.active()`` del presente, que miraría el
        futuro (look-ahead). El filtro ACTIVE se evalúa DENTRO del snapshot.

    INVARIANTES (auditoría):
      - NO ejecuta: no llama a lifecycle.evaluate / advance_bar / observe.
      - NO muta object_state ni POI.meta (la linaje la fija el caller).
      - Es determinista y causal: solo lee el mundo conocido hasta T.
    """
    # 1) Snapshot causal en T (proyecciones congeladas; sin look-ahead).
    proj = ms.projection_at(t)
    existing = list(proj.values())

    context_obj, htf_bias = _resolve_htf_context(ctx)

    # 2) Candidatos POI/refinement: ACTIVE DENTRO de la proyección en T.
    #    (No usamos ms.active() del presente: sería look-ahead.)
    ob_pois = [
        o for o in existing
        if o.type is ObjectType.ORDER_BLOCK
        and o.origin_tf in _POI_TFS
        and o.state == ObjectState.ACTIVE
    ]
    fvg_ltf = [
        o for o in existing
        if o.type is ObjectType.FVG
        and o.origin_tf in _LTF_TFS
        and o.state == ObjectState.ACTIVE
    ]
    if not ob_pois or not fvg_ltf:
        return []

    # 3) Relación canónica FVG↔OB (mismo sentido, solapamiento, orden causal).
    relations = relate_fvg_ob(
        fvg_ltf, ob_pois,
        max_bars_apart=max_bars_apart,
        same_direction=True,
        causal_mode="strict",
    )

    # 4) Ensamblar setups completos y delegar la elegibilidad a classify_eligibility.
    by_id = {o.id: o for o in existing}
    setups: list[Setup] = []
    seen: set[tuple[str, str]] = set()
    for rel in relations:
        ob = by_id.get(rel.ob_id)
        fvg = by_id.get(rel.fvg_id)
        if ob is None or fvg is None:
            continue
        if not _fvg_refines_ob(ms, fvg, ob):
            continue
        key = (ob.id, fvg.id)
        if key in seen:
            continue
        seen.add(key)

        # H2: confirmation (BOS) y trigger (DISPLACEMENT) en el snapshot en T.
        confirmation = _find_confirmation(existing, rel.direction, ob, fvg)
        trigger = _find_trigger(existing, rel.direction, ob, fvg)

        setup = Setup(
            symbol=(ob.symbol or fvg.symbol or ""),
            direction=int(rel.direction),
            context_htf=context_obj,
            poi=ob,
            refinement=fvg,
            confirmation=confirmation,
            trigger=trigger,
            meta={
                "relation": rel.relation,
                "causal_order": rel.causal_order,
                "overlap_low": rel.overlap_low,
                "overlap_high": rel.overlap_high,
                "bars_apart": rel.bars_apart,
                "poi_tf": ob.origin_tf,
                "refinement_tf": fvg.origin_tf,
                "htf_bias": htf_bias,
            },
        )
        # H3 + H2: la elegibilidad final (direction vs sesgo HTF y presencia de
        # confirmation/trigger) la CENTRALIZA classify_eligibility.
        classify_eligibility(setup, ctx, require_complete=True)
        setups.append(setup)
    return setups




# --- composicion (NO muta object_state) -------------------------------------- #
REASON_POI_INVALIDATED = "POI_INVALIDATED"
REASON_HTF_CONTEXT_CHANGED = "HTF_CONTEXT_CHANGED"


def build_setup(
    *,
    symbol: str,
    direction: int,
    context_htf: Optional[MarketObject] = None,
    poi: Optional[MarketObject] = None,
    refinement: Optional[MarketObject] = None,
    confirmation: Optional[MarketObject] = None,
    trigger: Optional[MarketObject] = None,
    htf_context_valid: bool = True,
    reason: str = "",
    meta: Optional[dict] = None,
) -> Setup:
    """Compone un Setup ICT/SMC SIN mutar ``object_state`` de ningun MarketObject.

    REGLA §13.3 (separacion ``object_state`` vs ``setup_eligibility``):
    - ``object_state`` PERTENECE al MarketObject y es de SOLO LECTURA aqui.
    - ``setup_eligibility`` PERTENECE al Setup. Se calcula aqui, independiente.
    - NO se escribe ``used_by_setup`` en ``POI.meta``: la linea de linaje se
      registra en otro momento (fuera de ``build_setup``).

    La elegibilidad se calcula como SNAPSHOT en el instante de la composicion.
    """
    eligibility = SetupEligibility.ELIGIBLE
    computed_reason = reason or ""

    if poi is not None and poi.is_terminal:
        eligibility = SetupEligibility.BLOCKED
        computed_reason = REASON_POI_INVALIDATED
    elif not htf_context_valid:
        eligibility = SetupEligibility.BLOCKED
        computed_reason = REASON_HTF_CONTEXT_CHANGED

    return Setup(
        symbol=symbol,
        direction=direction,
        context_htf=context_htf,
        poi=poi,
        refinement=refinement,
        confirmation=confirmation,
        trigger=trigger,
        eligibility=eligibility,
        reason=computed_reason,
        meta=dict(meta) if meta else {},
    )


# --- clasificacion de elegibilidad (SDD §13.4) ------------------------------ #
def _ctx_direction(ctx) -> int:
    """Direccion del contexto HTF, o 0 si no definida. Duck-typed."""
    if ctx is None:
        return 0
    if isinstance(ctx, dict):
        d = ctx.get("direction", 0)
        return int(d) if d is not None else 0
    d = getattr(ctx, "direction", None)
    return int(d) if d is not None else 0


def _ctx_aligned(ctx) -> bool:
    """True si el contexto HTF declara alineacion interna MTF.

    OE-05 / H9: solo ``aligned=False`` EXPLICITO bloquea. Si la clave esta
    ausente se asume alineado (comportamiento previo al endurecimiento), para
    no romper el contrato de contextos que solo declaran sesgo por cadena.
    """
    if ctx is None:
        return False
    if isinstance(ctx, dict):
        a = ctx.get("aligned", None)
    else:
        a = getattr(ctx, "aligned", None)
    if a is None:
        return True  # ausente => se asume alineado (no es aligned=False explicito)
    return bool(a)


def _htf_aligned(ctx, direction: int) -> bool:
    """Contexto HTF alineado con la direccion del setup (H3, Codex).

    Acepta dos formas de declarar el sesgo HTF:
      * numericamente (``ctx.direction`` via SimpleNamespace/MarketObject/dict), o
      * como cadena de sesgo (dict ``{'htf_bias': ...}`` o ``MarketObject.direction``
        normalizado por ``_normalize_bias``).
    Un setup bearish bajo sesgo bullish NO alinea => BLOCKED.
    """
    if direction == 0:
        return False
    # OE-05 / H9: si el contexto declara explicitamente aligned=False, NUNCA
    # alinea (fail-closed). El flag es autoritativo sobre el sesgo por cadena.
    if not _ctx_aligned(ctx):
        return False
    # 1) metodo numerico (direction del contexto HTF)
    ctx_dir = _ctx_direction(ctx)
    if ctx_dir != 0 and ctx_dir == direction:
        return True
    # 2) metodo de sesgo (cadena: bullish/bearish)
    bias = _normalize_bias(ctx)
    if bias == "bullish" and direction > 0:
        return True
    if bias == "bearish" and direction < 0:
        return True
    return False


def _is_active(mo) -> bool:
    """True si el MarketObject existe y esta en estado ACTIVE."""
    return mo is not None and getattr(mo, "state", None) == ObjectState.ACTIVE


def _obj_time(mo) -> Optional[Any]:
    """OE-02 / H6: tiempo de referencia de un objeto para orden causal.

    Usa confirmation_time (o tradable_time, o candidate_time, o creation_time)
    como marca del instante en que el objeto es operativo. Comparable entre
    distintas TF porque son datos temporales reales.
    """
    if mo is None:
        return None
    for attr in ("confirmation_time", "tradable_time", "candidate_time", "creation_time"):
        t = getattr(mo, attr, None)
        if t is not None:
            return t
    return None


def classify_eligibility(setup: "Setup", ctx, *, require_complete: bool = False) -> SetupEligibility:
    """Clasifica la elegibilidad de un setup compuesto (SDD §13.4).

    Punto UNICO de clasificación: ``build_setups_at`` delega aquí y NO duplica
    lógica. Precedencia:

        SUPERSEDED (POI INVALIDATED)
          > OUT_OF_CONTEXT (ctx None)
          > BLOCKED (ctx no alineado con direction — H3, Codex)
          > BLOCKED (setup incompleto: falta confirmation/trigger — H2, si
                   ``require_complete``)
          > ELIGIBLE (POI/refinement ACTIVE)

    H3: compara ``setup.direction`` con el sesgo HTF (``_htf_aligned``); un
    setup bearish bajo sesgo bullish queda BLOCKED.
    H2: si ``require_complete`` y faltan confirmation (BOS) o trigger
    (DISPLACEMENT), el setup no puede armarse => BLOCKED.

    NO muta los MarketObjects referenciados; actualiza setup.eligibility/reason.
    """
    if setup.poi is not None and setup.poi.state == ObjectState.INVALIDATED:
        setup.eligibility = SetupEligibility.SUPERSEDED
        setup.reason = "POI INVALIDATED: la estructura fue superada por el precio"
        return SetupEligibility.SUPERSEDED

    if ctx is None:
        setup.eligibility = SetupEligibility.OUT_OF_CONTEXT
        setup.reason = "contexto HTF ausente: no hay sesgo MTF para evaluar alineacion"
        return SetupEligibility.OUT_OF_CONTEXT

    if not _htf_aligned(ctx, setup.direction):
        setup.eligibility = SetupEligibility.BLOCKED
        setup.reason = (
            f"contexto HTF no alineado con direction={setup.direction} "
            f"(sesgo={_normalize_bias(ctx)}; not bullish)"
        )
        return SetupEligibility.BLOCKED

    # H2 (Setup completo, Codex): si el contrato exige setup completo y faltan
    # confirmation (BOS) o trigger (DISPLACEMENT), el setup no puede armarse y
    # queda BLOCKED. Centralizado aqui (build_setups_at NO lo duplica).
    if require_complete:
        missing = [
            name
            for name, comp in (
                ("confirmation", setup.confirmation),
                ("trigger", setup.trigger),
            )
            if comp is None
        ]
        if missing:
            setup.eligibility = SetupEligibility.BLOCKED
            setup.reason = (
                f"setup incompleto: faltan componentes requeridos {missing}"
            )
            return SetupEligibility.BLOCKED

    # OE-02 / H6 + OE-03 (Tesis 1, ley congelada): orden causal estricto de los
    # componentes del setup por tiempo operativo (no bar_index cross-TF):
    #     t_POI <= t_REFINEMENT <= t_CONFIRMATION <= t_TRIGGER <= t_DECISION
    # POI=OB (HTF), refinement=FVG (LTF), confirmation=BOS, trigger=DISPLACEMENT.
    # Setup no lleva decision_time => la cota superior del trigger es la propia
    # cadena (trigger debe ser >= confirmation, que ya es >= refinement >= POI).
    # Cualquier inversión es causalmente imposible en T => BLOCKED (no se inventa
    # causalidad hacia atrás). El DISPLACEMENT "crea la estructura" pero AÚN así
    # debe ocurrir DESPUÉS de la confirmación (BOS) en el tiempo real.
    _pairs = [
        ("POI", "refinement", setup.poi, setup.refinement),
        ("refinement", "confirmation", setup.refinement, setup.confirmation),
        ("confirmation", "trigger", setup.confirmation, setup.trigger),
    ]
    for name_a, name_b, a, b in _pairs:
        if a is not None and b is not None:
            ta = _obj_time(a)
            tb = _obj_time(b)
            if ta is not None and tb is not None and tb < ta:
                setup.eligibility = SetupEligibility.BLOCKED
                setup.reason = (
                    f"orden causal violado (H6): {name_b} ocurre antes que {name_a} "
                    f"({tb} < {ta}); el setup nunca pudo existir en tiempo real"
                )
                return SetupEligibility.BLOCKED

    if _is_active(setup.poi) and _is_active(setup.refinement):
        setup.eligibility = SetupEligibility.ELIGIBLE
        setup.reason = "contexto HTF alineado y POI/refinement ACTIVE"
        return SetupEligibility.ELIGIBLE

    setup.eligibility = SetupEligibility.BLOCKED
    setup.reason = "contexto HTF alineado pero POI/refinement no ACTIVE"
    return SetupEligibility.BLOCKED


__all__ = [
    "SetupEligibility",
    "Setup",
    "build_setup",
    "classify_eligibility",
    "build_setups_at",
]
