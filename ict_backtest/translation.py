"""ict_backtest/translation.py — capa de traduccion DataFrame <-> MarketObject.

ESCUDO de compatibilidad (REVISION_ARQUITECTURA_CONVIVENCIA.md):
- objects_to_legacy_df: desde MarketObject reconstruye las columnas sueltas
  que hoy leen sequence/rules/engine/ML/UI. Asi NADIE se entera del cambio.
- df_to_objects (Tarea B.2): desde {tf: df} produce MarketObject con
  origin_tf sellado y role por regla de capa.

El objeto nuevo vive "debajo" como fuente canonica; las columnas son una
VISTA reconstruida, no la verdad.
"""

from __future__ import annotations

import pandas as pd

from ict_backtest.market_object import (
    MarketObject,
    ObjectType,
    Role,
    ObjectState,
)


# Capas que cuentan como HTF para la regla de POI/CONTEXT (ontologia).
_HTF_TFS = {"D1", "H4", "H1"}


# Mapeo de estado (objeto -> columna legacy). Ver ontologia §5 y pipeline.
_STATE_TO_STATUS = {
    ObjectState.ACTIVE: "active",
    ObjectState.CREATED: "active",      # aun no mitigado = vigente
    ObjectState.MITIGATED: "active",   # sigue vigente hasta consumo/invalid
    ObjectState.CONSUMED: "active",    # ya operado; pipeline no lo filtra
    ObjectState.INVALIDATED: "none",   # compatible con bos_alive de pipeline
}


# Columnas ICT que el motor (sequence/engine/rules) lee del df y que deben
# sobrevivir al round-trip objeto<->columna SIN reinterpretación.
_LEGACY_COLS = (
    "bos_direction", "bos_status", "choch_dir", "choch_status",
    "fvg_state", "fvg_bullish", "fvg_bearish", "ob_direction",
    "ob_bullish", "ob_bearish", "ob_status", "macro_direction",
)


def objects_to_legacy_df(objects: list[MarketObject]) -> pd.DataFrame:
    """Reconstruye el dict de columnas sueltas desde MarketObjects.

    FIDELIDAD R9: si el objeto trae las columnas ICT en `meta` (las que puso
    el detector original), se devuelven TAL CUAL. Solo se recae en la lógica
    derivada si la columna no está en meta. Así el puente objeto<->columna es
    un round-trip perfecto y sequence no cambia de comportamiento.
    """
    rows: list[dict] = []
    for o in objects:
        t = o.type.value
        is_bos = t == "BOS"
        is_choch = t == "CHOCH"
        is_fvg = t == "FVG"
        is_ob = t == "ORDER_BLOCK"
        meta = o.meta or {}
        rows.append({
            "type": t,
            "origin_tf": o.origin_tf,
            "role": o.role.value,
            "direction": o.direction,
            "bos_direction": meta.get("bos_direction", o.direction if is_bos else 0),
            "bos_status": meta.get("bos_status", _STATE_TO_STATUS.get(o.state, "none")),
            "choch_dir": meta.get("choch_dir", o.direction if is_choch else 0),
            "choch_status": meta.get("choch_status", _STATE_TO_STATUS.get(o.state, "none") if is_choch else "-"),
            "fvg_state": meta.get("fvg_state", (t if is_fvg else "-")),
            "fvg_bullish": meta.get("fvg_bullish", (is_fvg and o.direction == 1)),
            "fvg_bearish": meta.get("fvg_bearish", (is_fvg and o.direction == -1)),
            "ob_direction": meta.get("ob_direction", (t if is_ob else "-")),
            "ob_bullish": meta.get("ob_bullish", (is_ob and o.direction == 1)),
            "ob_bearish": meta.get("ob_bearish", (is_ob and o.direction == -1)),
            "ob_status": meta.get("ob_status", _STATE_TO_STATUS.get(o.state, "none") if is_ob else "-"),
            "macro_direction": meta.get("macro_direction", (t if (is_bos or is_choch) else "-")),
            "zone_high": o.zone_high,
            "zone_low": o.zone_low,
            "quality_score": o.quality_score,
        })
    return pd.DataFrame(rows)


