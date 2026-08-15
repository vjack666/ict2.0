"""Fase E — cohorts.py (helper puro, sin lógica de trading).

Funciones que reciben UN TradeContext v2 y devuelven una FACETA leída de
``market_context``. Solo LECTURA. No usan ``pnl_r`` ni nada post-cierre: el
contexto ya está congelado en la entrada (anti look-ahead, regla R4 /
condición #1/#2 de Ruben). Si un TF no está disponible => "unknown".

Toda faceta es una categoría de string para que statistics_engine agrupe.
"""

from __future__ import annotations

from typing import Optional

from ict_backtest.diagnostics.trade_context import TradeContext, MarketContextFrame


def _frame(ctx: TradeContext, tf: str) -> Optional[MarketContextFrame]:
    mc = ctx.market_context or {}
    f = mc.get(tf)
    if f is None or not f.available:
        return None
    return f


def htf_alignment(ctx: TradeContext) -> str:
    """D1/H4/H1 mismo bias direccional => 'aligned'; si no 'not'; falta => 'unknown'."""
    biases = []
    for tf in ("D1", "H4", "H1"):
        f = _frame(ctx, tf)
        if f is None:
            return "unknown"
        biases.append(f.bias)
    first = biases[0]
    if first == "RANGING":
        return "not"
    return "aligned" if all(b == first for b in biases) else "not"


def has_htf_poi(ctx: TradeContext) -> str:
    """H4.poi anclado (PD) => 'yes'; si no 'no'; falta => 'unknown'."""
    f = _frame(ctx, "H4")
    if f is None:
        return "unknown"
    return "yes" if f.poi == "PD" else "no"


def m5_confirms(ctx: TradeContext) -> str:
    """M5.confirmation alineado con dirección de entrada => 'yes'/'no'/'unknown'."""
    f = _frame(ctx, "M5")
    if f is None:
        return "unknown"
    if ctx.direction > 0:
        return "yes" if f.confirmation == "BULLISH" else "no"
    if ctx.direction < 0:
        return "yes" if f.confirmation == "BEARISH" else "no"
    return "unknown"


def m1_clean(ctx: TradeContext) -> str:
    """M1.micro_structure alineado con dirección de entrada => 'yes'/'no'/'unknown'."""
    f = _frame(ctx, "M1")
    if f is None:
        return "unknown"
    if ctx.direction > 0:
        return "yes" if f.micro_structure == "BULLISH" else "no"
    if ctx.direction < 0:
        return "yes" if f.micro_structure == "BEARISH" else "no"
    return "unknown"


def d1_pd_state(ctx: TradeContext) -> str:
    """D1.premium_discount: DISCOUNT/PREMIUM/PD/EQ; falta => 'unknown'."""
    f = _frame(ctx, "D1")
    if f is None:
        return "unknown"
    return f.premium_discount  # DISCOUNT / PREMIUM / PD / EQ
