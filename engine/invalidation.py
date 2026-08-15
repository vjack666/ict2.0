"""engine/invalidation.py — Invalidacion predefinida y explicita (B3).

Ley 6 (invalidacion clara) + Ley 4 (geometria pura, sin indicadores).

Cada regla de invalidacion se CONGELA en el nacimiento del expediente (al
confirmarse el sweep): niveles y deadline fijos, derivados de estructura de
precio pura (swing opuesto, gap de tiempo). `check_invalidation` solo recibe
la vela EN CURSO (barra i, nunca i+1): es imposible recalcular swings con
datos posteriores al nacimiento (anti look-ahead).

Las reglas son el SUSTITUTO explicito de los resets hoy implicitos en
run_sequence:
  - TIMEOUT          : i - sweep_idx > gap (ventana de confirmacion vencida)
  - DIRECTION_FLIP   : el sesgo HTF cambia de direccion (top-down veto)
  - TOPDOWN_VETO     : la cascada D1->H4->H1 no permite la direccion objetivo
  - OPPOSITE_SWING_BREAK : el precio cierra mas alla del swing opuesto del
        setup (derrota de la estructura de entrada). NUEVA regla sustantiva,
        detras del flag `invalidate_on_opposite_swing` (OFF = bit a bit
        idéntico al historico).

Contrato anti-look-ahead (Ley 1): `build_rules` recibe el snapshot closed-
only del HTF en la vela del sweep; `check_invalidation` recibe SOLO el
MarketObject de la vela i. Ninguna regla lee el futuro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.bias.narrative import _swing_points
from engine.market_object import MarketObject


@dataclass
class InvalidationRule:
    """Una condicion de muerte predefinida para el expediente de la senal."""

    kind: str                       # TIMEOUT | DIRECTION_FLIP | TOPDOWN_VETO | OPPOSITE_SWING_BREAK
    level: float | None = None      # nivel de ruptura (solo OPPOSITE_SWING_BREAK)
    deadline_idx: int | None = None  # i maximo antes de timeout (solo TIMEOUT)
    descr: str = ""
    direction: int = 0              # direccion del setup (para OPPOSITE_SWING_BREAK)


def build_rules(
    *,
    direction: int,
    sweep_idx: int,
    sweep_time: Any,
    ltf_df: Any,
    htf_df: Any | None,
    htf: str | None,
    cfg,
) -> list[InvalidationRule]:
    """Congela las reglas de invalidacion en el nacimiento (sweep).

    `cfg` es SequenceConfig (de engine.sequence o ict_backtest.sequence); se
    leen `displace_gap`, `bos_gap`, `counter_trend` y el flag nuevo
    `invalidate_on_opposite_swing`. La regla OPPOSITE_SWING_BREAK se deriva
    del swing opuesto CONFIRMADO en el LTF cerrado hasta el sweep
    (engine.bias.narrative._swing_points): long -> ultimo swing low previo al
    sweep; short -> ultimo swing high previo. Si no hay swing opuesto aun,
    la regla no se crea (no inventa niveles).

    Regresion cero: con `invalidate_on_opposite_swing=False` (default) la
    lista NO contiene OPPOSITE_SWING_BREAK; las demas reglas son solo
    descriptivas y run_sequence las ignora salvo que se pasen por
    Expediente.invalidate (que hoy no ocurre en flujo happy-path).
    """
    rules: list[InvalidationRule] = []

    # TIMEOUT: deadline derivado de la ventana de confirmacion BOS efectiva.
    # Usamos el gap de BOS si esta fijo; si es dinamico (None) usamos un
    # fallback conservador igual al displace_gap + 40 (igual que sequence).
    bos_gap = getattr(cfg, "bos_gap", None)
    eff_bos_gap = bos_gap if bos_gap is not None else 40
    deadline = sweep_idx + max(getattr(cfg, "displace_gap", 6), eff_bos_gap)
    rules.append(InvalidationRule(
        kind="TIMEOUT",
        deadline_idx=deadline,
        descr=f"timeout si i-sweep_idx supera {deadline}",
    ))

    # Regla sustantiva nueva, detras de flag.
    if getattr(cfg, "invalidate_on_opposite_swing", False):
        level = _opposite_swing_level(ltf_df, sweep_idx, direction)
        if level is not None:
            rules.append(InvalidationRule(
                kind="OPPOSITE_SWING_BREAK",
                level=float(level),
                direction=int(direction),
                descr=(
                    f"precio cierra mas alla del swing opuesto "
                    f"{'low' if direction == 1 else 'high'} {level}"
                ),
            ))
    return rules


def _opposite_swing_level(ltf_df, sweep_idx: int, direction: int) -> float | None:
    """Nivel del swing opuesto CONFIRMADO cerrado hasta el sweep (Ley 4)."""
    if ltf_df is None or len(ltf_df) == 0:
        return None
    # Solo la porcion cerrada hasta el sweep (anti look-ahead).
    upto = ltf_df.iloc[: sweep_idx + 1] if sweep_idx + 1 <= len(ltf_df) else ltf_df
    if len(upto) < 3:
        return None
    sh, sl = _swing_points(upto)
    if direction == 1:
        # long: swing low opuesto (el suelo que no debe perderse)
        vals = [v for v in sl.dropna().values]
        return float(vals[-1]) if vals else None
    if direction == -1:
        vals = [v for v in sh.dropna().values]
        return float(vals[-1]) if vals else None
    return None


def check_invalidation(rules: list[InvalidationRule], bar: MarketObject, i: int):
    """Evalua las reglas contra la vela i. Devuelve la regla que mata, o None.

    Solo mira cierre/extremos de la barra i (nunca i+1). Para OPPOSITE_SWING_BREAK
    compara el cierre de la vela contra el nivel congelado.
    """
    if not rules:
        return None
    close = float(bar.meta.get("close", "nan"))
    high = float(bar.meta.get("high", "nan"))
    low = float(bar.meta.get("low", "nan"))
    for r in rules:
        if r.kind == "TIMEOUT":
            if r.deadline_idx is not None and i > r.deadline_idx:
                return r
        elif r.kind == "OPPOSITE_SWING_BREAK":
            if r.level is None:
                continue
            if r.direction == 1 and close < r.level:
                return r
            if r.direction == -1 and close > r.level:
                return r
        # DIRECTION_FLIP / TOPDOWN_VETO se evaluan en run_sequence (contexto
        # HTF), no contra la vela aislada; aqui pasan como no-disparadas.
        continue
    return None
