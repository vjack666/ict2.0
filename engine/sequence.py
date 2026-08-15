"""ict_backtest/sequence.py - Capa 2: motor EVENT-SEQUENCE (memoria de eventos).

Arregla la raiz del problema que viste: el mini-check del dashboard evaluaba
sweep + BOS + displacement en la MISMA vela ("todo de golpe"). En ICT real los
eventos ocurren EN SECUENCIA y el mercado se revela en cascada (D1 -> H4 -> M15):

  1. SWEEP    : el precio barre una liquidez (BSL/SSL) en HTF o LTF.
  2. DISPLACE  : en las proximas N velas hay una vela de displacement fuerte
                en la direccion del setup (la "falla" de la que habla ICT).
  3. BOS/CHOCH : luego el precio rompe estructura (BOS continuacion o CHOCH giro)
                en esa direccion.
  4. ENTRY     : aparece un FVG/OB en la direccion -> se genera la senal.

Cada evento se recuerda vela a vela en SequenceState (memoria). Si pasa
max_gap velas sin avanzar, la secuencia se reinicia (no acumula ruido).

Esto es la "memoria" que pediste, antes de meter ML (Capa 3): el estado de
que eventos ya pasaron y hace cuantas velas.

============================================================================
R9 PASO 3 - Refactor de tipo de dato (SIN cambiar reglas ICT).
============================================================================
El motor AHORA consume MarketObject[] en lugar de columnas sueltas del
DataFrame. Cada vela del LTF se envuelve en UN MarketObject(type=CANDLE) que
carga en su `meta` TODOS los campos ICT de esa vela (bos_dir, choch_dir,
fvg_*, ob_*, sweep_*, displacement_*, high/low/open/close/atr/bos_level/time).
Las funciones internas (_has_sweep, _has_bos, _latest_fvg_zone, etc.) leen
exclusivamente de MarketObject - NUNCA de ltf_df.iloc[i][col].

La conversion inicial (DataFrame -> MarketObject[]) vive en `_candle_objects`,
que NO toca translation.py (capa de compatibilidad intacta). `run_sequence`
acepta DataFrame O lista de objetos (compatibilidad de firma).

Equivalencia: el round-trip df -> objetos -> senales es IDENTICO al legado
(ver tests/test_r9_object_adapter.py). Ninguna regla ICT cambia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json

import numpy as np
import pandas as pd

# engine/sequence.py - B1: la secuencia sube al MOTOR (fuente unica de decision).
# NUNCA importa ict_backtest/ (Ley). Consume del motor y de la geometria pura.
from engine.multitf_context import MultiTFContext, extract_htf_layer
from engine.plan import top_down_allows_trade, _closed_row_at_time as closed_row_at_time
from engine.market_object import MarketObject, ObjectState, ObjectType, Role, _POI_TFS
# POI anclado: UNICA fuente = engine (Ley). El backtest no tiene logica propia.
from engine.poi_anchor import poi_present
# B5 (Ley 8 / Ley 7 / Ley 4): el Expediente por señal vive en el motor.
from engine.expediente import Expediente
# B3 (Ley 6 / Ley 4): invalidacion predefinida y explicita.
from engine.invalidation import build_rules, check_invalidation


PHASE = ("IDLE", "SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE")

# Campos ICT de la vela que sequence necesita. Se cargan en MarketObject.meta.
_CANDLE_FIELDS = (
    "bos_dir", "choch_dir", "fvg_bullish", "fvg_bearish", "ob_direction",
    "ob_bullish", "ob_bearish", "liquidity_sweep_up", "liquidity_sweep_down",
    "displacement_bullish", "displacement_bearish", "high", "low", "open",
    "close", "atr", "bos_level", "time",
)


@dataclass
class SequenceConfig:
    sweep_lookback: int = 8        # el sweep debe verse en las ultimas N velas
    displace_gap: int = 6          # ventana para el displacement tras el sweep
    # R10 (Propuesta A): ventana de confirmacion BOS.
    #   bos_gap: int  -> fijo (solo para debugging/scripts).
    #   bos_gap: None -> DINAMICO: confirmation_window() deriva N de la FUERZA
    #                del quiebre via tabla empirica del backtest (sin ATR/indicadores).
    # Por defecto running en modo dinamico; si se pasa int, se mantiene compat.
    bos_gap: int | None = None
    require_displacement: bool = True
    counter_trend: bool = False
    tp_mode: str = "fixed2r"
    # RR de la contratacion LTF (ICT 1:3). Usado por el nodo CONTRACT.
    rr: float = 3.0
    # B3: nueva regla sustantiva OPPOSITE_SWING_BREAK, detras de flag.
    # OFF = bit a bit identico al historico (regresion cero).
    invalidate_on_opposite_swing: bool = False


@dataclass
class SequenceState:
    """Memoria de la secuencia en curso para UN simbolo/direccion."""
    phase: str = "IDLE"
    direction: int = 0
    sweep_idx: int = -1
    displace_idx: int = -1
    bos_idx: int = -1
    bos_level: float = float("nan")
    zone_high: float = float("nan")
    zone_low: float = float("nan")
    zone_pd_type: str = "NONE"   # Fase B1 (SPEC §4): metadato de la zona congelada
    zone_pd_tier: str = "NONE"   # (no altera la decisión de entry; info para POI/stacking)
    zone_authority: Any = None     # Fase C (C2/C3): ZoneAuthority anotada (peso de confianza)
    htf_aligned: bool = True       # A1 (Brecha A1): ¿la cascada D1->H4->H1 permite la dir?
    htf_reason: str = "ok"         # A1: motivo del filtro top-down (observabilidad)
    poi_present: Any = None          # Brecha A (Fase C): ¿hay POI HTF anclado en dir? (bonus, no gate)
    expediente: Any = None          # B5: Expediente por señal (Ley 8/7/4)
    invalidation_rules: list = field(default_factory=list)  # B3: reglas congeladas al nacimiento
    history: list = field(default_factory=list)
    # Fase 5 (Arquitectura A): memoria causal minima. ids de cada evento ya
    # decidido por el motor; parent apunta a id YA confirmado (anti-look-ahead).
    sweep_id: str = ""
    displace_id: str = ""
    bos_id: str = ""
    entry_id: str = ""
    # Fase 6: cierre de la formacion. LIQUIDITY (raiz) y POI/REFINEMENT.
    liquidity_id: str = ""
    poi_id: str = ""
    refinement_id: str = ""
    entry_id: str = ""
    contract_id: str = ""   # Contratacion LTF (hijo del RETURN, role=EXECUTION)
    event_objs: dict = field(default_factory=dict)  # id -> MarketObject del evento
    def reset(self):
        self.phase = "IDLE"
        self.direction = 0
        self.sweep_idx = -1
        self.displace_idx = -1
        self.bos_idx = -1
        self.bos_level = float("nan")
        self.zone_high = float("nan")
        self.zone_low = float("nan")
        self.zone_pd_type = "NONE"
        self.zone_pd_tier = "NONE"
        self.zone_authority = None
        self.htf_aligned = True
        self.htf_reason = "ok"
        self.poi_present = None
        self.expediente = None
        self.invalidation_rules = []
        self.sweep_id = ""
        self.displace_id = ""
        self.bos_id = ""
        self.entry_id = ""
        self.liquidity_id = ""
        self.poi_id = ""
        self.refinement_id = ""
        self.entry_id = ""
        self.contract_id = ""
        self.event_objs = {}
    def note(self, tag: str, i: int, extra: str = ""):
        self.history.append((tag, i, extra))

    # ------------------------------------------------------------------
    # Persistencia (HYP-002 M3): snapshot JSON-serializable, sin referencias
    # vivas. Solo estado ya decidido (filas <= k). Versionado.
    # ------------------------------------------------------------------
    SCHEMA_VERSION = "1.0"

    def to_snapshot(self) -> dict:
        """Snapshot puro del estado ya decidido (JSON-serializable)."""
        from engine.invalidation import InvalidationRule
        return {
            "schema_version": self.SCHEMA_VERSION,
            "phase": self.phase,
            "direction": int(self.direction),
            "sweep_idx": int(self.sweep_idx),
            "displace_idx": int(self.displace_idx),
            "bos_idx": int(self.bos_idx),
            "bos_level": _f(self.bos_level),
            "zone_high": _f(self.zone_high),
            "zone_low": _f(self.zone_low),
            "zone_pd_type": self.zone_pd_type,
            "zone_pd_tier": self.zone_pd_tier,
            "zone_authority": _safe(self.zone_authority),
            "htf_aligned": bool(self.htf_aligned),
            "htf_reason": self.htf_reason,
            "poi_present": self.poi_present,
            "invalidation_rules": [_rule_to_dict(r) for r in self.invalidation_rules],
            "history": [(str(t), int(i), str(e)) for t, i, e in self.history],
            "liquidity_id": self.liquidity_id,
            "sweep_id": self.sweep_id,
            "displace_id": self.displace_id,
            "bos_id": self.bos_id,
            "poi_id": self.poi_id,
            "refinement_id": self.refinement_id,
            "entry_id": self.entry_id,
            "contract_id": self.contract_id,
            "event_objs": {
                oid: (obj.to_dict() if hasattr(obj, "to_dict") else obj)
                for oid, obj in self.event_objs.items()
            },
            "expediente": (
                self.expediente.to_dict() if self.expediente is not None else None
            ),
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "SequenceState":
        """Reconstruye SequenceState desde un snapshot (round-trip)."""
        from engine.market_object import MarketObject
        from engine.expediente import Expediente
        ver = str(data.get("schema_version", "1.0"))
        if ver.split(".")[0] != cls.SCHEMA_VERSION.split(".")[0]:
            raise ValueError(f"Schema incompatible: {ver} vs {cls.SCHEMA_VERSION}")
        st = cls()
        st.phase = data["phase"]
        st.direction = int(data["direction"])
        st.sweep_idx = int(data["sweep_idx"])
        st.displace_idx = int(data["displace_idx"])
        st.bos_idx = int(data["bos_idx"])
        st.bos_level = _nan_safe(data["bos_level"])
        st.zone_high = _nan_safe(data["zone_high"])
        st.zone_low = _nan_safe(data["zone_low"])
        st.zone_pd_type = data.get("zone_pd_tier", "NONE") and data.get("zone_pd_type", "NONE")
        st.zone_pd_tier = data.get("zone_pd_tier", "NONE")
        st.zone_authority = data.get("zone_authority")
        st.htf_aligned = bool(data.get("htf_aligned", True))
        st.htf_reason = data.get("htf_reason", "ok")
        st.poi_present = data.get("poi_present")
        st.invalidation_rules = [_rule_from_dict(r) for r in data.get("invalidation_rules", [])]
        st.history = [(t, int(i), e) for t, i, e in data.get("history", [])]
        st.liquidity_id = data.get("liquidity_id", "")
        st.sweep_id = data.get("sweep_id", "")
        st.displace_id = data.get("displace_id", "")
        st.bos_id = data.get("bos_id", "")
        st.poi_id = data.get("poi_id", "")
        st.refinement_id = data.get("refinement_id", "")
        st.entry_id = data.get("entry_id", "")
        st.contract_id = data.get("contract_id", "")
        st.event_objs = {
            oid: MarketObject.from_dict(d) for oid, d in data.get("event_objs", {}).items()
        }
        exp_d = data.get("expediente")
        st.expediente = Expediente.from_dict(exp_d) if exp_d else None
        return st

    def save(self, path: str) -> None:
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(self.to_snapshot(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str) -> "SequenceState":
        from pathlib import Path
        with Path(path).open("r", encoding="utf-8") as f:
            return cls.from_snapshot(json.load(f))


# Helpers de serializacion (privados, modulo sequence).
def _f(x):
    if x is None or (isinstance(x, float) and x != x):
        return None
    return float(x)


def _nan_safe(x):
    return float("nan") if x is None else float(x)


def _safe(obj):
    if obj is None:
        return None
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, (dict, list, str, int, float, bool)):
        return obj
    return str(obj)


def _rule_to_dict(r) -> dict:
    return {
        "kind": getattr(r, "kind", ""),
        "level": _f(getattr(r, "level", None)),
        "deadline_idx": (None if getattr(r, "deadline_idx", None) is None
                         else int(getattr(r, "deadline_idx"))),
        "descr": getattr(r, "descr", ""),
        "direction": int(getattr(r, "direction", 0)),
    }


def _rule_from_dict(d: dict):
    from engine.invalidation import InvalidationRule
    return InvalidationRule(
        kind=d.get("kind", ""),
        level=_nan_safe(d.get("level")),
        deadline_idx=(None if d.get("deadline_idx") is None else int(d["deadline_idx"])),
        descr=d.get("descr", ""),
        direction=int(d.get("direction", 0)),
    )
# ---------------------------------------------------------------------------
# R9 Paso 3: constructor de objetos (NO toca translation.py)
# ---------------------------------------------------------------------------

def _candle_objects(ltf_df: pd.DataFrame, ltf_tf: str) -> list[MarketObject]:
    """Envuelve cada vela del LTF en UN MarketObject(type=CANDLE).

    Carga en `meta` TODOS los campos ICT de la vela para que sequence los
    lea sin tocar el DataFrame. El `bar_index` ancla al indice de la vela
    (igual que ltf_df.iloc[i]), garantizando equivalencia 1:1 con el legado.
    """
    objs: list[MarketObject] = []
    for i, row in ltf_df.iterrows():
        meta: dict[str, Any] = {}
        for col in _CANDLE_FIELDS:
            meta[col] = row.get(col, np.nan)
        objs.append(MarketObject(
            type=ObjectType.CANDLE, origin_tf=ltf_tf, role=Role.REFINEMENT,
            state=ObjectState.ACTIVE,
            bar_index=int(i), bar_time=row.get("time"), meta=meta,
        ))
    return objs


# ---------------------------------------------------------------------------
# Funciones internas - leen MarketObject (NO columnas del DataFrame)
# ---------------------------------------------------------------------------

def _has_sweep(obj: MarketObject, est_htf: dict, direction: int) -> bool:
    """Sweep de la liquidez OPUESTA a la direccion del setup (stop-hunt).

    Long busca sweep DOWN (barre SSL); Short busca sweep UP (barre BSL).
    Se acepta en LTF o HTF.
    """
    if direction == 1:
        return bool(obj.meta.get("liquidity_sweep_down", False)) or bool(est_htf.get("sweep_down", False))
    if direction == -1:
        return bool(obj.meta.get("liquidity_sweep_up", False)) or bool(est_htf.get("sweep_up", False))
    return False


def _has_displacement(obj: MarketObject, direction: int, est_htf: dict | None = None) -> bool:
    """Displacement de impulso fuerte en la direccion del setup.

    Igual que el sweep, se acepta en LTF O HTF (la vela del sweep puede ser
    HTF). Antes solo miraba la vela LTF exacta, lo que silenciaba setups de
    ruptura rapida (Silver Bullet) donde la entrada M5 es pequena sobre el FVG.
    Ver AUDIT_BUG_SILVER_TF.md (hallazgo IA externa: asimetria de diseno).
    """
    if direction == 1:
        if bool(obj.meta.get("displacement_bullish", False)):
            return True
        return bool((est_htf or {}).get("displacement_bullish", False))
    if direction == -1:
        if bool(obj.meta.get("displacement_bearish", False)):
            return True
        return bool((est_htf or {}).get("displacement_bearish", False))
    return False


def _has_choch(obj: MarketObject, est_htf: dict, direction: int, counter_trend: bool) -> bool:
    """CHOCH en la direccion del giro (aviso de cambio de caracter, libro 02 §3.1).

    En contratendencia el CHOCH debe ir OPUESTO al HTF (es el paso 2 de la
    secuencia canonica BOS->CHOCH->BOS). En a-favor no se exige (el BOS de
    continuacion basta).
    """
    choch_dir = int(obj.meta.get("choch_dir", 0) or 0)
    htf_trend = str(est_htf.get("trend", "RANGING"))
    if counter_trend:
        want = -1 if htf_trend == "BULLISH" else 1 if htf_trend == "BEARISH" else direction
    else:
        return False  # a-favor: el CHOCH no es requisito (ver _has_bos)
    return choch_dir == want


def _has_bos(obj: MarketObject, est_htf: dict, direction: int, counter_trend: bool) -> bool:
    """BOS/CHOCH en la direccion del setup.

    A-favor (counter_trend=False): el BOS del LTF debe ir en la direccion del
    sesgo HTF. Contratendencia: el BOS/CHOCH debe ir en direccion OPUESTA al HTF.
    """
    _bd = obj.meta.get("bos_dir", 0)
    bos_dir = 0 if (_bd is None or (isinstance(_bd, float) and (_bd != _bd))) else int(_bd)
    _cd = obj.meta.get("choch_dir", 0)
    choch_dir = 0 if (_cd is None or (isinstance(_cd, float) and (_cd != _cd))) else int(_cd)
    htf_trend = str(est_htf.get("trend", "RANGING"))
    if counter_trend:
        want = -1 if htf_trend == "BULLISH" else 1 if htf_trend == "BEARISH" else direction
    else:
        want = direction
    return (bos_dir == want) or (choch_dir == want)


def _htf_has_poi(est_htf: dict, target: int) -> bool:
    """¿El HTF tiene un POI (FVG/OB) en la direccion del setup?

    Ontologia (MARKET_OBJECT_MODEL.md): el POI institucional SOLO existe en
    HTF (D1/H4/H1). La zona de entrada del LTF (FVG/OB) solo cuenta si
    hay un POI de HTF que la respalde. Sin esto, un FVG M15 suelto se
    usa como entrada (error conceptual que la tesis 18 corrige).

    `est_htf` puede traer las columnas de detectores del HTF; si no las trae,
    se asume que NO hay POI (comportamiento conservador).
    """
    if target == 1:
        return bool(est_htf.get("fvg_bullish", False)) or bool(est_htf.get("ob_bullish", False))
    if target == -1:
        return bool(est_htf.get("fvg_bearish", False)) or bool(est_htf.get("ob_bearish", False))
    return False


def _latest_fvg_zone(obj: MarketObject, direction: int) -> tuple[float, float] | None:
    """Cuadro del FVG mas reciente en la direccion del setup.

    Devuelve (zone_high, zone_low) del FVG. El trader traza ESTE cuadro y
    espera el retorno (mitigation). Si no hay FVG, None.
    """
    if direction == 1 and bool(obj.meta.get("fvg_bullish", False)):
        # Normaliza: un FVG puede dejar low>high (gap); la zona es (max, min).
        h, l = float(obj.meta.get("high")), float(obj.meta.get("low"))
        return (max(h, l), min(h, l))
    if direction == -1 and bool(obj.meta.get("fvg_bearish", False)):
        h, l = float(obj.meta.get("high")), float(obj.meta.get("low"))
        return (max(h, l), min(h, l))
    return None


def _latest_ob_zone(obj: MarketObject, direction: int) -> tuple[float, float] | None:
    """Cuerpo del order block (vela de displacement previa) como cuadro.

    La columna del dataframe es 'ob_direction' (values 'bullish'/'bearish'),
    NO 'ob_dir'. Se corrige el nombre y el case para que el OB se use de
    verdad como zona de entrada.
    """
    ob_dir = str(obj.meta.get("ob_direction", "-")).lower()
    if direction == 1 and ob_dir == "bullish":
        o, c = float(obj.meta.get("open")), float(obj.meta.get("close"))
        return (max(o, c), min(o, c))
    if direction == -1 and ob_dir == "bearish":
        o, c = float(obj.meta.get("open")), float(obj.meta.get("close"))
        return (max(o, c), min(o, c))
    return None


def _touches_zone(obj: MarketObject, zone_high: float, zone_low: float) -> bool:
    """La vela toca/retorna al cuadro (mitigation). Confirma entrada."""
    low, high = float(obj.meta.get("low")), float(obj.meta.get("high"))
    return (low <= zone_high) and (high >= zone_low) and (zone_low < zone_high)


def _direction_from_bias(bias: str, counter_trend: bool) -> int:
    if bias == "BULLISH":
        return -1 if counter_trend else 1
    if bias == "BEARISH":
        return 1 if counter_trend else -1
    return 0


def _make_event_object(symbol, ltf_tf, event_type, direction, i, time, level,
                        parent_id, meta, role=None, obj_type=None) -> "MarketObject":
    """Fase 5/6 (Arquitectura A): crea el MarketObject de UN evento de secuencia.

    `id` es uuid unico (no hash) para evitar colision entre eventos del mismo
    idx. `parent_object` apunta al id del evento padre YA confirmado. Anti-
    look-ahead: el llamador solo pasa parent_id de un evento con idx <= i.
    El nivel es DERIVABLE de OHLC (sin indicadores).
    `role`/`obj_type` permiten respetar la ontologia (POI=HTF, FVG/OB=REFINEMENT).
    """
    from uuid import uuid4
    if obj_type is None:
        obj_type = event_type if event_type in ObjectType.__members__ else "CANDLE"
    if role is None:
        role = "CONTEXT"
    obj = MarketObject(
        type=ObjectType[obj_type],
        origin_tf=ltf_tf,
        role=Role[role],
        direction=int(direction),
        zone_high=float(level) if level == level else float("nan"),
        zone_low=float(level) if level == level else float("nan"),
        creation_time=time,
        state=ObjectState.CREATED,
        bar_index=int(i),
        bar_time=time,
        parent_object=parent_id or None,
        meta=dict(meta or {}),
        symbol=symbol,
    )
    return obj


def _build_expediente(symbol: str, ltf_tf: str, direction: int, i: int,
                      time, birth_condition: str,
                      liquidity_id: str = "") -> "tuple[Expediente, MarketObject]":
    """B5: crea el Expediente en el nacimiento (sweep) y registra SWEEP.

    Fase 5: el evento SWEEP recibe su propio MarketObject con id; su padre es
    la liquidez (ausente como objeto explicito) -> parent_object="" (raiz).
    Fase 6: el SWEEP SI tiene padre explicito = LIQUIDITY (liquidity_id).
    """
    exp = Expediente.open(
        symbol=symbol,
        tf=ltf_tf,
        direction=direction,
        birth_idx=i,
        birth_time=time,
        birth_condition=birth_condition,
        invalidation_rule="",  # se predefine en el nacimiento (B3)
        meta={"symbol": symbol, "ltf_tf": ltf_tf},
    )
    # Evento SWEEP: hijo de LIQUIDITY ya confirmada.
    sweep_obj = _make_event_object(symbol, ltf_tf, "SWEEP", direction, i, time,
                                   float("nan"), liquidity_id,
                                   {"phase": "SWEEP", "condition": birth_condition})
    exp.advance("SWEEP", i, time, birth_condition,
                event_id=sweep_obj.id, parent_event_id=liquidity_id)
    return exp, sweep_obj


def _advance_expediente(exp: "Expediente | None", phase: str, i: int, time,
                        condition: str = "", event_id: str = "",
                        parent_event_id: str = "") -> None:
    if exp is None:
        return
    try:
        exp.advance(phase, i, time, condition, event_id=event_id,
                    parent_event_id=parent_event_id)
    except ValueError:
        # Guarda anti-look-ahead: si algo intenta registrar idx menor, no
        # rompe la señal (defensivo). No debe ocurrir en flujo normal.
        pass


def _invalidate_expediente(exp: "Expediente | None", i: int, time,
                           reason: str | None) -> None:
    if exp is None:
        return
    try:
        exp.invalidate(i, time, reason)
    except ValueError:
        pass


def _check_and_apply_invalidation(state: "SequenceState", obj: MarketObject, i: int) -> bool:
    """B3: evalúa las reglas congeladas contra la barra i.

    Devuelve True si el expediente fue invalidado (y la secuencia debe
    reiniciarse). Las reglas son descriptivas salvo OPPOSITE_SWING_BREAK, que
    SI cambia la decision - pero solo cuando el flag esta ON (regresion cero).
    """
    if not state.invalidation_rules or state.expediente is None:
        return False
    rule = check_invalidation(state.invalidation_rules, obj, i)
    if rule is None:
        return False
    _invalidate_expediente(state.expediente, i, obj.meta.get("time"), rule.descr)
    return True


def confirmation_window(bos_obj: MarketObject, ctx_objs: list[MarketObject],
                         ctx_len: int, bos_table: dict | None) -> int:
    """R10 (Propuesta A): ventana de confirmacion BOS DINAMICA, SIN INDICADORES.

    Deriva N de la FUERZA del quiebre usando MATEMATICA PURA del gráfico:
        r = rango_bos / rango_promedio_contexto
    donde rango = high - low (ningún indicador). Luego mapea `r` a un bucket
    entero y lo busca en `bos_table` (tabla empirica P(mitigacion en N velas |
    fuerza r), pre-calculada del backtest). Si no hay tabla, fallback 40.

    Esto reemplaza el "numero magico" por "lo que el mercado hizo antes en
    situaciones iguales" (Principio 1: decision del estado, no constante).
    """
    if bos_table is None:
        return 40  # fallback deterministico (default canonico previo a R10)

    def _rango(o: MarketObject) -> float:
        return float(o.meta.get("high", 0.0)) - float(o.meta.get("low", 0.0))

    rango_bos = _rango(bos_obj)
    if ctx_len > 0 and rango_bos <= 0:
        return 40
    # rango promedio del contexto (promedio simple de high-low, NO ATR).
    if ctx_len > 0:
        suma = sum(_rango(o) for o in ctx_objs[:ctx_len])
        rango_ctx = suma / ctx_len
    else:
        rango_ctx = rango_bos
    if rango_ctx <= 0:
        return 40
    r = rango_bos / rango_ctx
    # bucket: 1 (debil) .. 5+ (muy fuerte). BOS fuerte => bucket alto.
    bucket = max(1, min(5, int(round(r))))
    return int(bos_table.get(bucket, 40))


def _effective_bos_gap(cfg: SequenceConfig, i: int, obj, est_htf,
                       objs, bos_table) -> int:
    """Ventana efectiva: fija si bos_gap es int, dinamica si es None.

    R10: el contexto es la ventana de velas previas (memoria del humano) para
    medir el rango promedio del mercado sin indicadores.
    """
    if cfg.bos_gap is None:
        lo = max(0, i - 50)
        ctx = objs[lo:i] if i > lo else objs[lo:i + 1]
        return confirmation_window(obj, ctx, len(ctx), bos_table)
    return cfg.bos_gap


def _build_ltf_contract(state: "SequenceState", objs, obj, ltf_tf: str, target: int,
                         cfg: "SequenceConfig", exec_frames: dict | None = None):
    """Contratacion LTF (nodo CONTRACT, hijo del RETURN).

    entry/sl/tp SIN mezclar con los eventos de formacion. Geometria LTF pura
    por defecto; si se pasan `exec_frames` (M5/M1) se reancla la entrada fina
    via engine.execution.fine_execution (el motor NO inventa deteccion).

    Devuelve dict con entry, sl, tp, rr, exec_tf, fine.
    """
    # entry = precio del RETURN (toque de la zona LTF por el que se disparo).
    entry = float(obj.meta.get("close", np.nan))
    # SL estructural = mecha del sweep LTF (libro 18: SL SIEMPRE en estructura).
    _sweep = objs[state.sweep_idx] if 0 <= state.sweep_idx < len(objs) else None
    _buf = 0.3
    if _sweep is not None:
        _rng = float(_sweep.meta.get("high", 0.0)) - float(_sweep.meta.get("low", 0.0))
        if _rng > 0:
            _buf = _buf * _rng
        if target > 0:
            _sl_level = float(_sweep.meta.get("low", np.nan))
            sl = _sl_level - _buf
        else:
            _sl_level = float(_sweep.meta.get("high", np.nan))
            sl = _sl_level + _buf
    else:
        sl = float("nan")
    rr = float(getattr(cfg, "rr", 3.0))
    if np.isfinite(entry) and np.isfinite(sl) and sl != entry:
        if target > 0:
            tp = entry + rr * (entry - sl)
        else:
            tp = entry - rr * (sl - entry)
    else:
        tp = float("nan")
    exec_tf = "M15"
    fine = False
    # Reanclaje fino opcional (NO deteccion nueva; solo reancla lo ya validado).
    if exec_frames:
        try:
            from engine.execution import fine_execution
            _fe = fine_execution(
                exec_frames, obj.meta.get("time"), target, exec_tf="M5",
                rr=rr, sweep_ts=_sweep.meta.get("time") if _sweep is not None else None,
            )
            if _fe.get("ok"):
                entry, sl, tp = float(_fe["entry"]), float(_fe["sl"]), float(_fe["tp"])
                exec_tf = _fe.get("exec_tf", "M5")
                fine = True
        except Exception:
            pass
    return {
        "entry": entry, "sl": sl, "tp": tp, "rr": rr,
        "exec_tf": exec_tf, "fine": fine,
    }


def _run_sequence_impl(ltf_df_or_objs: Any, est_htf_fn, cfg: SequenceConfig,
                 htf_poi_fn=None, ltf_tf: str = "M15", bos_table: dict | None = None,
                 htf_pd_index=None, ltf_map: dict | None = None,
                 htf: str | None = None,
                 est_htf_ctx_fn=None, exec_frames: dict | None = None,
                 initial_state: Any = None, start_i: int = 0,
                 copy_objs: bool = True, single_step: bool = False):
    """Recorre el LTF y devuelve lista de dicts de senal.

    R9 Paso 3: acepta DataFrame O lista de MarketObject (type=CANDLE). En
    ambos casos itera sobre MarketObject[]; NUNCA lee columnas del DataFrame
    dentro del loop. Equivalencia 100% con el legado (mismo bar_index).

    est_htf_fn(i) -> dict con trend/sweep_up/sweep_down del HTF en la vela i.
        En Fase C (C1) tambien puede traer 'pd_zones': lista de PD arrays
        HTF vigentes (HtfPdZone) a la vela i.
        (Legacy: mantenido para llamadores existentes y tests aislados.)
    htf / est_htf_ctx_fn (Fase 1, lectura multitemporal): si est_htf_ctx_fn
        se pasa, run_sequence lo llama por barra y obtiene un MultiTFContext
        con el snapshot closed-only de TODA la cadena D1..M1. Luego aplica
        extract_htf_layer(context, htf) para seguir decidiendo con el MISMO
        HTF que usaba antes (Opción A): comportamiento 100% idéntico al
        baseline de 1 nivel. Los otros 5 TF viajan disponibles en el
        contexto pero aún no influyen en la lógica. Sin est_htf_ctx_fn, el
        comportamiento es exactamente el de antes (est_htf_fn legacy).
    htf_poi_fn(i, target) -> bool OPCIONAL: si se pasa, la zona de entrada del
        LTF (FVG/OB) SOLO se memoriza cuando el HTF tiene un POI en esa
        direccion (fidelidad ICT, tesis 18). Si es None (default), el
        comportamiento es el historico (no rompe llamadores existentes).
    bos_table -> dict bucket->ventana (R10 Propuesta A). Si cfg.bos_gap is None,
        la ventana de confirmacion BOS se deriva de la FUERZA del quiebre via
        esta tabla empirica (sin indicadores). Si bos_gap es int, se ignora.
    htf_pd_index -> HtfPdIndex OPCIONAL (Fase C, C1/C2). Si se pasa, cada
        zona LTF trazada se ANOTA con su ZoneAuthority (peso de confianza de
        zona, NO gate duro). El conteo de senales NO cambia: C solo aporta
        informacion contextual (Contrato de no invasion de C).
    Cada senal: {time, direction, entry, phase_log, zone_authority}.

    single_step (Opción B, Change Gate Mayor 2026-08-14, autorizado por Director):
        si True, el loop itera SOLO la vela `start_i+1` (una transición). Usado
        por SequenceRunner.step(i) para replay/streaming vela-a-vela O(N) con
        índices absolutos intactos (objs completo, NO sublista). Es el MISMO
        cuerpo de máquina de estados; solo se limita a 1 iteración. Cero
            segunda implementación semántica, cero look-ahead.
        """
        # Conversion inicial: DataFrame -> MarketObject[] (si no vino ya como objetos).
    if isinstance(ltf_df_or_objs, pd.DataFrame):
        objs = _candle_objects(ltf_df_or_objs, ltf_tf)
    else:
        # M2 (2026-08-12): copy_objs controla si recreamos una copia superficial
        # de la coleccion en cada llamada. El motor SOLO LEE `objs` por indice
        # `<= i` (no hay append/pop/sort ni mutacion de elementos dentro del
        # loop), por lo que reutilizar la coleccion por referencia (copy_objs=False)
        # es semánticamente idéntico y elimina el O(n) por llamada. El default
        # True preserva el comportamiento histórico hasta demostrar equivalencia.
        objs = list(ltf_df_or_objs) if copy_objs else ltf_df_or_objs

    state = initial_state if initial_state is not None else SequenceState()
    signals: list[dict] = []
    n = len(objs)
    phase_seen = {"SWEEP": 0, "DISPLACE": 0, "BOS": 0, "ENTRY": 0}
    # B3: reglas de invalidacion congeladas por nacimiento del expediente.
    # Se construyen al confirmar el sweep (build_rules) y se evaluan con
    # check_invalidation solo contra la barra i. Con el flag OFF, build_rules
    # no anade OPPOSITE_SWING_BREAK => comportamiento bit a bit identico.
    expedientes: list[Expediente] = []
    # Contexto de "memoria del humano": las 50 velas previas para medir el
    # rango promedio (matematica pura high-low, sin indicadores).
    CTX_WINDOW = 50

    for i in range(start_i + 1, (start_i + 2) if single_step else n):
        obj = objs[i]
        # Fase 1 (lectura multitemporal): si se pasó est_htf_ctx_fn, run_sequence
        # recibe el MultiTFContext completo y lo reduce al MISMO HTF de antes
        # (Opción A) vía extract_htf_layer. Sin esto, usa est_htf_fn legacy
        # (comportamiento idéntico al histórico).
        if est_htf_ctx_fn is not None:
            _ctx = est_htf_ctx_fn(i)
            est_htf = extract_htf_layer(_ctx, htf) if htf is not None else {}
        else:
            _ctx = None
            est_htf = est_htf_fn(i)
        htf_trend = str(est_htf.get("trend", "RANGING"))
        bias = htf_trend if htf_trend in ("BULLISH", "BEARISH") else "RANGING"
        if bias == "RANGING":
            state.reset()
            continue

        # Direccion objetivo segun sesgo (a-favor o contratendencia)
        target = _direction_from_bias(bias, cfg.counter_trend)
        if target == 0:
            state.reset()
            continue

        # BRECHA A1 (Opción B, filtro suave): la dirección objetivo debe
        # alinearse con la cascada top-down D1->H4->H1 del MultiTFContext
        # completo. Solo se aplica cuando el llamador pasó est_htf_ctx_fn
        # (modo multitemporal). Si es None (legacy sin contexto) el
        # comportamiento histórico queda INTACTO. El POI anclado NO es veto
        # (require_pd=False): según auditoría destruye edge; se usa como
        # bonus/anotación, no como gate duro.
        if est_htf_ctx_fn is not None and _ctx is not None:
            from engine.plan import top_down_allows_trade
            _ok, _reason = top_down_allows_trade(
                _ctx, target, counter_trend=cfg.counter_trend, require_pd=False,
            )
            if not _ok:
                # Veta la dirección que choca con la cascada y reinicia la
                # secuencia (no cambia la lógica interna del SETUP).
                state.htf_aligned = False
                state.htf_reason = _reason
                state.reset()
                continue

        # Si la secuencia en curso es de distinta direccion, reinicia
        if state.phase != "IDLE" and state.direction != target:
            state.reset()

        # Memoria de zona: recordar la ULTIMA vela con FVG/OB entre el sweep y
        # el BOS (el FVG/OB NO esta en la vela del BOS). Se congela en BOS_DONE
        # para que el cuadro no se mueva mientras se espera el retorno.
        if state.phase in ("SWEEP_DONE", "DISPLACE_DONE"):
            # Fidelidad ICT (tesis 18): la zona LTF (FVG/OB) solo se traza como
            # cuadro de entrada si el HTF tiene un POI en esa direccion. Sin
            # guarda (htf_poi_fn=None) el comportamiento es el historico.
            # POI anclado = motor (engine.poi_anchor). Anota poi_present (bool)
            # para metadata; NO es gate duro (el veto destruye edge).
            if htf_poi_fn is not None:
                state.poi_present = bool(htf_poi_fn(i, target))
            else:
                state.poi_present = None
            # Hook historico: poi_ok decide si se memoriza la zona LTF. Con
            # htf_poi_fn=None es no-op (comportamiento historico intacto).
            poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))
            if poi_ok:
                _fvg = _latest_fvg_zone(obj, target)
                _ob = _latest_ob_zone(obj, target)
                _zone_obj = None
                if _fvg is not None:
                    state.zone_high, state.zone_low = _fvg
                    state.zone_pd_type = str(obj.meta.get("pd_type", "FVG"))
                    state.zone_pd_tier = str(obj.meta.get("pd_tier", "T2"))
                elif _ob is not None:
                    state.zone_high, state.zone_low = _ob
                    state.zone_pd_type = str(obj.meta.get("pd_type", "OB"))
                    state.zone_pd_tier = str(obj.meta.get("pd_tier", "T2"))
                # zone_authority eliminado del backtest: era ornamento del
                # backtest (tier/stacking). El motor es la unica fuente.
                state.zone_authority = None

        if state.phase == "IDLE":
            if _has_sweep(obj, est_htf, target):
                state.phase = "SWEEP_DONE"
                state.direction = target
                state.sweep_idx = i
                state.note("SWEEP", i)
                # B5: Expediente nace con el sweep (Ley 7 unicidad por id hash).
                # Fase 5/6 (Arq A): guarda el id del evento SWEEP para enlazar hijos.
                # Fase 6: crea LIQUIDITY (raiz) y enlaza SWEEP -> LIQUIDITY.
                _liq_level = (float(obj.meta.get("ssl_price", np.nan)) if target == 1
                              else float(obj.meta.get("bsl_price", np.nan)))
                _liq_obj = _make_event_object(
                    obj.meta.get("symbol", "") or "", ltf_tf, "LIQUIDITY",
                    target, i, obj.meta.get("time"), _liq_level, "",
                    {"phase": "LIQUIDITY",
                     "kind": "SSL" if target == 1 else "BSL"},
                    role="CONTEXT", obj_type="LIQUIDITY")
                state.liquidity_id = _liq_obj.id
                state.event_objs[_liq_obj.id] = _liq_obj
                _exp, _sweep_obj = _build_expediente(
                    obj.meta.get("symbol", "") or "",
                    ltf_tf, target, i, obj.meta.get("time"),
                    ("SWEEP_DOWN@LTF" if target == 1 else "SWEEP_UP@LTF"),
                    liquidity_id=_liq_obj.id,
                )
                # Fase 6: registra LIQUIDITY en el Expediente (ya existe _exp) antes del SWEEP.
                _advance_expediente(_exp, "LIQUIDITY", i, obj.meta.get("time"),
                                    event_id=_liq_obj.id, parent_event_id="")
                state.expediente = _exp
                state.sweep_id = _sweep_obj.id
                state.event_objs[_sweep_obj.id] = _sweep_obj
                # B3: congela las reglas de invalidacion en el nacimiento.
                # build_rules usa estructura pura cerrada hasta el sweep.
                state.invalidation_rules = build_rules(
                    direction=target,
                    sweep_idx=i,
                    sweep_time=obj.meta.get("time"),
                    ltf_df=(ltf_df_or_objs if isinstance(ltf_df_or_objs, pd.DataFrame) else None),
                    htf_df=None,
                    htf=htf,
                    cfg=cfg,
                )
                if state.expediente is not None:
                    state.expediente.invalidation_rule = "; ".join(
                        r.descr for r in state.invalidation_rules
                    )
                phase_seen["SWEEP"] += 1
        elif state.phase == "SWEEP_DONE":
            if i - state.sweep_idx > cfg.displace_gap:
                if _check_and_apply_invalidation(state, obj, i):
                    expedientes.append(state.expediente)  # type: ignore[arg-type]
                state.reset()
                continue
            if (not cfg.require_displacement) or _has_displacement(obj, target, est_htf):
                state.phase = "DISPLACE_DONE"
                state.displace_idx = i
                state.note("DISPLACE", i)
                # Fase 5 (Arq A): evento DISPLACEMENT, padre = SWEEP ya confirmado.
                _level = float(obj.meta.get("close", np.nan))
                _disp_obj = _make_event_object(
                    obj.meta.get("symbol", "") or "", ltf_tf, "DISPLACEMENT",
                    target, i, obj.meta.get("time"), _level, state.sweep_id,
                    {"phase": "DISPLACE"})
                state.displace_id = _disp_obj.id
                state.event_objs[_disp_obj.id] = _disp_obj
                _advance_expediente(state.expediente, "DISPLACE", i, obj.meta.get("time"),
                                    event_id=_disp_obj.id, parent_event_id=state.sweep_id)
                phase_seen["DISPLACE"] += 1
        elif state.phase == "DISPLACE_DONE":
            if i - state.displace_idx > _effective_bos_gap(cfg, i, obj, est_htf, objs, bos_table):
                if _check_and_apply_invalidation(state, obj, i):
                    expedientes.append(state.expediente)  # type: ignore[arg-type]
                state.reset()
                continue
            if _has_bos(obj, est_htf, target, cfg.counter_trend):
                # Secuencia canonica BOS->CHOCH->BOS (libro 02 §3.1): en
                # contratendencia exigir CHOCH (giro) ANTES del BOS de confirmacion.
                if cfg.counter_trend and not _has_choch(obj, est_htf, target, cfg.counter_trend):
                    continue
                state.phase = "BOS_DONE"
                state.bos_idx = i
                try:
                    state.bos_level = float(obj.meta.get("bos_level", np.nan))
                except (TypeError, ValueError):
                    state.bos_level = float("nan")
                # Fase 5 (Arq A): evento BOS, padre = DISPLACEMENT ya confirmado.
                _bos_obj = _make_event_object(
                    obj.meta.get("symbol", "") or "", ltf_tf, "BOS",
                    target, i, obj.meta.get("time"), state.bos_level, state.displace_id,
                    {"phase": "BOS"})
                state.bos_id = _bos_obj.id
                state.event_objs[_bos_obj.id] = _bos_obj
                # Fase 6: POI institucional HTF (role=POI) anclado al BOS padre ya
                # cerrado, y REFINEMENT LTF (role=REFINEMENT, la zona FVG/OB) hijo
                # del POI. Si no hay POI HTF anclado (htf_poi_fn=None o False), el
                # REFINEMENT LTF se ancla directo al BOS (sin inventar POI).
                # ONTología DURA: el POI institucional SOLO existe en HTF (D1/H4/H1).
                # Si el llamador no pasó un TF HTF real (htf=None), NO se crea POI
                # (evita ValueError en MarketObject y respeta la restricción de capa).
                _poi_anchored = bool(htf_poi_fn is not None and htf_poi_fn(i, target))
                _have_htf = bool(htf) and str(htf).upper() in _POI_TFS
                if _poi_anchored and _have_htf:
                    _poi_obj = _make_event_object(
                        obj.meta.get("symbol", "") or "", htf, "POI",
                        target, i, obj.meta.get("time"), state.bos_level, state.bos_id,
                        {"phase": "POI", "anchored": True},
                        role="POI", obj_type="BOS")
                    state.poi_id = _poi_obj.id
                    state.event_objs[_poi_obj.id] = _poi_obj
                    _ref_parent = _poi_obj.id
                else:
                    state.poi_id = ""
                    _ref_parent = state.bos_id
                # REFINEMENT LTF = zona FVG/OB ya cacheada (zone_high/zone_low).
                _ref_obj = _make_event_object(
                    obj.meta.get("symbol", "") or "", ltf_tf,
                    state.zone_pd_type if state.zone_pd_type in ("FVG", "ORDER_BLOCK") else "ORDER_BLOCK",
                    target, i, obj.meta.get("time"),
                    (state.zone_high + state.zone_low) / 2.0 if (np.isfinite(state.zone_high) and np.isfinite(state.zone_low)) else state.bos_level,
                    _ref_parent,
                    {"phase": "REFINEMENT", "pd_type": state.zone_pd_type,
                     "poi_anchored": _poi_anchored},
                    role="REFINEMENT", obj_type=state.zone_pd_type if state.zone_pd_type in ("FVG", "ORDER_BLOCK") else "ORDER_BLOCK")
                state.refinement_id = _ref_obj.id
                state.event_objs[_ref_obj.id] = _ref_obj
                # Fase 6: el Expediente debe contar la historia COMPLETA (Director §4).
                # POI y REFINEMENT se confirman en el instante del BOS (mismo idx,
                # ya validado por la guarda anti-look-ahead de advance).
                if _poi_anchored:
                    _advance_expediente(state.expediente, "POI", i, obj.meta.get("time"),
                                        event_id=_poi_obj.id, parent_event_id=state.bos_id)
                _advance_expediente(state.expediente, "REFINEMENT", i, obj.meta.get("time"),
                                    event_id=_ref_obj.id, parent_event_id=_ref_parent)
                # TRAZAR EL CUADRO: usar la zona cacheada (FVG/OB del tramo
                # sweep->displacement, memoria arriba), NO la vela del BOS donde
                # el imbalance ya no esta. El trader marca ese cuadro y ESPERA
                # el retorno (mitigation). Fallback: nivel del BOS +- 0.5 * rango
                # promedio (meta["atr"] ya es avg_candle_range, fuente unica de
                # volatilidad; migrado de ATR a rango puro, Fase 1).
                if not (np.isfinite(state.zone_high) and np.isfinite(state.zone_low)):
                    # CASO LIMITE (FVG-coincidente-con-BOS): la zona LTF puede
                    # caer en la MISMA vela que el BOS, donde la rama de
                    # memorizacion (SWEEP_DONE/DISPLACE_DONE) ya no corre. Se
                    # intenta la vela del BOS y la inmediatamente ANTERIOR (ambas
                    # ya cerradas -> anti look-ahead preservado). Cubre setups
                    # ICT reales.
                    for _ji in (state.bos_idx, state.bos_idx - 1):
                        if _ji < 0 or _ji >= len(objs):
                            continue
                        _prev = objs[_ji]
                        _pf = _latest_fvg_zone(_prev, target)
                        _po = _latest_ob_zone(_prev, target)
                        if _pf is not None:
                            state.zone_high, state.zone_low = _pf
                            state.zone_pd_type = str(_prev.meta.get("pd_type", "FVG"))
                            break
                        elif _po is not None:
                            state.zone_high, state.zone_low = _po
                            state.zone_pd_type = str(_prev.meta.get("pd_type", "OB"))
                            break
                    # Fallback historico: nivel del BOS +- 0.5 * rango promedio
                    # (meta["atr"] ya es avg_candle_range; migrado de ATR a rango
                    # puro, Fase 1).
                    if not (np.isfinite(state.zone_high) and np.isfinite(state.zone_low)):
                        _atr = obj.meta.get("atr", np.nan)
                        try:
                            atr = float(_atr) if _atr is not None else float("nan")
                        except (TypeError, ValueError):
                            atr = float("nan")
                        if np.isfinite(atr) and np.isfinite(state.bos_level):
                            state.zone_high = state.bos_level + 0.5 * atr
                            state.zone_low = state.bos_level - 0.5 * atr
                state.note("BOS", i)
                _advance_expediente(state.expediente, "BOS", i, obj.meta.get("time"),
                                    event_id=_bos_obj.id, parent_event_id=state.displace_id)
                phase_seen["BOS"] += 1
        elif state.phase == "BOS_DONE":
            if i - state.bos_idx > _effective_bos_gap(cfg, i, obj, est_htf, objs, bos_table):
                if _check_and_apply_invalidation(state, obj, i):
                    expedientes.append(state.expediente)  # type: ignore[arg-type]
                state.reset()
                continue
            # ENTRADA = el precio RETORNA al cuadro trazado (mitigation), no FVG instantaneo.
            if _touches_zone(obj, state.zone_high, state.zone_low):
                # SENAL: la secuencia completa ocurrio en orden y el precio
                # volvio al cuadro (igual que el trader que espera el toque).
                zone_auth = getattr(state, "zone_authority", None)
                _poi_present = getattr(state, "poi_present", None)
                # B5: cierra el expediente (ENTRY) y lo adjunta a la señal.
                _exp = state.expediente
                if _exp is not None:
                    # Fase 5/6 (Arq A): evento RETURN, padre = REFINEMENT (no BOS).
                    _ret_obj = _make_event_object(
                        obj.meta.get("symbol", "") or "", ltf_tf, "RETURN",
                        target, i, obj.meta.get("time"),
                        float(obj.meta.get("close", np.nan)), state.refinement_id or state.bos_id,
                        {"phase": "ENTRY", "poi_anchored": bool(state.poi_id)})
                    state.entry_id = _ret_obj.id
                    state.event_objs[_ret_obj.id] = _ret_obj
                    _advance_expediente(_exp, "ENTRY", i, obj.meta.get("time"),
                                        event_id=_ret_obj.id, parent_event_id=state.refinement_id or state.bos_id)
                    _exp.outcome = "ENTRY"
                    # CONTRACT (contratacion LTF): nodo SEPARADO hijo del RETURN.
                    # NO mezcla sus niveles con los eventos de formacion. Empaqueta
                    # entry/sl/tp (geometria LTF pura; exec fino opcional).
                    _ct = _build_ltf_contract(
                        state, objs, obj, ltf_tf, target, cfg, exec_frames)
                    _ct_obj = _make_event_object(
                        obj.meta.get("symbol", "") or "", _ct["exec_tf"], "CONTRACT",
                        target, i, obj.meta.get("time"), _ct["entry"],
                        state.entry_id,
                        {"phase": "CONTRACT", "entry": _ct["entry"], "sl": _ct["sl"],
                         "tp": _ct["tp"], "rr": _ct["rr"], "exec_tf": _ct["exec_tf"],
                         "fine": _ct["fine"], "poi_anchored": bool(state.poi_id)},
                        role="EXECUTION", obj_type="CONTRACT")
                    state.contract_id = _ct_obj.id
                    state.event_objs[_ct_obj.id] = _ct_obj
                    _advance_expediente(_exp, "CONTRACT", i, obj.meta.get("time"),
                                        event_id=_ct_obj.id, parent_event_id=state.entry_id)
                    expedientes.append(_exp)
                signals.append({
                    "time": str(obj.meta.get("time")),
                    "direction": target,
                    "entry": float(obj.meta.get("close")),
                    "bos_level": state.bos_level,
                    "sweep_at": state.sweep_idx,
                    "displace_at": state.displace_idx,
                    "bos_at": state.bos_idx,
                    "entry_at": i,
                    "zone_authority": zone_auth,
                    "poi_present": _poi_present,
                    "htf_aligned": state.htf_aligned,
                    "htf_reason": state.htf_reason,
                    # Fase 5/6 (Arq A): ids de eventos + niveles derivables (aditivo).
                    "event_ids": {
                        "LIQUIDITY": state.liquidity_id,
                        "SWEEP": state.sweep_id,
                        "DISPLACE": state.displace_id,
                        "BOS": state.bos_id,
                        "POI": state.poi_id,
                        "REFINEMENT": state.refinement_id,
                        "RETURN": state.entry_id,
                        "CONTRACT": state.contract_id,
                    },
                    "levels": {
                        "liquidity": (float(objs[state.sweep_idx].meta.get("ssl_price", np.nan))
                                      if target == 1 else
                                      float(objs[state.sweep_idx].meta.get("bsl_price", np.nan))
                                      ) if state.sweep_idx >= 0 else float("nan"),
                        "sweep": (float(objs[state.sweep_idx].meta.get("low", np.nan))
                                  if target == 1 else
                                  float(objs[state.sweep_idx].meta.get("high", np.nan))
                                  ) if state.sweep_idx >= 0 else float("nan"),
                        "displace": float(objs[state.displace_idx].meta.get("close", np.nan))
                        if state.displace_idx >= 0 else float("nan"),
                        "bos": state.bos_level,
                        "zone_high": state.zone_high,
                        "zone_low": state.zone_low,
                    },
                    # B5: Expediente adjunto (Ley 8 trazabilidad). No altera la
                    # firma vieja; es metadata extra dentro de la señal.
                    "expediente": _exp,
                    # M2 (SDD_M2_LINEAGE): grafo causal real de objetos, snapshot
                    # inmutable en el instante de señal. Permite a un consumidor
                    # puro reconstruir la cadena por parent_object (origen), no por
                    # proximidad temporal. Aditivo: run_sequence 2-tuple intacto.
                    "event_objects": {
                        _id: _o.to_dict() for _id, _o in state.event_objs.items()
                    },
                })
                state.note("ENTRY", i)
                phase_seen["ENTRY"] += 1
                state.reset()  # una secuencia por senal
    return signals, phase_seen, expedientes, state


def run_sequence(ltf_df_or_objs: Any, est_htf_fn, cfg: SequenceConfig,
                htf_poi_fn=None, ltf_tf: str = "M15", bos_table: dict | None = None,
                htf_pd_index=None, ltf_map: dict | None = None,
                htf: str | None = None,
                est_htf_ctx_fn=None, exec_frames: dict | None = None):
    """Wrapper 2-tuple (signals, phase_seen) - firma legacy preservada.

    El motor autónomo usa _run_sequence_impl (4-tuple); aquí se descartan los
    expedientes y el estado para no romper llamadores existentes.
    """
    s, p, _, _ = _run_sequence_impl(
        ltf_df_or_objs, est_htf_fn, cfg,
        htf_poi_fn=htf_poi_fn, ltf_tf=ltf_tf, bos_table=bos_table,
        htf_pd_index=htf_pd_index, ltf_map=ltf_map,
        htf=htf, est_htf_ctx_fn=est_htf_ctx_fn, exec_frames=exec_frames,
    )
    return s, p


def run_sequence_traced(ltf_df_or_objs: Any, est_htf_fn, cfg: SequenceConfig,
                        htf_poi_fn=None, ltf_tf: str = "M15", bos_table: dict | None = None,
                        htf_pd_index=None, ltf_map: dict | None = None,
                        htf: str | None = None,
                        est_htf_ctx_fn=None, exec_frames: dict | None = None,
                        initial_state=None, start_i: int = 0,
                        copy_objs: bool = True):
    """B1: (signals, phase_seen, expedientes, state) - trazabilidad + estado.

    Devuelve el SequenceState final para persistencia (HYP-002 M3). El llamador
    puede pasar initial_state+start_i para reanudar tras un crash.

    Opción B (2026-08-14): usa SequenceRunner (misma lógica que step(i)),
    garantizando una sola implementación de la máquina de estados.
    """
    # Conversion inicial: DataFrame -> MarketObject[] (si no vino ya como objetos).
    if isinstance(ltf_df_or_objs, pd.DataFrame):
        objs = _candle_objects(ltf_df_or_objs, ltf_tf)
    else:
        objs = list(ltf_df_or_objs) if copy_objs else ltf_df_or_objs
    runner = SequenceRunner(
        objs, est_htf_ctx_fn, cfg, ltf_tf=ltf_tf, htf=htf,
        htf_poi_fn=htf_poi_fn, bos_table=bos_table, htf_pd_index=htf_pd_index,
        ltf_map=ltf_map, exec_frames=exec_frames, initial_state=initial_state)
    return runner.run_all(start_i=start_i)


class SequenceRunner:
    """Opción B (Change Gate Mayor 2026-08-14, autorizado por Director).

    Runner incremental vela-a-vela para replay/streaming. Mantiene el estado
    absoluto del motor y expone step(i) que procesa SOLO la transición de la
    vela i (O(1) por llamada, O(N) total). NO es un segundo motor: step(i)
    delega en _run_sequence_impl con single_step=True, el MISMO cuerpo de
    máquina de estados. Índices absolutos intactos (objs completo, no sublista).

    Garantía de una sola lógica: run_sequence_traced() usa SequenceRunner en su
    loop interno, por lo que batch y streaming comparten idéntico código.
    """

    def __init__(self, objs, est_htf_ctx_fn, cfg, ltf_tf="M15", htf=None,
                 htf_poi_fn=None, bos_table=None, htf_pd_index=None,
                 ltf_map=None, exec_frames=None, initial_state=None):
        # objs es la lista COMPLETA de MarketObject[] (índices absolutos).
        self.objs = list(objs) if not isinstance(objs, list) else objs
        self.est_htf_ctx_fn = est_htf_ctx_fn
        self.cfg = cfg
        self.ltf_tf = ltf_tf
        self.htf = htf
        self.htf_poi_fn = htf_poi_fn
        self.bos_table = bos_table
        self.htf_pd_index = htf_pd_index
        self.ltf_map = ltf_map
        self.exec_frames = exec_frames
        self.state = initial_state if initial_state is not None else SequenceState()
        self.signals: list[dict] = []
        self.phase_seen = {"SWEEP": 0, "DISPLACE": 0, "BOS": 0, "ENTRY": 0}
        self.expedientes: list = []

    def step(self, i: int):
        """Procesa SOLO la transición de la vela i (índice absoluto).

        Usa single_step=True: _run_sequence_impl itera range(i, i+1).
        El estado se acumula entre llamadas (initial_state=self.state).
        """
        sigs, phase, exp, state = _run_sequence_impl(
            self.objs, None, self.cfg,
            htf_poi_fn=self.htf_poi_fn, ltf_tf=self.ltf_tf,
            bos_table=self.bos_table, htf_pd_index=self.htf_pd_index,
            ltf_map=self.ltf_map, htf=self.htf,
            est_htf_ctx_fn=self.est_htf_ctx_fn, exec_frames=self.exec_frames,
            initial_state=self.state, start_i=i - 1, single_step=True,
            copy_objs=False,
        )
        self.state = state
        self.signals.extend(sigs)
        for k in self.phase_seen:
            self.phase_seen[k] += phase.get(k, 0)
        self.expedientes.extend(exp)
        return sigs

    def run_all(self, start_i: int = 0, end_i: int | None = None):
        """Conveniencia: corre step(i) para i en [start_i+1, end_i)."""
        n = len(self.objs)
        end = n if end_i is None else min(end_i, n)
        for i in range(start_i + 1, end):
            self.step(i)
        return self.signals, self.phase_seen, self.expedientes, self.state
