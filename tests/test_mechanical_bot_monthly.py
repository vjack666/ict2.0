from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from types import SimpleNamespace

import backtest.mechanical_bot_monthly as monthly
from engine.market_object import ObjectState, ObjectType

from backtest.mechanical_bot_monthly import (
    MonthlyBotConfig, MonthlyMechanicalBacktest, freeze_context, nightly_cutoff,
    session_windows, stochastic_cross, write_events_jsonl,
)

UTC = timezone.utc

def _frame(times, closes, highs=None, lows=None):
    highs = highs or [x + .0001 for x in closes]
    lows = lows or [x - .0001 for x in closes]
    return pd.DataFrame({"time": pd.to_datetime(times, utc=True), "open": closes, "high": highs, "low": lows, "close": closes})

def test_cutoff_is_prior_guayaquil_night_and_sessions_handle_dst():
    assert nightly_cutoff(date(2026, 8, 10)).isoformat() == "2026-08-10T01:00:00+00:00"
    london, ny = session_windows(date(2026, 8, 10))
    assert london.start.isoformat() == "2026-08-10T07:00:00+00:00"
    assert ny.start.isoformat() == "2026-08-10T12:00:00+00:00"
    winter_london, winter_ny = session_windows(date(2026, 1, 10))
    assert winter_london.start.hour == 8 and winter_ny.start.hour == 13

def test_freeze_context_consumes_engine_context_and_cannot_pass_future_bar(monkeypatch):
    cutoff = datetime(2026, 8, 10, 1, tzinfo=UTC)
    base = _frame(["2026-08-08", "2026-08-09", "2026-08-10"], [1.0, 1.1, 0.8])
    seen = []
    def detector(frame, _config):
        seen.append(frame.copy())
        return SimpleNamespace(frame=frame)
    stack = {tf: {"trend": "BULLISH", "available": True} for tf in ("D1", "H4", "H1", "M15")}
    zone = SimpleNamespace(type=ObjectType.FVG, direction=1, state=ObjectState.ACTIVE, zone_low=1.0, zone_high=1.1)
    monkeypatch.setattr(monthly, "detect_market_structure", detector)
    monkeypatch.setattr(monthly, "build_context_stack", lambda *_a, **_k: stack)
    monkeypatch.setattr(monthly, "top_down_allows_trade", lambda *_a, **_k: (True, "ok"))
    monkeypatch.setattr(monthly, "build_ltf_canonical_feed", lambda *_a, **_k: {"zones": {"M15": [zone]}})
    context = freeze_context({"D1": base, "H4": base, "H1": base, "M15": base}, cutoff)
    assert context.direction == "BUY" and context.fvg_direction == "BUY"
    assert pd.Timestamp("2026-08-10", tz="UTC") not in seen[0].time.tolist()  # D1 future bar excluded

def test_stochastic_cross_uses_closed_m15_and_direction():
    # crafted descending then recovery sequence produces a normal BUY cross.
    times = pd.date_range("2026-08-10", periods=39, freq="15min", tz="UTC")
    closes = [1.20 - i*.0005 for i in range(30)] + [1.187023, 1.186739, 1.189656, 1.189101, 1.185673, 1.185162, 1.185187, 1.184612, 1.186635]
    frame = _frame(times, closes)
    assert stochastic_cross(frame, "BUY")
    assert not stochastic_cross(frame, "SELL")

