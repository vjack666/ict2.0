from datetime import datetime, timedelta, timezone
import math

import pytest

from mechanical_bot.core import (
    BotConfig, BotState, Candle, MechanicalBot, Position, Snapshot,
    SnapshotRejected, StochasticReading, validate_snapshot,
)

NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
CONFIG = BotConfig(enabled=True, stale_after=timedelta(minutes=20))


def snapshot(direction="BUY", probability=0.70, confirmed=True, **extra):
    return Snapshot(direction, probability, confirmed, extra.get("asof_time", NOW), **{k:v for k,v in extra.items() if k != "asof_time"})


def oversold_cross():
    return StochasticReading(k=25, d=18, previous_k=15, previous_d=18)


def overbought_cross():
    return StochasticReading(k=75, d=82, previous_k=85, previous_d=82)


def positions(profit):
    return [Position("EURUSD", CONFIG.magic_number, "BUY", .1, 1.1, profit)]


def test_snapshot_requires_confirmed_fresh_and_threshold_but_ignores_ltf():
    assert validate_snapshot(snapshot(), CONFIG, NOW) == "BUY"
    with pytest.raises(SnapshotRejected):
        validate_snapshot(snapshot(probability=.699), CONFIG, NOW)
    with pytest.raises(SnapshotRejected):
        validate_snapshot(snapshot(confirmed=False), CONFIG, NOW)
    with pytest.raises(SnapshotRejected):
        validate_snapshot(snapshot(asof_time=NOW - timedelta(minutes=21)), CONFIG, NOW)
    # Snapshot deliberately has no M5/M1 fields; these cannot veto this API.


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.01, 1.01, True])
def test_snapshot_probability_must_be_a_finite_unit_interval(probability):
    with pytest.raises(SnapshotRejected):
        validate_snapshot(snapshot(probability=probability), CONFIG, NOW)


def test_snapshot_rejects_future_time_non_boolean_confirmation_and_missing_symbol():
    with pytest.raises(SnapshotRejected, match="future"):
        validate_snapshot(snapshot(asof_time=NOW + timedelta(microseconds=1)), CONFIG, NOW)
    with pytest.raises(SnapshotRejected, match="confirmed"):
        validate_snapshot(snapshot(confirmed="false"), CONFIG, NOW)
    with pytest.raises(SnapshotRejected, match="symbol"):
        validate_snapshot(snapshot(symbol=""), CONFIG, NOW)


def test_config_rejects_non_finite_probability_threshold():
    for value in (math.nan, math.inf, True):
        with pytest.raises(ValueError):
            BotConfig(min_probability=value)
    with pytest.raises(ValueError, match="boolean"):
        BotConfig(enabled="false")


def test_buy_and_sell_only_open_on_matching_stochastic_cross():
    bot = MechanicalBot(CONFIG)
    bot.arm()
    action = bot.decide_entry(snapshot("BUY"), oversold_cross(), 1.1000, 1_000, NOW)
    assert (action.kind, action.side, action.volume) == ("OPEN", "BUY", .10)
    assert bot.state == BotState.INITIAL_ENTRY

    sell = MechanicalBot(CONFIG)
    sell.arm()
    action = sell.decide_entry(snapshot("SELL"), overbought_cross(), 1.1000, 1_000, NOW)
    assert (action.kind, action.side) == ("OPEN", "SELL")


def test_default_configuration_is_off_and_never_enters():
    bot = MechanicalBot()
    assert bot.state == BotState.OFF
    assert bot.decide_entry(snapshot(), oversold_cross(), 1.1, 1000, NOW) is None
    with pytest.raises(RuntimeError):
        bot.arm()


def test_reentries_are_exactly_20_and_40_pips_from_initial_price():
    bot = MechanicalBot(CONFIG)
    bot.arm()
    bot.decide_entry(snapshot(), oversold_cross(), 1.1000, 1_000, NOW)
    assert bot.monitor(1.0981, positions(-1)) is None
    one = bot.monitor(1.0980, positions(-1))
    assert (one.kind, one.volume, one.reason) == ("OPEN", .20, "adverse_reentry_1")
    assert bot.monitor(1.0961, positions(-1)) is None
    two = bot.monitor(1.0960, positions(-1))
    assert (two.kind, two.volume, two.reason) == ("OPEN", .30, "adverse_reentry_2")
    assert bot.monitor(1.0940, positions(-1)) is None


def test_tp_and_risk_only_use_bot_positions_for_same_symbol():
    bot = MechanicalBot(CONFIG)
    bot.arm(); bot.decide_entry(snapshot(), oversold_cross(), 1.1, 1_000, NOW)
    other = Position("GBPUSD", CONFIG.magic_number, "BUY", .1, 1.1, 9_999)
    assert bot.monitor(1.1, positions(59) + [other]) is None
    assert bot.monitor(1.1, positions(60)).reason == "take_profit_aggregate"

    risk = MechanicalBot(CONFIG)
    risk.arm(); risk.decide_entry(snapshot(), oversold_cross(), 1.1, 1_000, NOW)
    unrelated = Position("EURUSD", 9, "BUY", .1, 1.1, -9_999)
    assert risk.monitor(1.1, positions(-19) + [unrelated]) is None
    assert risk.monitor(1.1, positions(-20)).reason == "max_floating_loss"


def test_missing_own_positions_fails_closed_and_never_reenters():
    bot = MechanicalBot(CONFIG)
    bot.arm(); bot.decide_entry(snapshot(), oversold_cross(), 1.1, 1_000, NOW)
    assert bot.monitor(1.0980, []) is None
    assert bot.state == BotState.ERROR


def test_complete_close_resets_cycle_and_requires_new_signal():
    bot = MechanicalBot(CONFIG)
    bot.arm(); bot.decide_entry(snapshot(), oversold_cross(), 1.1, 1_000, NOW)
    bot.complete_close()
    assert bot.cycle is None and bot.state == BotState.CLOSED


def test_disarm_preserves_cycle_and_blocks_new_decisions():
    bot = MechanicalBot(CONFIG)
    bot.arm(); bot.decide_entry(snapshot(), oversold_cross(), 1.1, 1_000, NOW)
    bot.stop()
    assert bot.state == BotState.OFF and bot.cycle is not None
    assert bot.decide_entry(snapshot(asof_time=NOW + timedelta(minutes=1)), oversold_cross(), 1.1, 1_000, NOW + timedelta(minutes=1)) is None

def test_after_close_the_same_snapshot_cannot_reopen_a_cycle():
    bot = MechanicalBot(CONFIG)
    bot.arm(); bot.decide_entry(snapshot(), oversold_cross(), 1.1, 1_000, NOW)
    bot.complete_close()
    assert bot.decide_entry(snapshot(), oversold_cross(), 1.1, 1_000, NOW) is None
    assert bot.decide_entry(snapshot(asof_time=NOW + timedelta(minutes=1)), oversold_cross(), 1.1, 1_000, NOW + timedelta(minutes=1)).kind == "OPEN"