def df_to_objects(frames: dict[str, pd.DataFrame],
                   symbol: str = "") -> list[MarketObject]:
    """Desde {tf: df con columnas de detectores} produce MarketObjects.

    SELLA la capa (origen) y aplica la regla de rol:
    - HTF (D1/H4/H1): FVG/OB -> POI; BOS/CHOCH -> CONTEXT.
    - LTF (M15/M5/M3/M1): FVG/OB/BOS/CHOCH -> REFINEMENT (nunca POI).

    Reusa las columnas que build_features ya calculo (bos_direction,
    fvg_bullish, etc.). No reescribe los detectores: solo los ENVUELVE en
    objetos con identidad. Es el unico punto de verdad del sello de capa.
    """
    objs: list[MarketObject] = []
    for tf, df in frames.items():
        htf = tf in _HTF_TFS
        for idx, row in df.iterrows():
            # SWEEP (libro 05): la mecha que tomo liquidez. Objeto PERSISTENTE
            # con zona = nivel de la mecha. Fuente unica: canonical_sweep
            # (columnas liquidity_sweep_* ya presentes en el df via detect_bos).
            # No se crea detector paralelo; se reusa la columna existente.
            sd = bool(row.get("liquidity_sweep_down", False))
            su = bool(row.get("liquidity_sweep_up", False))
            if sd or su:
                # sweep_down barre SSL => setup LONG (+1); sweep_up barre BSL => SHORT (-1).
                # Coherente con sequence._has_sweep (long busca sweep_down).
                direction = 1 if sd else -1
                side = "down" if sd else "up"
                # Zona = mecha de la vela que barrio la liquidez (high/low reales).
                # No depende de sweep_high/low (no siempre presentes); la mecha
                # de la vela sweep ES el nivel de liquidez tomada.
                z_high = float(row.get("high", 0.0) or 0.0)
                z_low = float(row.get("low", 0.0) or 0.0)
                objs.append(MarketObject(
                    type=ObjectType.SWEEP, origin_tf=tf,
                    # El sweep es raiz de liquidez: en HTF actua como CONTEXT,
                    # en LTF como REFINEMENT (nunca POI).
                    role=Role.CONTEXT if htf else Role.REFINEMENT,
                    direction=direction, symbol=symbol, state=ObjectState.ACTIVE,
                    bar_index=int(idx), bar_time=row.get("time"),
                    zone_high=z_high, zone_low=z_low,
                    meta={"sweep_side": side,
                          "liquidity_sweep_down": sd,
                          "liquidity_sweep_up": su},
                ))
            bd = int(row.get("bos_dir", 0) or 0)
            if bd != 0:
                objs.append(MarketObject(
                    type=ObjectType.BOS, origin_tf=tf,
                    role=Role.CONTEXT if htf else Role.REFINEMENT,
                    direction=bd, symbol=symbol, state=ObjectState.ACTIVE,
                    bar_index=int(idx), bar_time=row.get("time"),
                    zone_high=float(row.get("high", 0.0) or 0.0),
                    zone_low=float(row.get("low", 0.0) or 0.0),
                    meta={"bos_dir": bd,
                          "bos_direction": row.get("bos_direction", "NONE"),
                          "bos_status": row.get("bos_status", "active"),
                          "macro_direction": row.get("macro_direction", row.get("trend", "-"))},
                ))
            cd = int(row.get("choch_dir", 0) or 0)
            if cd != 0:
                objs.append(MarketObject(
                    type=ObjectType.CHOCH, origin_tf=tf,
                    role=Role.CONTEXT if htf else Role.REFINEMENT,
                    direction=cd, symbol=symbol, state=ObjectState.ACTIVE,
                    bar_index=int(idx), bar_time=row.get("time"),
                    zone_high=float(row.get("high", 0.0) or 0.0),
                    zone_low=float(row.get("low", 0.0) or 0.0),
                    meta={"choch_dir": cd,
                          "choch_signal": row.get("choch_signal", "NONE"),
                          "choch_status": row.get("choch_status", "active"),
                          "macro_direction": row.get("macro_direction", row.get("trend", "-"))},
                ))
            fb = bool(row.get("fvg_bullish", False))
            fbe = bool(row.get("fvg_bearish", False))
            if fb or fbe:
                d = 1 if fb else -1
                objs.append(MarketObject(
                    type=ObjectType.FVG, origin_tf=tf,
                    # POI solo en HTF (regla dura de capa).
                    role=Role.POI if htf else Role.REFINEMENT,
                    direction=d, symbol=symbol, state=ObjectState.ACTIVE,
                    bar_index=int(idx), bar_time=row.get("time"),
                    zone_high=float(row.get("high", 0.0) or 0.0),
                    zone_low=float(row.get("low", 0.0) or 0.0),
                    meta={"fvg_state": row.get("fvg_state", "bullish" if fb else "bearish"),
                          "fvg_bullish": fb, "fvg_bearish": fbe,
                          "pd_type": row.get("pd_type", "FVG"),
                          "pd_tier": row.get("pd_tier", "T2")},
                ))
            obb = bool(row.get("ob_bullish", False))
            obbe = bool(row.get("ob_bearish", False))
            if obb or obbe:
                d = 1 if obb else -1
                objs.append(MarketObject(
                    type=ObjectType.ORDER_BLOCK, origin_tf=tf,
                    role=Role.POI if htf else Role.REFINEMENT,
                    direction=d, symbol=symbol, state=ObjectState.ACTIVE,
                    bar_index=int(idx), bar_time=row.get("time"),
                    zone_high=float(row.get("high", 0.0) or 0.0),
                    zone_low=float(row.get("low", 0.0) or 0.0),
                    meta={"ob_direction": row.get("ob_direction", "bullish" if obb else "bearish"),
                          "ob_bullish": obb, "ob_bearish": obbe,
                          "ob_status": row.get("ob_status", "active"),
                          "pd_type": row.get("pd_type", "OB"),
                          "pd_tier": row.get("pd_tier", "T2")},
                ))
    return objs
