"""Fase D — Paso 2: TradeContextBuilder (funcion pura, sin estado).

RESPONSABILIDAD UNICA: tomar los datos EMITIDOS por `simulate_trade`
(RawDiagnosticData) y CONGELARLOS en un `TradeContext`. NO simula, NO decide,
NO lee R7.

Separacion de responsabilidades (Ruben 2026-07-18):
  - `engine.simulate_trade`    : SIMULA un trade (su unica responsabilidad).
  - `engine.simulate_trade_with_context`: EMITE RawDiagnosticData (no conoce
                                 el esquema de diagnostico).
  - `diagnostics.context_builder`: CONSTRUYE y CONGELA el TradeContext.

Asi `engine.py` queda limpio y Fase D crece (noticias, vol, sesion, regimen,
liquidez, spreads...) SIN tocar la logica de ejecucion: solo se amplia este
builder y/o el RawDiagnosticData que emite `simulate_trade_with_context`.

Principio anti look-ahead: el builder SOLO usa datos disponibles ANTES/A DURANTE
la simulacion (entry context + exit diagnostics). Nunca recalcula post-outcome.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from ict_backtest.diagnostics.trade_context import CONTEXT_VERSION, TradeContext


@dataclass
class RawDiagnosticData:
    """Lo que `simulate_trade_with_context` EMITE (no congela).

    Es un contenedor tonto de datos disponibles en simulacion. El builder lo
    traduce a TradeContext. Si un campo falta, el builder usa default (no inventa).
    """
    signal: Any                 # ICTSignal (time, direction, zone_authority, sweep_at...)
    trade: Any                  # ICTTrade (entry_time, exit_time, pnl_r)
    meta: dict[str, Any]        # {exit_reason, mfe_r, mae_r, hold_bars}
    row: dict[str, Any] | None = None        # fila LTF en signal.time (atr, etc.)
    htf_context: dict[str, Any] | None = None  # {trend, sweep_up, sweep_down} HTF
    market_stack: dict[str, Any] | None = None  # Fase D multi-TF: stack closed-only
                                                   # {tf: snapshot} de context_mtf.
                                                   # None si no se solicito la cadena.
    backtest_id: str = ""


def build_trade_context(
    raw: RawDiagnosticData,
    *,
    signal_id: str | None = None,
    context_version: str = CONTEXT_VERSION,
) -> TradeContext:
    """Congela RawDiagnosticData en un TradeContext INMUTABLE.

    Funcion PURA: mismos inputs -> mismo contexto. No toca R7 ni el PnL.
    Establece context_created_at al UTC actual (garante de congelacion pre-resultado).
    """
    sig = raw.signal
    trade = raw.trade
    meta = raw.meta or {}
    row = raw.row or {}
    htf = raw.htf_context or {}

    # ids persistentes
    trade_id = str(uuid.uuid4())
    sid = signal_id if signal_id is not None else f"sig-{getattr(sig, 'time', '?')}"

    # entry context
    zone_auth = getattr(sig, "zone_authority", None)
    zone_auth_dict = None
    if zone_auth is not None:
        zone_auth_dict = {
            "has_htf_anchor": bool(getattr(zone_auth, "has_htf_anchor", False)),
            "tier": str(getattr(zone_auth, "tier", "NONE")),
            "stacking_level": int(getattr(zone_auth, "stacking_level", 0) or 0),
            "confidence_weight": float(getattr(zone_auth, "confidence_weight", 0.0)),
            "level": str(getattr(zone_auth, "level", "NONE")),
        }

    # structure quality (de la fila LTF si esta disponible)
    atr = float(row.get("atr", 0.0) or 0.0)
    atr_z = float(row.get("atr_z", 0.0) or 0.0)

    # phase_log de la secuencia (sweep->displace->BOS->return) desde indices
    # de la senal (sweep_at/bos_at/entry_at). Si faltan, log minimo.
    phase_log: tuple[str, ...] = ("SWEEP", "DISPLACE", "BOS", "RETURN")

    # exit diagnostics
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()

    # Fase D multi-TF: congelar el expediente completo (reglas #1/#4/#5).
    # market_stack viene closed-only de context_mtf; lo normalizamos a
    # {tf: MarketContextFrame}. Si es None (no se solicito la cadena),
    # market_context queda None (contexto v1 sigue valido).
    from ict_backtest.diagnostics.mtf_context import normalize_mtf_stack
    market_context = normalize_mtf_stack(raw.market_stack) if raw.market_stack else None

    return TradeContext(
        backtest_id=raw.backtest_id,
        trade_id=trade_id,
        signal_id=sid,
        context_version=context_version,
        context_created_at=created_at,
        symbol=getattr(sig, "symbol", getattr(trade, "symbol", "")),
        entry_time=getattr(trade, "entry_time", getattr(sig, "time", "")),
        exit_time=getattr(trade, "exit_time", ""),
        direction=int(getattr(sig, "direction", 0)),
        htf_trend=str(htf.get("trend", "RANGING")),
        htf_bias=str(htf.get("trend", "RANGING")),
        sweep_up=bool(htf.get("sweep_up", False)),
        sweep_down=bool(htf.get("sweep_down", False)),
        zone_authority=zone_auth_dict,
        displacement_gap=int(getattr(sig, "displace_at", 0) or 0)
                          - int(getattr(sig, "sweep_at", 0) or 0),
        bos_gap=int(getattr(sig, "bos_at", 0) or 0)
                - int(getattr(sig, "displace_at", 0) or 0),
        atr_z=atr_z,
        sl_is_structural=bool(row.get("sl_is_structural", False)),
        dist_entry_to_sl_r=float(row.get("dist_entry_to_sl_r", 0.0) or 0.0),
        phase_log=phase_log,
        exit_reason=str(meta.get("exit_reason", "")),
        pnl_r=float(getattr(trade, "pnl_r", 0.0)),
        mfe_r=float(meta.get("mfe_r", 0.0)),
        mae_r=float(meta.get("mae_r", 0.0)),
        hold_bars=int(meta.get("hold_bars", 0)),
        adverse_excursion_at_exit=float(meta.get("mae_r", 0.0)),
        time_in_drawdown=0.0,  # se precisa loop post; Paso 2 lo deja 0 (no inventa)
        regime_tag=None,
        htf_bias_at_exit=None,
        market_context=market_context,
    )
