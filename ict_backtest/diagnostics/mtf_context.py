"""Fase D — Adaptador multi-TF: normaliza el snapshot closed-only de
``ict_backtest/v2/context_mtf`` al schema de diagnóstico de Ruben.

NO recalcula nada ni mixea clocks: solo traduce el stack (que ya es
closed-only anti look-ahead) a ``MarketContextFrame`` por TF, con los campos
que pidió Ruben:

    D1 : bias, structure, premium_discount
    H4 : bias, structure, poi
    H1 : structure, liquidity
    M15: setup, sweep, displacement, bos, fvg, ob
    M5 : confirmation, micro_structure
    M1 : execution, entry_quality

Regla #4: si el stack marca ``available=False`` para un TF, el frame queda
``available=False`` y TODOS sus campos de contenido en ``MISSING`` (nunca se
copian de otro TF ni se inventan).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ict_backtest.diagnostics.trade_context import MarketContextFrame


_MISSING = "MISSING"


def _norm_str(v: Any, default: str = _MISSING) -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _norm_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _frame_from_snapshot(tf: str, snap: dict[str, Any]) -> MarketContextFrame:
    """Traduce un snapshot de context_mtf a MarketContextFrame según el rol del TF."""
    if not snap.get("available", False):
        # Regla #4: nada inventado. Campos de contenido en MISSING.
        return MarketContextFrame(
            tf=tf,
            available=False,
            bias=_MISSING,
            structure=_MISSING,
            premium_discount=_MISSING,
            poi=_MISSING,
            liquidity=_MISSING,
            setup=_MISSING,
            setup_sweep=_MISSING,
            setup_displacement=_MISSING,
            setup_bos=_MISSING,
            setup_fvg=_MISSING,
            setup_ob=_MISSING,
            confirmation=_MISSING,
            micro_structure=_MISSING,
            execution=_MISSING,
            entry_quality=_MISSING,
        )

    trend = _norm_str(snap.get("trend"), "RANGING")
    bos_dir = _norm_int(snap.get("bos_dir"), 0)
    bos = "BULLISH" if bos_dir > 0 else "BEARISH" if bos_dir < 0 else "NONE"
    choch = _norm_str(snap.get("choch"), "NONE")
    sweep_up = bool(snap.get("sweep_up", False))
    sweep_down = bool(snap.get("sweep_down", False))
    sweep = "UP" if sweep_up else "DOWN" if sweep_down else "NONE"

    # fvg/ob: el snapshot de context_mtf hoy trae trend/bos/choch/sweep;
    # fvg/ob viven en la fila cruda. Los leemos del snapshot ampliado si
    # viene (run_backtest los inyecta); si no, quedan como datos reales vacíos.
    fvg = _norm_str(snap.get("fvg_state"), "NONE")
    ob = _norm_str(snap.get("ob_dir"), "NONE")

    base = dict(
        tf=tf,
        available=True,
        bias=trend,
        structure=bos if bos != "NONE" else choch if choch != "NONE" else "NONE",
        premium_discount=_norm_str(snap.get("pd_side"), "UNKNOWN"),
        poi=_norm_str(snap.get("pd_side"), "UNKNOWN"),
        liquidity="BSL/SSL" if (sweep_up or sweep_down) else "NONE",
        setup=_norm_str(snap.get("setup"), "NONE"),
        setup_sweep=sweep,
        setup_displacement=_norm_str(snap.get("displacement"), "NONE"),
        setup_bos=bos,
        setup_fvg=fvg,
        setup_ob=ob,
    )

    if tf in ("M1", "M5"):
        base.update(
            confirmation=trend,
            micro_structure=bos if bos != "NONE" else "NONE",
            execution="CLOSED_BAR" if snap.get("time") else "NONE",
            entry_quality="AT_CLOSE" if snap.get("time") else "NONE",
        )
    else:
        base.update(
            confirmation=_MISSING,
            micro_structure=_MISSING,
            execution=_MISSING,
            entry_quality=_MISSING,
        )
    return MarketContextFrame(**base)


def normalize_mtf_stack(stack: dict[str, Any]) -> dict[str, MarketContextFrame]:
    """Convierte el stack de ``context_mtf.build_context_stack`` en
    ``{tf: MarketContextFrame}`` ordenado D1→M1."""
    order = ("D1", "H4", "H1", "M15", "M5", "M1")
    out: dict[str, MarketContextFrame] = {}
    for tf in order:
        snap = stack.get(tf)
        if snap is None:
            out[tf] = MarketContextFrame(tf=tf, available=False)
        else:
            out[tf] = _frame_from_snapshot(tf, snap)
    # cualquier TF extra que no esté en la lista (p.ej. M30) se conserva
    for tf, snap in stack.items():
        if tf not in out:
            out[tf] = _frame_from_snapshot(tf, snap)
    return out
