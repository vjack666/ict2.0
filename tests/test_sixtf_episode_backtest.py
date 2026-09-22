from __future__ import annotations

import pandas as pd
import pytest

from backtest.economics import EconomicScenario
from backtest.sixtf_episode_backtest import (
    SixTFBacktestConfig,
    backtest_episode,
    summarize_trades,
)


def _m1(prices: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"time": ts, "open": o, "high": h, "low": l, "close": c, "volume": 100.0}
            for ts, o, h, l, c in prices
        ]
    )


def _episode(direction: int = 1) -> dict:
    return {
        "episode_id": "EP_TEST",
        "decision_time": "2026-01-01T00:00:00Z",
        "direction": direction,
        "component_tfs": {
            "context_htf": "D1",
            "poi": "H4",
            "refinement": "M15",
            "confirmation": "M5",
            "trigger": "M1",
        },
        "object_refs": ["D1", "H4", "M15", "M5", "M1"],
    }


def test_sixtf_episode_backtest_resolves_tp_and_costs():
    frame = _m1(
        [
            ("2026-01-01T00:00:00Z", 1.1000, 1.1002, 1.0998, 1.1000),
            ("2026-01-01T00:01:00Z", 1.1000, 1.1021, 1.0999, 1.1020),
        ]
    )
    trade = backtest_episode(
        _episode(1),
        frame,
        config=SixTFBacktestConfig(risk_pips=10.0, reward_r=2.0, horizon_m1_bars=5),
        economics=EconomicScenario(1.0, 0.3, 5.0),
    )

    assert trade["exit_status"] == "TP"
    assert trade["exit_r"] == pytest.approx(1.0)
    assert trade["net_R"] == pytest.approx(0.77)
    assert trade["economic_status"] == "RESOLVED"
    assert trade["component_tfs"]["trigger"] == "M1"


def test_sixtf_episode_backtest_preserves_unresolved_horizon():
    frame = _m1(
        [
            ("2026-01-01T00:00:00Z", 1.1000, 1.1002, 1.0998, 1.1000),
            ("2026-01-01T00:01:00Z", 1.1000, 1.1002, 1.0998, 1.1000),
        ]
    )
    trade = backtest_episode(
        _episode(-1),
        frame,
        config=SixTFBacktestConfig(risk_pips=10.0, reward_r=2.0, horizon_m1_bars=1),
        economics=EconomicScenario(1.0, 0.3, 5.0),
    )

    assert trade["exit_status"] == "HORIZON"
    assert trade["net_R"] is None
    assert trade["economic_status"] == "UNRESOLVED_TECHNICAL_OUTCOME"


def test_sixtf_backtest_summary_counts_resolved_and_unresolved():
    summary = summarize_trades(
        [
            {"net_R": 0.5, "exit_r": 1.0, "exit_status": "TP"},
            {"net_R": -1.2, "exit_r": -1.0, "exit_status": "SL"},
            {"net_R": None, "exit_r": None, "exit_status": "HORIZON"},
        ]
    )

    assert summary["trade_count"] == 3
    assert summary["resolved_count"] == 2
    assert summary["unresolved_count"] == 1
    assert summary["win_rate"] == 0.5
    assert summary["sum_net_R"] == pytest.approx(-0.7)
