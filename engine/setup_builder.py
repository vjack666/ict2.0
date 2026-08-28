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

from engine.market_object import MarketObject, ObjectState, ObjectType
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
    """Normaliza un sesgo HTF a uno de {'bullish','bearish','neutral','none'}."""
    if isinstance(bias, MarketObject):
        d = int(bias.direction)
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


def build_setups_at(
    ms: "MarketState",
    t,
    ctx,
    *,
    max_bars_apart: int = 240,
) -> list["Setup"]:
    """Compone setups ICT/SMC en T a partir de un MarketState (solo lectura).

    Ensambla, para cada par ``(OB HTF ACTIVE como POI, FVG LTF ACTIVE que lo
    refina)`` que además satisface la relación canónica FVG↔OB (``relate_fvg_ob``
    en modo strict causal), un ``Setup`` con:

        context_htf  <- contexto HTF provisto en ``ctx`` (D1/H4)
        poi          <- Order Block HTF (POI)
        refinement   <- FVG LTF que refina al POI
        direction    <- dirección del par (1 bullish / -1 bearish)
        eligibility  <- ELIGIBLE si el contexto HTF es bullish; si no, BLOCKED

    Consume la API canónica del MarketState:
      * ``objects_existing_at(t)`` — snapshot causal en T (sin repaint).
      * ``active()`` — filtra a objetos vivos (no terminales).
      * ``htf_contains_ltf`` / ``ltf_refines_htf`` — contención MTF (refinamiento).
    Y la relación canónica ``relate_fvg_ob`` (engine.relations) para el
    emparejamiento geométrico/causal FVG↔OB.

    INVARIANTES (auditoría):
      - NO ejecuta: no llama a lifecycle.evaluate / advance_bar / observe.
      - NO muta object_state ni POI.meta (la linaje la fija el caller).
      - Es determinista y causal: solo lee el mundo conocido hasta T.
    """
    # 1) Snapshot causal en T y conjunto activo (cumple objects_existing_at + active).
    existing = ms.objects_existing_at(t)
    active_ids = {o.id for o in ms.active()}
    existing = [o for o in existing if o.id in active_ids]

    context_obj, htf_bias = _resolve_htf_context(ctx)

    # 2) Candidatos POI: Order Blocks en HTF, ACTIVE.
    ob_pois = [
        o for o in existing
        if o.type is ObjectType.ORDER_BLOCK
        and o.origin_tf in _POI_TFS
    ]
    # 3) Candidatos refinamiento: FVG en LTF, ACTIVE.
    fvg_ltf = [
        o for o in existing
        if o.type is ObjectType.FVG
        and o.origin_tf in _LTF_TFS
    ]
    if not ob_pois or not fvg_ltf:
        return []

    # 4) Relación canónica FVG↔OB (mismo sentido, solapamiento, orden causal).
    relations = relate_fvg_ob(
        fvg_ltf, ob_pois,
        max_bars_apart=max_bars_apart,
        same_direction=True,
        causal_mode="strict",
    )

    # 5) Ensamblar setups: la relación geométrica debe confirmarse con la
    #    contención MTF (el FVG LTF refina al OB HTF).
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

        if htf_bias == "bullish":
            eligibility = SetupEligibility.ELIGIBLE
            reason = "HTF context bullish; H4 OB POI refined by M15 FVG accepted"
        else:
            eligibility = SetupEligibility.BLOCKED
            reason = f"HTF context not bullish (bias={htf_bias}); setup blocked"

        setups.append(Setup(
            symbol=(ob.symbol or fvg.symbol or ""),
            direction=int(rel.direction),
            context_htf=context_obj,
            poi=ob,
            refinement=fvg,
            eligibility=eligibility,
            reason=reason,
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
        ))
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
    """True si el contexto HTF declara alineacion interna MTF."""
    if ctx is None:
        return False
    if isinstance(ctx, dict):
        a = ctx.get("aligned", None)
    else:
        a = getattr(ctx, "aligned", None)
    return bool(a) if a is not None else True


def _htf_aligned(ctx, direction: int) -> bool:
    """Contexto HTF alineado con la direccion del setup."""
    if direction == 0:
        return False
    ctx_dir = _ctx_direction(ctx)
    if ctx_dir == 0 or ctx_dir != direction:
        return False
    return _ctx_aligned(ctx)


def _is_active(mo) -> bool:
    """True si el MarketObject existe y esta en estado ACTIVE."""
    return mo is not None and getattr(mo, "state", None) == ObjectState.ACTIVE


def classify_eligibility(setup: "Setup", ctx) -> SetupEligibility:
    """Clasifica la elegibilidad de un setup compuesto (SDD §13.4).

    Precedencia: SUPERSEDED (POI INVALIDATED) > OUT_OF_CONTEXT (ctx None) >
    BLOCKED (ctx no alineado o poi/refinement no ACTIVE) > ELIGIBLE.
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
            f"(ctx.direction={_ctx_direction(ctx)})"
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
