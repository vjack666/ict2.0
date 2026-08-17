from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.market_object import ObjectType


def candle(t, o, h, l, c):
    return {"time": t, "open": o, "high": h, "low": l, "close": c}


def test_bullish_fvg_appears_only_after_third_candle_closes():
    rows = [
        candle(0, 1.100, 1.105, 1.095, 1.102),
        candle(1, 1.102, 1.110, 1.101, 1.109),
        candle(2, 1.109, 1.120, 1.112, 1.118),
    ]
    zones = detect_fvg(rows, timeframe="H1", symbol="EURUSD")
    assert len(zones) == 1
    zone = zones[0]
    assert zone.type == ObjectType.FVG
    assert zone.direction == 1
    assert zone.candidate_bar == 0
    assert zone.confirmation_bar == 2
    assert zone.tradable_bar == 2
    assert zone.zone_low == 1.105
    assert zone.zone_high == 1.112


def test_bearish_fvg_is_causal():
    rows = [
        candle(0, 1.105, 1.110, 1.100, 1.108),
        candle(1, 1.108, 1.109, 1.098, 1.099),
        candle(2, 1.099, 1.095, 1.090, 1.091),
    ]
    zones = detect_fvg(rows, timeframe="H1")
    assert len(zones) == 1
    assert zones[0].direction == -1
    assert zones[0].candidate_bar == 0
    assert zones[0].confirmation_bar == 2


def test_fvg_prefix_invariance_under_future_append():
    prefix = [
        candle(0, 1.100, 1.105, 1.095, 1.102),
        candle(1, 1.102, 1.110, 1.101, 1.109),
        candle(2, 1.109, 1.120, 1.112, 1.118),
    ]
    future = candle(3, 1.118, 1.130, 1.117, 1.125)
    base = [z.to_dict() for z in detect_fvg(prefix, timeframe="H1")]
    extended = [z.to_dict() for z in detect_fvg(prefix + [future], timeframe="H1")]
    assert extended[: len(base)] == base


def test_bullish_order_block_requires_closed_followthrough():
    rows = [
        candle(0, 1.100, 1.110, 1.095, 1.099),
        candle(1, 1.098, 1.125, 1.097, 1.120),
    ]
    blocks = detect_order_blocks(rows, timeframe="H1", min_body_ratio=0.20)
    assert len(blocks) == 1
    ob = blocks[0]
    assert ob.type == ObjectType.ORDER_BLOCK
    assert ob.direction == 1
    assert ob.candidate_bar == 0
    assert ob.confirmation_bar == 1
    assert ob.tradable_bar == 1
    assert ob.meta["followthrough"] == 1


def test_bearish_order_block_requires_closed_followthrough():
    rows = [
        candle(0, 1.100, 1.110, 1.095, 1.109),
        candle(1, 1.108, 1.109, 1.080, 1.085),
    ]
    blocks = detect_order_blocks(rows, timeframe="H1", min_body_ratio=0.20)
    assert len(blocks) == 1
    assert blocks[0].direction == -1


def test_order_block_does_not_use_future_bar_for_existing_signal():
    prefix = [
        candle(0, 1.100, 1.110, 1.095, 1.099),
        candle(1, 1.098, 1.125, 1.097, 1.120),
    ]
    future = candle(2, 1.120, 1.140, 1.115, 1.135)
    base = [z.to_dict() for z in detect_order_blocks(prefix, timeframe="H1", min_body_ratio=0.20)]
    extended = [z.to_dict() for z in detect_order_blocks(prefix + [future], timeframe="H1", min_body_ratio=0.20)]
    assert extended[: len(base)] == base


def test_order_block_rejects_entry_on_footprint_candle():
    rows = [candle(0, 1.100, 1.110, 1.095, 1.099)]
    assert detect_order_blocks(rows, timeframe="H1", min_body_ratio=0.20) == []
