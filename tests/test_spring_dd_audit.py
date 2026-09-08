from tools.spring_dd_audit import RiskConfig, TradeOutcome, classify_trade, summarize


def test_risk_limits_are_five_k_and_three_percent():
    risk = RiskConfig()
    assert risk.stop_usd == 150.0
    assert risk.take_profit_usd == 60.0


def test_stop_has_priority_when_both_levels_are_touched():
    outcome = classify_trade(1.1000, [1.1100], [1.0800])
    assert outcome.pnl_usd == -150.0


def test_summary_reports_drawdown():
    result = summarize([TradeOutcome(1.1, 20, 3, 60), TradeOutcome(1.1, 2, 20, -150)])
    assert result["final_balance"] == 4910.0
    assert result["max_drawdown_usd"] == 150.0
