"""Isolated economic backtest consumer for six-TF Episodes.

This module consumes already-built six-timeframe Episodes.  It does not create
signals, does not mutate the engine, and does not authorize trading.  The entry
model is intentionally explicit and diagnostic: enter at the M1 close available
at ``decision_time``, use a fixed risk in pips, and resolve SL/TP on future M1
bars only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import pandas as pd

from backtest.economics import EconomicScenario, account_trade_economics


@dataclass(frozen=True)
class SixTFBacktestConfig:
    risk_pips: float = 10.0
    reward_r: float = 2.0
    horizon_m1_bars: int = 240
    tie_policy: str = "pessimistic"

    def __post_init__(self) -> None:
        if self.risk_pips <= 0:
            raise ValueError("risk_pips must be positive")
        if self.reward_r <= 0:
            raise ValueError("reward_r must be positive")
        if self.horizon_m1_bars <= 0:
            raise ValueError("horizon_m1_bars must be positive")
        if self.tie_policy not in {"pessimistic", "optimistic"}:
            raise ValueError("tie_policy must be pessimistic or optimistic")


def _utc(value: Any) -> pd.Timestamp:
    result = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(result):
        raise ValueError(f"invalid timestamp: {value!r}")
    return result


def _m1_entry(m1: pd.DataFrame, decision_time: Any) -> tuple[int, pd.Series]:
    cutoff = _utc(decision_time)
    times = pd.to_datetime(m1["time"], utc=True, errors="coerce")
    prefix = m1.loc[times <= cutoff].reset_index(drop=True)
    if prefix.empty:
        raise ValueError("MISSING_M1_ENTRY_BAR")
    return len(prefix) - 1, prefix.iloc[-1]


def _future_m1(m1: pd.DataFrame, decision_time: Any, horizon: int) -> pd.DataFrame:
    cutoff = _utc(decision_time)
    times = pd.to_datetime(m1["time"], utc=True, errors="coerce")
    future = m1.loc[times > cutoff].copy().reset_index(drop=True)
    return future.head(horizon)


def _resolve_exit(
    future: pd.DataFrame,
    *,
    direction: int,
    sl: float,
    tp: float,
    tie_policy: str,
) -> dict[str, Any]:
    for index, row in future.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        hit_sl = low <= sl if direction > 0 else high >= sl
        hit_tp = high >= tp if direction > 0 else low <= tp
        if hit_sl and hit_tp:
            exit_r = -1.0 if tie_policy == "pessimistic" else abs(tp - float(row["open"])) / abs(float(row["open"]) - sl)
            return {
                "exit_status": "TIE_" + tie_policy.upper(),
                "exit_time": _utc(row["time"]).isoformat(),
                "exit_bar_offset": int(index) + 1,
                "exit_price": sl if tie_policy == "pessimistic" else tp,
                "exit_r": exit_r if tie_policy == "pessimistic" else 1.0,
            }
        if hit_sl:
            return {
                "exit_status": "SL",
                "exit_time": _utc(row["time"]).isoformat(),
                "exit_bar_offset": int(index) + 1,
                "exit_price": sl,
                "exit_r": -1.0,
            }
        if hit_tp:
            return {
                "exit_status": "TP",
                "exit_time": _utc(row["time"]).isoformat(),
                "exit_bar_offset": int(index) + 1,
                "exit_price": tp,
                "exit_r": 1.0,
            }
    if future.empty:
        return {
            "exit_status": "UNRESOLVED_NO_FUTURE_M1",
            "exit_time": None,
            "exit_bar_offset": None,
            "exit_price": None,
            "exit_r": None,
        }
    last = future.iloc[-1]
    return {
        "exit_status": "HORIZON",
        "exit_time": _utc(last["time"]).isoformat(),
        "exit_bar_offset": len(future),
        "exit_price": float(last["close"]),
        "exit_r": None,
    }


def backtest_episode(
    episode: Mapping[str, Any],
    m1: pd.DataFrame,
    *,
    config: SixTFBacktestConfig,
    economics: EconomicScenario,
) -> dict[str, Any]:
    direction = int(episode["direction"])
    decision_time = _utc(episode["decision_time"])
    entry_index, entry_bar = _m1_entry(m1, decision_time)
    entry = float(entry_bar["close"])
    risk = config.risk_pips * economics.pip_size
    if direction > 0:
        sl = entry - risk
        tp = entry + risk * config.reward_r
    else:
        sl = entry + risk
        tp = entry - risk * config.reward_r
    future = _future_m1(m1, decision_time, config.horizon_m1_bars)
    resolved = _resolve_exit(
        future,
        direction=direction,
        sl=sl,
        tp=tp,
        tie_policy=config.tie_policy,
    )
    trade = {
        "episode_id": episode["episode_id"],
        "decision_time": decision_time.isoformat(),
        "entry_time": _utc(entry_bar["time"]).isoformat(),
        "entry_bar_index": int(entry_index),
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "risk_pips": config.risk_pips,
        "reward_r": config.reward_r,
        "horizon_m1_bars": config.horizon_m1_bars,
        "component_tfs": dict(episode.get("component_tfs", {})),
        "object_refs": list(episode.get("object_refs", [])),
        **resolved,
    }
    return account_trade_economics(trade, economics)


def backtest_episodes(
    episodes: Iterable[Mapping[str, Any]],
    m1: pd.DataFrame,
    *,
    config: SixTFBacktestConfig,
    economics: EconomicScenario,
) -> list[dict[str, Any]]:
    return [
        backtest_episode(episode, m1, config=config, economics=economics)
        for episode in episodes
    ]


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = [trade for trade in trades if trade.get("net_R") is not None]
    wins = [trade for trade in resolved if float(trade["net_R"]) > 0]
    losses = [trade for trade in resolved if float(trade["net_R"]) <= 0]
    net_rs = [float(trade["net_R"]) for trade in resolved]
    gross_rs = [float(trade["exit_r"]) for trade in resolved if trade.get("exit_r") is not None]
    return {
        "trade_count": len(trades),
        "resolved_count": len(resolved),
        "unresolved_count": len(trades) - len(resolved),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": len(wins) / len(resolved) if resolved else None,
        "mean_net_R": sum(net_rs) / len(net_rs) if net_rs else None,
        "sum_net_R": sum(net_rs) if net_rs else 0.0,
        "mean_gross_R": sum(gross_rs) / len(gross_rs) if gross_rs else None,
        "exit_status_counts": {
            status: sum(1 for trade in trades if trade.get("exit_status") == status)
            for status in sorted({str(trade.get("exit_status")) for trade in trades})
        },
    }


__all__ = [
    "SixTFBacktestConfig",
    "backtest_episode",
    "backtest_episodes",
    "summarize_trades",
]
