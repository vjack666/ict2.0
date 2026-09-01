"""Tests de geometría de outcomes secuenciales (R-multiples, sin indicadores).

Nota de datos sintéticos: las series planas hacen que CADA barra sea pivote
empatado bajo la regla de swings del motor; se usan series monótonas/zigzag
con variación real.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.sequential_events import SeqConfig, Stage, run_sequential
from engine.sequential_outcome import (
    OutcomeConfig,
    TradeLevels,
    bootstrap_clustered,
    measured_projection_tp,
    resolve_outcome,
    structural_stop,
    wilson_interval,
)

CFG = OutcomeConfig(horizon_bars=200, sl_buffer=0.0001)


def _long_levels() -> TradeLevels:
    return TradeLevels(direction=1, entry=1.1050, sl=1.1000, tp=1.1150)


def _short_levels() -> TradeLevels:
    return TradeLevels(direction=-1, entry=1.1050, sl=1.1100, tp=1.0950)


# --- TradeLevels validity -------------------------------------------------

def test_levels_valid_long_requires_sl_below_entry_below_tp():
    assert TradeLevels(1, 1.1050, 1.1000, 1.1150).is_valid()
    assert not TradeLevels(1, 1.1050, 1.1060, 1.1150).is_valid()  # SL above entry
    assert not TradeLevels(1, 1.1050, 1.1000, 1.1040).is_valid()  # TP below entry


def test_levels_valid_short_mirror():
    assert TradeLevels(-1, 1.1050, 1.1100, 1.0950).is_valid()
    assert not TradeLevels(-1, 1.1050, 1.1040, 1.0950).is_valid()


def test_levels_invalid_on_nan():
    assert not TradeLevels(1, float("nan"), 1.1000, 1.1150).is_valid()
    assert not TradeLevels(0, 1.1050, 1.1000, 1.1150).is_valid()


# --- structural stop -------------------------------------------------------

def test_structural_stop_long_is_min_of_candidates_minus_buffer():
    sl = structural_stop(1, sweep_extreme=1.0990, broken_swing=1.0995, buffer=0.0001)
    assert sl == 1.0989


def test_structural_stop_short_is_max_plus_buffer():
    sl = structural_stop(-1, sweep_extreme=1.1110, broken_swing=1.1105, buffer=0.0001)
    assert sl == 1.1111


def test_structural_stop_falls_back_to_available_anchor():
    assert structural_stop(1, sweep_extreme=None, broken_swing=1.0995, buffer=0.0001) == 1.0994
    assert structural_stop(-1, sweep_extreme=1.1110, broken_swing=None, buffer=0.0001) == 1.1111


def test_structural_stop_none_without_anchors_never_atr():
    assert structural_stop(1, sweep_extreme=None, broken_swing=None, buffer=0.0001) is None


# --- measured projection TP ------------------------------------------------

def test_measured_projection_long_and_short():
    assert measured_projection_tp(1, 1.1100, 1.1000) == 1.1200
    assert measured_projection_tp(-1, 1.1100, 1.1000) == 1.0900


def test_measured_projection_degenerate_range_is_none():
    assert measured_projection_tp(1, 1.1000, 1.1000) is None


# --- resolve_outcome --------------------------------------------------------

def test_resolve_tp_first_long():
    high = np.array([1.1060, 1.1070, 1.1080, 1.1090, 1.1120, 1.1160])
    low = np.array([1.1030, 1.1035, 1.1040, 1.1050, 1.1080, 1.1100])
    res = resolve_outcome(high, low, 2, _long_levels(), CFG)
    assert res["outcome"] == "TP"
    assert res["exit_r"] == pytest.approx(2.0)
    assert res["exit_bar"] == 5
    assert res["bars_held"] == 3


def test_resolve_sl_first_long():
    high = np.array([1.1060, 1.1070, 1.1080, 1.1075, 1.1060])
    low = np.array([1.1030, 1.1035, 1.1040, 1.0995, 1.0980])
    res = resolve_outcome(high, low, 2, _long_levels(), CFG)
    assert res["outcome"] == "SL"
    assert res["exit_r"] == -1.0
    assert res["exit_bar"] == 3


def test_intrabar_tie_resolves_pessimistic_to_sl():
    high = np.array([1.1060, 1.1070, 1.1080, 1.1200])
    low = np.array([1.1030, 1.1035, 1.1040, 1.0950])  # same bar spans SL and TP
    res = resolve_outcome(high, low, 2, _long_levels(), CFG)
    assert res["outcome"] == "SL"
    assert res["exit_r"] == -1.0


def test_entry_bar_itself_never_triggers():
    # touch ON the entry bar must be ignored (entry fills at its close)
    high = np.array([1.1200, 1.1070, 1.1080, 1.1085, 1.1090])
    low = np.array([1.0950, 1.1035, 1.1040, 1.1045, 1.1050])
    res = resolve_outcome(high, low, 2, _long_levels(), CFG)
    assert res["outcome"] == "OPEN"


def test_horizon_cap_yields_open():
    cfg = OutcomeConfig(horizon_bars=2, sl_buffer=0.0001)
    # bars 3-4 (inside horizon) never touch; the touch happens at bar 5 (outside)
    high = np.array([1.1060, 1.1070, 1.1080, 1.1085, 1.1090, 1.1200])
    low = np.array([1.1030, 1.1035, 1.1040, 1.1045, 1.1050, 1.1040])
    res = resolve_outcome(high, low, 2, _long_levels(), cfg)
    assert res["outcome"] == "OPEN"
    assert res["exit_r"] is None


def test_short_mirror_tp_resolution():
    high = np.array([1.1040, 1.1045, 1.1050, 1.1045, 1.1040])
    low = np.array([1.1060, 1.1055, 1.1050, 1.0940, 1.1000])
    res = resolve_outcome(high, low, 2, _short_levels(), CFG)
    assert res["outcome"] == "TP"
    assert res["exit_r"] == pytest.approx(2.0)


def test_invalid_levels_reported_not_scanned():
    bad = TradeLevels(direction=1, entry=1.1050, sl=1.1200, tp=1.1150)
    high = np.array([1.1] * 5)
    low = np.array([1.0] * 5)
    res = resolve_outcome(high, low, 0, bad, CFG)
    assert res["outcome"] == "INVALID"


# --- statistics --------------------------------------------------------------

def test_wilson_interval_bounds():
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and 0.0 < hi < 0.35
    lo, hi = wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and 0.65 < lo < 1.0
    lo, hi = wilson_interval(50, 100)
    assert 0.40 < lo <= 0.50 <= hi < 0.60


def test_bootstrap_clustered_reproducible_and_excludes_open():
    trades = [
        {"chain_id": "A", "exit_r": 1.0},
        {"chain_id": "A", "exit_r": -1.0},
        {"chain_id": "B", "exit_r": 1.0},
        {"chain_id": "C", "exit_r": None},  # OPEN -> excluded
    ]
    a = bootstrap_clustered(trades, "chain_id", n_resamples=500, seed=7)
    b = bootstrap_clustered(trades, "chain_id", n_resamples=500, seed=7)
    assert a == b
    assert a["n_closed"] == 3
    assert a["n_clusters"] == 2
    lo, hi = a["mean_r_ci"]
    assert lo <= hi


# --- integration: additive sweep-extreme capture ------------------------------

def _synth_monotonic_sequence(n: int = 90) -> pd.DataFrame:
    """Zigzag con pisos iguales en 1.1000, sweep, desplazamiento y BOS-lite."""
    rows = []
    price = 1.1000
    for i in range(n):
        if i % 2 == 0 and i < 30:
            o, h, l, c = price, price + 0.0012, price - 0.0008, price + 0.0004
        elif i < 30:
            o, h, l, c = price, price + 0.0008, price - 0.0012, price - 0.0004
        elif i == 30:
            o, h, l, c = 1.1002, 1.1006, 1.0985, 1.1004  # sweep below equal lows
        elif i == 33:
            o, h, l, c = 1.1004, 1.1040, 1.1003, 1.1038  # displacement bull
        elif i == 36:
            o, h, l, c = 1.1038, 1.1055, 1.1036, 1.1052  # break of swing high
        else:
            step = 0.00008 if i > 30 else 0.0
            o = price
            c = price + step
            h = max(o, c) + 0.0004
            l = min(o, c) - 0.0004
        rows.append({"time": i, "open": o, "high": h, "low": l, "close": c})
        price = c
    return pd.DataFrame(rows)


def test_sweep_nodes_carry_wick_extremes_backward_compatible():
    df = _synth_monotonic_sequence()
    chains = run_sequential(df, SeqConfig(structure_mode="lite"))
    sweeps = [nd for ch in chains for nd in ch.nodes if nd.stage is Stage.SWEEP]
    assert sweeps, "expected at least one SWEEP node in synthetic zigzag"
    for nd in sweeps:
        assert isinstance(nd.extra.get("pool_form_bar"), int)
        sh, sl = nd.extra.get("sweep_high"), nd.extra.get("sweep_low")
        assert sh is not None and sl is not None
        assert np.isfinite(sh) and np.isfinite(sl)