def test_cycle_ladder_and_loss_priority_and_jsonl(tmp_path):
    # Directly exercise basket management: 20/40 pips are measured from initial.
    frames = {tf: _frame(["2026-08-01", "2026-08-02"], [1.1, 1.2]) for tf in ("D1", "H4", "H1", "M15")}
    frames["M1"] = _frame(["2026-08-03 08:00", "2026-08-03 08:01", "2026-08-03 08:02"], [1.2, 1.2, 1.2], highs=[1.2, 1.2, 1.2], lows=[1.2, 1.198, 1.196])
    replay = MonthlyMechanicalBacktest(frames, MonthlyBotConfig(spread_pips=0, slippage_pips=0, commission_per_lot_side=0))
    replay._open_initial(datetime(2026, 8, 3, 8, tzinfo=UTC), 1.2, "BUY", "LONDON", datetime(2026, 8, 3, tzinfo=UTC))
    replay._manage_bar(datetime(2026, 8, 3, 8, 1, tzinfo=UTC), frames["M1"].iloc[1])
    replay._manage_bar(datetime(2026, 8, 3, 8, 2, tzinfo=UTC), frames["M1"].iloc[2])
    assert [e["volume"] for e in replay.events if e["kind"] == "REENTRY"] == [.2, .3]
    # A later candle spans both a gain and a loss threshold; loss wins.
    replay._manage_bar(datetime(2026, 8, 3, 8, 3, tzinfo=UTC), pd.Series({"high": 1.22, "low": 1.17}))
    close = [e for e in replay.events if e["kind"] == "CLOSE"][-1]
    assert close["reason"] == "max_floating_loss"
    assert close["session"] == "LONDON"
    output = tmp_path / "events.jsonl"
    write_events_jsonl(replay.events, output)
    assert len(output.read_text().splitlines()) == len(replay.events)


def test_close_records_all_execution_costs_including_spread_slippage_and_commission():
    frames = {tf: _frame(["2026-08-01", "2026-08-02"], [1.2, 1.2]) for tf in ("D1", "H4", "H1", "M15")}
    frames["M1"] = _frame(["2026-08-03 08:00"], [1.2])
    replay = MonthlyMechanicalBacktest(frames)
    replay._open_initial(datetime(2026, 8, 3, 8, tzinfo=UTC), 1.2, "BUY", "LONDON", datetime(2026, 8, 3, tzinfo=UTC))
    replay._close_cycle(datetime(2026, 8, 3, 8, 1, tzinfo=UTC), 1.2, "test")
    close = [event for event in replay.events if event["kind"] == "CLOSE"][-1]
    assert close["raw_gross_pnl_usd"] == 0.0
    assert round(close["execution_cost_usd"], 2) == 2.6
    assert round(close["net_pnl_usd"], 2) == -2.6


def test_run_reports_daily_progress():
    frames = {tf: _frame(["2026-07-30", "2026-07-31", "2026-08-01"], [1.0, 1.1, 1.2]) for tf in ("D1", "H4", "H1", "M15")}
    frames["M1"] = _frame(["2026-08-01 07:00", "2026-08-01 08:00"], [1.1, 1.1])
    seen = []
    MonthlyMechanicalBacktest(frames).run(date(2026, 8, 1), date(2026, 8, 1), progress=lambda day, index, total: seen.append((day, index, total)))
    assert seen == [(date(2026, 8, 1), 1, 1)]







def test_window_manages_open_basket_after_entry_in_same_session(monkeypatch):
    # The historical implementation returned immediately after opening; this
    # proves that following M1 bars still close a reached aggregate TP.
    m15_times = pd.date_range("2026-08-03 03:00", periods=20, freq="15min", tz="UTC")
    frames = {tf: _frame(["2026-08-01", "2026-08-02"], [1.1, 1.2]) for tf in ("D1", "H4", "H1")}
    frames["M15"] = _frame(m15_times, [1.2] * len(m15_times))
    frames["M1"] = _frame(
        ["2026-08-03 07:00", "2026-08-03 07:01", "2026-08-03 07:02", "2026-08-03 07:03"],
        [1.2] * 4, highs=[1.2, 1.2, 1.207, 1.2], lows=[1.2] * 4,
    )
    replay = MonthlyMechanicalBacktest(frames, MonthlyBotConfig(spread_pips=0, slippage_pips=0, commission_per_lot_side=0))
    context = monthly.FrozenContext(datetime(2026, 8, 3, tzinfo=UTC), "BUY", "BULLISH", "BULLISH", "BULLISH", "BULLISH", "BUY", 1.1, 1.11)
    monkeypatch.setattr(monthly, "stochastic_cross", lambda *_a: True)
    replay._run_window(monthly.SessionWindow("LONDON", datetime(2026, 8, 3, 7, tzinfo=UTC), datetime(2026, 8, 3, 8, tzinfo=UTC)), context)
    assert any(event["kind"] == "ENTRY" for event in replay.events)
    assert any(event["kind"] == "CLOSE" and event["reason"] == "take_profit_aggregate" for event in replay.events)
