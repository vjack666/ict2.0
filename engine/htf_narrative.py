"""engine/htf_narrative.py — NARRATIVA UNIFICADA HTF (Deuda 5).

Une los pedazos sueltos del motor ICT en UNA sola "idea del día":

    liquidez (objetivo)  ->  displacement/BOS  ->  POI (OB)  ->  premium/discount

Contrato:
  ENT: velas cerradas (open/high/low/close) del TF de trabajo.
  SAL: dict con bias, zona del dealing range, objetivo de liquidez, POI y un
       `summary` legible en español.
  CRIT: geometría pura reutilizando los módulos existentes del motor.
        SIN indicadores (no ATR, no EMA). `engine/` NUNCA importa `ict_backtest/`.
"""

from __future__ import annotations

import pandas as pd

from engine.bias.narrative import BEARISH, BULLISH, NEUTRAL, HtfBias, compute_htf_bias
from engine.bos import StructureConfig, detect_market_structure
from engine.dealing_range import dealing_range_htf
from engine.liquidity_levels import nearest_liquidity_target
from engine.order_block import order_block_for_bos
from engine.poi_anchor import make_htf_poi_fn  # ancla narrativa (Brecha B)
from engine.htf_pd_index import HtfPdIndex      # indice PD arrays HTF (rescate)
from engine.zone_authority import evaluate_zone_authority, HtfPdZone

# FVG como POI alternativo es OPCIONAL: si el módulo no existe, se ignora.
try:  # pragma: no cover - depende de si engine.fvg_poi está presente
    from engine.fvg_poi import fvg_for_bos  # type: ignore
except Exception:  # pragma: no cover
    fvg_for_bos = None  # type: ignore[assignment]

__all__ = ["build_htf_narrative", "narrative_ready_for_trade"]


def _resolve_bias(frame: pd.DataFrame, htf_bias=None) -> HtfBias:
    """Sesgo HTF vigente. Si no se pasa uno, se deriva del propio frame.

    El frame de trabajo hace de proxy de D1/H4/H1 (misma geometría de swings);
    así la narrativa es autocontenida sin importar el backtest.

    REGLA EXP-012 (camino B): el sesgo es SIEMPRE canónico (sin gate). El gate
    vive solo en detect_market_structure (estructura LTF/entrada); censurarlo
    aquí desalineaba sesgo↔estructura (ver results/motor_veltick_EURUSD_M15.json).
    """
    if htf_bias is not None:
        return htf_bias
    if frame is None or len(frame) < 3:
        return HtfBias(d1=NEUTRAL, h4=NEUTRAL, h1=NEUTRAL)
    return compute_htf_bias(frame, frame, frame)


def _last_bos_event(frame: pd.DataFrame, exp012: bool = False) -> dict | None:
    """Último BOS del frame: {'index': i, 'direction': BULLISH|BEARISH}.

    Con exp012=True aplica el gate EXP-012 (solo CHOCH reales cuentan).
    """
    if frame is None or len(frame) < 3:
        return None
    try:
        structure = detect_market_structure(frame, StructureConfig(exp012_choch=exp012))
    except Exception:
        return None
    # detect_market_structure devuelve el frame con índice 0..n-1.
    bos = pd.Series(structure.frame["bos_dir"]).fillna(0).to_numpy()
    positions = [i for i, v in enumerate(bos) if int(v) != 0]
    if not positions:
        return None
    pos = positions[-1]
    raw = int(bos[pos])
    return {"index": pos, "direction": BULLISH if raw == 1 else BEARISH}


def _fmt(value) -> str:
    """Formato compacto de precio para el resumen."""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "?"


def _build_summary(bias: str, zone: str, liq: dict, poi: dict | None) -> str:
    """Resumen legible en español de la idea del día."""
    partes = [f"Sesgo {bias} en {zone}"]

    side = liq.get("side", "NONE")
    if side != "NONE" and liq.get("level") is not None:
        partes.append(f"objetivo {side} {_fmt(liq['level'])}")
    else:
        partes.append("sin objetivo de liquidez")

    if poi:
        tipo = poi.get("kind", "OB")
        anclado = "anclado HTF" if poi.get("anchored") else "sin anclar"
        bottom = poi.get("ob_bottom", poi.get("fvg_bottom"))
        top = poi.get("ob_top", poi.get("fvg_top"))
        partes.append(f"POI {tipo} {_fmt(bottom)}-{_fmt(top)} {anclado}")
    else:
        partes.append("sin POI")

    return "; ".join(partes)


