from backtest.economics import EconomicScenario, account_trade_economics
import pytest


def test_proxy_scenario_accounts_round_turn_costs_in_net_r():
    trade = {"entry": 1.1000, "sl": 1.0990, "exit_r": 2.0}
    scenario = EconomicScenario(
        spread_pips=1.0, slippage_pips=0.3, commission_per_lot_side=5.0
    )
    result = account_trade_economics(trade, scenario)
    assert result["initial_risk_cash"] == pytest.approx(100.0)
    assert result["gross_pnl_cash"] == pytest.approx(200.0)
    assert result["cost_cash"] == pytest.approx(23.0)
    assert result["net_R"] == pytest.approx(1.77)


def test_unresolved_outcome_does_not_become_zero():
    result = account_trade_economics(
        {"entry": 1.1, "sl": 1.099, "exit_r": None},
        EconomicScenario(1.0, 0.3, 5.0),
    )
    assert result["net_R"] is None
    assert result["economic_status"] == "UNRESOLVED_TECHNICAL_OUTCOME"
