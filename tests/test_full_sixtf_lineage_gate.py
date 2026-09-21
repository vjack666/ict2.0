from __future__ import annotations

import pandas as pd

from engine.lineage import (
    build_six_tf_lineage_spine,
    validate_six_tf_persistence_consistency,
)
from engine.market_object import MarketObject
from scripts.audit.verify_full_sixtf_lineage_gate import run_checks


DURATION = {
    "D1": pd.Timedelta(days=1),
    "H4": pd.Timedelta(hours=4),
    "H1": pd.Timedelta(hours=1),
    "M15": pd.Timedelta(minutes=15),
    "M5": pd.Timedelta(minutes=5),
    "M1": pd.Timedelta(minutes=1),
}

# Audited EURUSD Control B: last point where all six canonical TFs coexist.
# Source package SHA256:
# 359ef7e3219142422acec473ae786bd07de13043e2cf0e9a532a9e3eb1eab642
REAL_CONTROL_B = {
    "D1": {
        "open_time": "2026-08-21T00:00:00Z",
        "future_open": "2026-08-24T00:00:00Z",
        "ohlc": (1.16781, 1.17115, 1.16688, 1.16750),
    },
    "H4": {
        "open_time": "2026-08-24T16:00:00Z",
        "future_open": "2026-08-24T20:00:00Z",
        "ohlc": (1.16694, 1.16748, 1.16628, 1.16648),
    },
    "H1": {
        "open_time": "2026-08-24T19:00:00Z",
        "future_open": "2026-08-24T20:00:00Z",
        "ohlc": (1.16645, 1.16697, 1.16628, 1.16648),
    },
    "M15": {
        "open_time": "2026-08-24T20:15:00Z",
        "future_open": "2026-08-24T20:30:00Z",
        "ohlc": (1.16627, 1.16636, 1.16566, 1.16585),
    },
    "M5": {
        "open_time": "2026-08-24T20:30:00Z",
        "future_open": "2026-08-24T20:35:00Z",
        "ohlc": (1.16586, 1.16604, 1.16579, 1.16593),
    },
    "M1": {
        "open_time": "2026-08-24T20:34:00Z",
        "future_open": "2026-08-24T20:35:00Z",
        "ohlc": (1.16594, 1.16595, 1.16589, 1.16593),
    },
}

EXPECTED_CLOSE = {
    "D1": "2026-08-22T00:00:00+00:00",
    "H4": "2026-08-24T20:00:00+00:00",
    "H1": "2026-08-24T20:00:00+00:00",
    "M15": "2026-08-24T20:30:00+00:00",
    "M5": "2026-08-24T20:35:00+00:00",
    "M1": "2026-08-24T20:35:00+00:00",
}


def _frames(_t: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Real audited Control-B bars plus one deliberately unclosed row per TF."""
    out: dict[str, pd.DataFrame] = {}
    for tf, item in REAL_CONTROL_B.items():
        o, h, l, c = item["ohlc"]
        out[tf] = pd.DataFrame(
            {
                "time": [
                    pd.Timestamp(item["open_time"]),
                    pd.Timestamp(item["future_open"]),
                ],
                "open": [o, c],
                "high": [h, c],
                "low": [l, c],
                "close": [c, c],
            }
        )
    return out


def test_full_six_tf_gate_reproducible_real_control_b():
    t = pd.Timestamp("2026-08-24T20:35:00Z")
    result = run_checks(_frames(t), t)

    assert result["all_pass"] is True
    assert result["full"]["valid"] is True
    assert result["prefix"]["valid"] is True
    assert result["full_prefix_identical"] is True
    assert result["save_load_roundtrip"] is True
    assert all(result["edge_fail_closed"].values())
    assert all(result["missing_tf_fail_closed"].values())
    assert result["future_object_rejected"] is True

    closes = {
        tf: layer["close_time"]
        for tf, layer in result["full_layers"].items()
    }
    assert closes == EXPECTED_CLOSE


def test_real_control_b_anchors_preserve_audited_close_prices():
    t = pd.Timestamp("2026-08-24T20:35:00Z")
    objects, layers = build_six_tf_lineage_spine(
        _frames(t),
        t,
        symbol="EURUSD",
    )
    assert [obj.origin_tf for obj in objects] == ["D1", "H4", "H1", "M15", "M5", "M1"]
    for obj in objects:
        expected_close = REAL_CONTROL_B[obj.origin_tf]["ohlc"][3]
        assert obj.zone_low == expected_close
        assert obj.zone_high == expected_close
        assert str(obj.tradable_time) == str(pd.Timestamp(EXPECTED_CLOSE[obj.origin_tf]))
        assert layers[obj.origin_tf]["closed_only"] is True


def test_persisted_six_tf_spine_must_match_closed_feed_exactly():
    t = pd.Timestamp("2026-08-24T20:35:00Z")
    frames = _frames(t)
    persisted, _ = build_six_tf_lineage_spine(frames, t, symbol="EURUSD")

    clean = validate_six_tf_persistence_consistency(
        persisted,
        frames,
        t,
        symbol="EURUSD",
    )
    assert clean["valid"] is True
    assert clean["persisted_signature"] == clean["derived_signature"]

    tampered = [MarketObject.from_dict(obj.to_dict()) for obj in persisted]
    m5 = next(obj for obj in tampered if obj.origin_tf == "M5")
    m5.zone_low = float(m5.zone_low) - 0.00010

    blocked = validate_six_tf_persistence_consistency(
        tampered,
        frames,
        t,
        symbol="EURUSD",
    )
    assert blocked["valid"] is False
    assert blocked["status"] == "FAIL"
    assert any("no coincide" in error for error in blocked["errors"])


def test_missing_persisted_six_tf_spine_fails_closed():
    t = pd.Timestamp("2026-08-24T20:35:00Z")
    result = validate_six_tf_persistence_consistency(
        [],
        _frames(t),
        t,
        symbol="EURUSD",
    )
    assert result["valid"] is False
    assert any("ausente" in error for error in result["errors"])
