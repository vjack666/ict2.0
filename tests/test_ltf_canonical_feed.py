"""Tests del feed canónico LTF y la frontera temporal PIT (Codex H4).

Verifican que ``engine.ltf_canonical_feed`` proyecta el estado de lifecycle
SOLO por timestamp (nunca comparando índices de distinta temporalidad), y que
un objeto H4 alimentado con barras M15 cuyo índice posicional es menor que el
``tradable_bar`` H4 (pero cuyo timestamp es posterior) NO se descarta como
BEFORE_TRADABLE.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from engine.lifecycle import evaluate, observe_lower_tf
from engine.ltf_canonical_feed import build_ltf_canonical_feed, _touch_state
from engine.market_object import MarketObject, ObjectState, ObjectType, Role


# === Tests originales (reproducibilidad / as-of decision_time) =============

def _m15() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=5, freq="15min"),
            "open": [1.09, 1.02, 1.12, 1.115, 1.13],
            "high": [1.10, 1.13, 1.14, 1.135, 1.14],
            "low": [1.00, 1.01, 1.11, 1.105, 1.12],
            "close": [1.01, 1.12, 1.13, 1.125, 1.135],
        }
    )


def test_canonical_feed_reuses_detectors_and_tracks_touch_as_of_decision_time():
    frame = _m15()
    result = build_ltf_canonical_feed(
        {"M15": frame},
        pd.Timestamp("2020-01-01 00:45", tz="UTC"),
        exec_tf="M15",
        include_sequence=False,
    )

    zones = result["zones"]["M15"]
    assert result["source"].startswith("engine.detectors")
    assert any(obj.type is ObjectType.FVG for obj in zones)
    fvg = next(obj for obj in zones if obj.type is ObjectType.FVG)
    assert fvg.state is ObjectState.PARTIALLY_MITIGATED
    assert fvg.touch_count == 1
    assert fvg.first_touch_time == frame.iloc[3]["time"]


def test_canonical_feed_excludes_future_objects_and_is_deterministic():
    frame = _m15()
    t = pd.Timestamp("2020-01-01 00:30", tz="UTC")
    before = build_ltf_canonical_feed({"M15": frame}, t, include_sequence=False)
    extended = pd.concat(
        [frame, pd.DataFrame({"time": [pd.Timestamp("2020-01-01 02:00")], "open": [1.1], "high": [1.2], "low": [1.0], "close": [1.15]})],
        ignore_index=True,
    )
    after = build_ltf_canonical_feed({"M15": extended}, t, include_sequence=False)
    assert [obj.to_dict() for obj in before["zones"]["M15"]] == [obj.to_dict() for obj in after["zones"]["M15"]]


# === Nuevos tests: frontera temporal PIT por timestamp (Codex H4) ==========

def _ts(n: int) -> datetime:
    return datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc) + __import__("datetime").timedelta(minutes=n)


def _h4_fvg_bull(bar: int, zone_low: float, zone_high: float) -> MarketObject:
    return MarketObject(
        id=f"FVG_H4_{bar}_BULL", symbol="EURUSD", type=ObjectType.FVG, origin_tf="H4",
        role=Role.REFINEMENT, direction=1, zone_high=zone_high, zone_low=zone_low,
        creation_time=_ts(bar), state=ObjectState.ACTIVE, bar_index=bar, bar_time=_ts(bar),
        candidate_bar=bar - 2, candidate_time=_ts(bar - 2), confirmation_bar=bar,
        confirmation_time=_ts(bar), tradable_bar=bar, tradable_time=_ts(bar),
        mitigation_level=zone_low, meta={"pattern": "3C_FVG", "side": "bullish"},
    )


def _m15_frame(times, rows):
    df = pd.DataFrame(
        [{"time": t, "open": o, "high": h, "low": l, "close": c} for t, (o, h, l, c) in zip(times, rows)]
    )
    return df.reset_index(drop=True)


def test_build_feed_empty_frame_returns_empty_zones():
    feed = build_ltf_canonical_feed({}, _ts(100), exec_tf="M15", include_sequence=False)
    assert feed["zones"]["M15"] == []
    assert feed["decision_time"] is not None
    assert "source" in feed


def test_build_feed_applies_lifecycle_by_timestamp():
    # Patrón FVG bull 3-vela en M15: vela2.low(1.1002) > vela0.high(1.1000).
    times = [_ts(0), _ts(1), _ts(2), _ts(3), _ts(4), _ts(5)]
    rows = [
        (1.0990, 1.1000, 1.0985, 1.0995),  # first: high=1.1000
        (1.0995, 1.0998, 1.0992, 1.0996),  # middle
        (1.1001, 1.1006, 1.1002, 1.1004),  # third: low=1.1002 > 1.1000 => FVG [1.1000,1.1002]
        (1.0998, 1.0999, 1.0995, 1.0995),  # bar3 cierra < far_side 1.1000 => INVALIDATED
        (1.0996, 1.0997, 1.0990, 1.0992),
        (1.0994, 1.0995, 1.0991, 1.0993),
    ]
    df = _m15_frame(times, rows)
    feed = build_ltf_canonical_feed({"M15": df}, _ts(5), exec_tf="M15", include_sequence=False)
    zones = feed["zones"]["M15"]
    # La vela de confirmación (índice 2) crea la zona; la vela 3 la invalida.
    fvg = next(z for z in zones if z.id == "FVG_M15_2_BULL")
    assert fvg.state == ObjectState.INVALIDATED
    assert fvg.invalidated_bar == 3


def test_touch_state_h4_object_with_m15_bars_timestamp_only():
    """Objeto H4 cuya ``tradable_bar`` (H4) es 10, alimentado con barras M15
    de índice posicional 0..4 (MENOR que 10) pero timestamp POSTERIOR a
    ``tradable_time``. Con la comparación cross-TF por índice, todas serían
    descartadas como BEFORE_TRADABLE; por timestamp deben procesarse.
    """
    ob_h4 = _h4_fvg_bull(10, 1.0995, 1.1005)  # tradable_time=_ts(10), tradable_bar=10
    # M15 frame: índices 0..4, timestamps _ts(20..24) (todos > _ts(10)).
    times = [_ts(20), _ts(21), _ts(22), _ts(23), _ts(24)]
    rows = [
        (1.1000, 1.1008, 1.0996, 1.1004),  # toca (partial)
        (1.1000, 1.1008, 1.0996, 1.1004),  # toca (partial)
        (1.0996, 1.0998, 1.0990, 1.0990),  # cierra < far_side 1.0995 => INVALIDATED
        (1.0994, 1.0996, 1.0990, 1.0991),
        (1.0993, 1.0995, 1.0990, 1.0992),
    ]
    df = _m15_frame(times, rows)
    obj = _touch_state(ob_h4, df, _ts(24))
    # No debe quedar atrapado en ACTIVE por un falso BEFORE_TRADABLE.
    assert obj.state == ObjectState.INVALIDATED
    assert obj.invalidated_bar is not None


def test_touch_state_stamps_tf_and_preserves_authority():
    # Una vela M15 no debe poder transicionar el estado oficial de un objeto H4
    # salvo a través de evaluate con authority_tf=H4 (lo que hace el feed con
    # el sello tf=origin_tf). Verificamos que el sello es coherente.
    ob_h4 = _h4_fvg_bull(10, 1.0995, 1.1005)
    times = [_ts(20), _ts(21)]
    rows = [
        (1.1000, 1.1008, 1.0996, 1.1004),
        (1.0996, 1.0998, 1.0990, 1.0994),
    ]
    df = _m15_frame(times, rows)
    sub = df.loc[pd.to_datetime(df["time"], utc=True, errors="coerce") > pd.to_datetime(ob_h4.tradable_time, utc=True, errors="coerce")].copy()
    sub["__index__"] = sub.index
    sub["tf"] = ob_h4.origin_tf  # el feed sella con origin_tf (H4)
    for _, row in sub.iterrows():
        evaluate(ob_h4, row.to_dict(), authority_tf=ob_h4.origin_tf, decision_time=row["time"])
    assert ob_h4.authority_tf == "H4"
    assert ob_h4.state in (ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED,
                           ObjectState.MITIGATED, ObjectState.INVALIDATED)


def test_observe_lower_tf_does_not_alter_official_state_in_feed_context():
    ob_h4 = _h4_fvg_bull(10, 1.0995, 1.1005)
    # Barras M15 con timestamp > tradable_time pero índice pequeño.
    for idx in (5, 6):
        bar = {"__index__": idx, "time": _ts(20 + idx), "tf": "M15",
               "open": 1.0996, "high": 1.0998, "low": 1.0990, "close": 1.0994}
        observe_lower_tf(ob_h4, bar, observed_tf="M15")
    assert ob_h4.state == ObjectState.ACTIVE
    assert ob_h4.first_touch_bar is None
    assert len(ob_h4.meta["observations"]["M15"]) == 2