def build_htf_narrative(
    frame: pd.DataFrame,
    lookback: int = 10,
    htf_bias=None,
    htf_frames: dict[str, pd.DataFrame] | None = None,
    exp012: bool = True,
) -> dict:
    """Mapa ICT completo de la vela actual (la idea del dia).

    Args:
        frame: TF de trabajo (proxy de D1/H4/H1 si no se pasa htf_frames).
        lookback: ventana de dealing range.
        htf_bias: sesgo HTF precomputado (opcional).
        htf_frames: dict {tf: DataFrame} de los TF padre (D1/H4/H1). Si se
            pasa, el POI se marca 'anchored' segun si hay BOS/CHOCH padre en
            la misma direccion ya cerrado (Brecha B, tesis 18). Si es None,
            el ancla queda como False (no se puede evaluar).
        exp012: si True (default), expone el conteo de CHOCH EXP-012 (bonus de
            autoridad, brecha EXP-012 cerrada 2026-08-08) en la salida sin
            vetar el sesgo canonico. El observador lo pinta siempre.

    Returns:
        {'bias', 'is_favorable', 'zone', 'liquidity_target', 'poi', 'summary'}
    """
    # Sesgo SIEMPRE canónico (camino B): el flag exp012 solo controla la
    # pintura de auditoría choch_exp012 (abajo), no el sesgo.
    bias_obj = _resolve_bias(frame, htf_bias)
    direction = getattr(bias_obj, "direction", NEUTRAL) or NEUTRAL

    # 1) Donde esta el precio? premium/discount anclado al sesgo.
    dealing = dealing_range_htf(frame, bias_obj, lookback=lookback)
    # 2) Hacia donde va? objetivo de liquidez del dia.
    liquidity = nearest_liquidity_target(frame, bias_obj)
    # 3) Que rompio? ultimo BOS. 4) Desde donde? POI que lo origino.
    last_bos = _last_bos_event(frame, exp012=exp012)

    # Ancla narrativa: si tenemos los TF padre, construimos htf_poi_fn para
    # marcar el POI como anclado (bonus, no gate duro).
    htf_poi_fn = None
    htf_pd_index = None
    ltf_map = None
    if htf_frames:
        try:
            htf_poi_fn = make_htf_poi_fn(frame, htf_frames)
            # Indice de PD arrays HTF vigentes (rescate de la capa backtest).
            # Solo los TF que son padre (D1/H4/H1) y el propio frame LTF.
            _idx_frames = {tf: df for tf, df in htf_frames.items()
                           if tf in ("D1", "H4", "H1")}
            htf_pd_index = HtfPdIndex(_idx_frames)
            ltf_map = htf_pd_index.build_ltf_map(frame)
        except Exception:
            htf_poi_fn = None
            htf_pd_index = None
            ltf_map = None

    poi = None
    if last_bos is not None:
        poi = order_block_for_bos(frame, last_bos, bias_obj)
        if poi is not None:
            poi = {**poi, "kind": "OB"}
        elif fvg_for_bos is not None:  # POI alternativo opcional
            try:
                alt = fvg_for_bos(frame, last_bos, bias_obj)
            except Exception:
                alt = None
            if alt:
                poi = {**alt, "kind": "FVG"}
        # marcar ancla: el POI esta respaldado por BOS/CHOCH padre en la
        # direccion del setup (libro 21 sec4).
        if poi is not None and htf_poi_fn is not None:
            tnum = 1 if direction == BULLISH else (-1 if direction == BEARISH else 0)
            try:
                poi["anchored"] = bool(htf_poi_fn(len(frame) - 1, tnum))
            except Exception:
                poi["anchored"] = False
        elif poi is not None:
            poi["anchored"] = False
        # Enriquecer con AUTORIDAD CONTEXTUAL del POI (tier/stacking/peso).
        # NO es gate duro: es la medicion de calidad que la tesis 21 sec4 pide
        # como bonus. Respeta auditoria Fase E (POI-gate destruye edge).
        if poi is not None and htf_pd_index is not None and ltf_map is not None:
            try:
                _i = len(frame) - 1
                _ltf_zone = HtfPdZone(
                    tf=frame.attrs.get("tf", "LTF") if hasattr(frame, "attrs") else "LTF",
                    pd_type=poi.get("kind", "OB"),
                    pd_tier="T2",
                    direction=(1 if direction == BULLISH else -1),
                    zone_high=float(poi.get("ob_top", poi.get("fvg_top", float("nan")))),
                    zone_low=float(poi.get("ob_bottom", poi.get("fvg_bottom", float("nan")))),
                )
                _htf_zones: list[HtfPdZone] = []
                for _tf in htf_pd_index.timeframes:
                    _htf_zones.extend(htf_pd_index.zones_at(_i, _tf, ltf_map))
                _auth = evaluate_zone_authority(_ltf_zone, _htf_zones)
                poi["authority"] = {
                    "has_htf_anchor": _auth.has_htf_anchor,
                    "tier": _auth.tier,
                    "stacking_level": _auth.stacking_level,
                    "confidence_weight": _auth.confidence_weight,
                    "level": _auth.level,
                }
            except Exception:
                poi["authority"] = None

    zone = str(dealing.get("zone", "OTE_NONE"))
    is_favorable = bool(dealing.get("is_favorable", False))

    # EXP-012 (bonus de autoridad, no veta el sesgo canonico): conteo de CHOCH
    # reales en el frame. El observador lo pinta siempre (default exp012=True).
    choch_exp012 = None
    if exp012 and frame is not None and len(frame) >= 5:
        try:
            fr = detect_market_structure(
                frame, StructureConfig(exp012_choch=True)
            ).frame
            cnt = int(fr["choch_exp012"].sum())
            lvl = (
                float(fr.loc[fr["choch_exp012"] == 1, "choch_pivot_level"].iloc[-1])
                if (fr["choch_exp012"] == 1).any() else None
            )
            choch_exp012 = {"count": cnt, "last_level": lvl}
        except Exception:
            choch_exp012 = None

    return {
        "bias": direction,
        "is_favorable": is_favorable,
        "zone": zone,
        "liquidity_target": liquidity,
        "poi": poi,
        "last_bos": last_bos,
        "choch_exp012": choch_exp012,
        "summary": _build_summary(direction, zone, liquidity, poi),
    }


def narrative_ready_for_trade(narr: dict) -> bool:
    """True solo si el HTF está COMPLETO: sesgo + zona + POI + objetivo."""
    if not narr:
        return False
    if narr.get("bias", NEUTRAL) not in (BULLISH, BEARISH):
        return False
    if not narr.get("is_favorable"):
        return False
    if narr.get("poi") is None:
        return False
    liq = narr.get("liquidity_target") or {}
    return liq.get("side", "NONE") != "NONE"
