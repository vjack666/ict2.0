"""ict_backtest/costs.py — Tabla de costos de mercado reales (R6.3 / G3).

Costos en pips por símbolo (spread promedio + comisión ida/vuelta +
slippage adverso medio). Fuente: brokers típicos XAUUSD/EURUSD/GBPUSD.
Estos valores son referencia de producción; el runner los aplica por
DEFECTO. El modo teoría (sin costos) es opt-in via --no-cost.

No son constantes mágicas de estrategia: son el costo de transacción real
del mercado, igual que el spread que paga cualquier trader. Documentados
en un único sitio (PRINCIPIO: un número, un sitio -> METRICS_CANON).
"""

from __future__ import annotations

from typing import Any

# spread_pips:     medio spread en pips (XAU ~2-3, EURUSD ~1, GBPUSD ~1.2)
# commission_pips: comision ida+vuelta en pips
# slippage_pips:   slippage promedio adverso en pips
COST_BY_SYMBOL: dict[str, dict[str, float]] = {
    "XAUUSD": {"spread_pips": 3.0, "commission_pips": 0.7, "slippage_pips": 0.5},
    "EURUSD": {"spread_pips": 1.0, "commission_pips": 0.6, "slippage_pips": 0.3},
    "GBPUSD": {"spread_pips": 1.2, "commission_pips": 0.7, "slippage_pips": 0.4},
    "DEFAULT": {"spread_pips": 2.0, "commission_pips": 0.7, "slippage_pips": 0.5},
}


def resolve_cost(symbol: str, override: str | None = None,
                 no_cost: bool = False) -> dict[str, float] | None:
    """Resuelve el dict de costos para `symbol`.

    - no_cost=True  -> None (modo teoría, sin costos).
    - override="spread,commission,slippage" -> usa esos pips explicitos.
    - sino -> COST_BY_SYMBOL[symbol] o DEFAULT.
    """
    if no_cost:
        return None
    if override:
        sp, cp, slp = (float(x) for x in override.split(","))
        return {"spread_pips": sp, "commission_pips": cp, "slippage_pips": slp}
    return dict(COST_BY_SYMBOL.get(symbol, COST_BY_SYMBOL["DEFAULT"]))
