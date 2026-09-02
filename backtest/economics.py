"""Deterministic economic accounting for the PASS_EDGE intraday contract.

This module does not create signals or resolve OHLC outcomes.  It converts a
technical outcome into a net-R record using a frozen, explicit cost scenario.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EconomicScenario:
    """All monetary assumptions required for one EURUSD proxy scenario."""

    spread_pips: float
    slippage_pips: float
    commission_per_lot_side: float
    lot_size: float = 1.0
    contract_size: float = 100_000.0
    pip_size: float = 0.0001

    def __post_init__(self) -> None:
        if self.spread_pips < 0 or self.slippage_pips < 0:
            raise ValueError("spread and slippage must be non-negative")
        if self.commission_per_lot_side < 0 or self.lot_size <= 0:
            raise ValueError("commission must be non-negative and lot size positive")
        if self.contract_size <= 0 or self.pip_size <= 0:
            raise ValueError("contract size and pip size must be positive")


def account_trade_economics(
    trade: dict[str, Any], scenario: EconomicScenario
) -> dict[str, Any]:
    """Return a copy of *trade* with auditable gross/cost/net-R fields.

    ``exit_r`` is the technical gross R emitted by the causal outcome
    resolver.  Invalid or open outcomes remain economically unresolved rather
    than being silently converted to zero.
    """

    result = dict(trade)
    gross_r = trade.get("exit_r")
    entry = trade.get("entry")
    sl = trade.get("sl")
    if gross_r is None or entry is None or sl is None:
        result.update({"gross_pnl_cash": None, "initial_risk_cash": None,
                       "cost_cash": None, "net_R": None,
                       "economic_status": "UNRESOLVED_TECHNICAL_OUTCOME"})
        return result

    risk_price = abs(float(entry) - float(sl))
    if risk_price <= 0:
        raise ValueError("trade initial risk must be positive")
    units = scenario.lot_size * scenario.contract_size
    initial_risk_cash = risk_price * units
    gross_pnl_cash = float(gross_r) * initial_risk_cash
    pip_cash = scenario.pip_size * units
    spread_cash = scenario.spread_pips * pip_cash
    slippage_cash = scenario.slippage_pips * pip_cash
    commission_cash = 2.0 * scenario.commission_per_lot_side * scenario.lot_size
    cost_cash = spread_cash + slippage_cash + commission_cash
    result.update({
        "gross_pnl_cash": gross_pnl_cash,
        "initial_risk_cash": initial_risk_cash,
        "spread_cash": spread_cash,
        "slippage_cash": slippage_cash,
        "commission_cash": commission_cash,
        "cost_cash": cost_cash,
        "net_R": (gross_pnl_cash - cost_cash) / initial_risk_cash,
        "economic_status": "RESOLVED",
        "economic_scenario": {
            "spread_pips": scenario.spread_pips,
            "slippage_pips": scenario.slippage_pips,
            "commission_per_lot_side": scenario.commission_per_lot_side,
            "lot_size": scenario.lot_size,
            "contract_size": scenario.contract_size,
            "pip_size": scenario.pip_size,
        },
    })
    return result
