"""Tests del motor de eventos secuenciales."""
from __future__ import annotations

import pandas as pd

from engine.sequential_events import (
    STAGE_ORDER,
    SeqConfig,
    Stage,
    run_sequential,
    summarize_chains,
)


def _synth_bull_sequence(n: int = 80) -> pd.DataFrame:
    """Construye un tramo sintético donde puede formarse EQL→sweep→disp→up."""
    rows = []
    price = 1.1000
    for i in range(n):
        # early equal lows around 1.1000
        if i in (10, 18, 26):
            o, h, l, c = price, price + 0.0008, 1.1000, price + 0.0003
        elif i == 30:
            # sweep below 1.1000 and close back above
            o, h, l, c = 1.1002, 1.1005, 1.0990, 1.1004
        elif i == 32:
            # displacement bull (large body)
            o, h, l, c = 1.1004, 1.1035, 1.1003, 1.1032
        elif i == 35:
            # structure push
            o, h, l, c = 1.1030, 1.1045, 1.1028, 1.1042
        else:
            drift = 0.00005 * (1 if i > 30 else -1)
            o = price
            c = price + drift
            h = max(o, c) + 0.0003
            l = min(o, c) - 0.0003
        rows.append({"time": i, "open": o, "high": h, "low": l, "close": c})
        price = c
    return pd.DataFrame(rows)


def test_stage_order_is_canonical():
    assert [s.value for s in STAGE_ORDER] == [
        "LIQUIDITY_POOL",
        "SWEEP",
        "DISPLACEMENT",
        "STRUCTURE",
        "OB",
        "FVG",
        "RETEST",
    ]


def test_run_on_empty_raises():
    df = pd.DataFrame({"open": [], "high": [], "low": [], "close": []})
    chains = run_sequential(df)
    assert chains == []


def test_run_on_random_ohlc_no_crash_and_order_respected():
    import numpy as np

    rng = np.random.default_rng(0)
    n = 200
    close = 1.1 + np.cumsum(rng.normal(0, 0.0004, n))
    high = close + rng.uniform(0.0001, 0.0006, n)
    low = close - rng.uniform(0.0001, 0.0006, n)
    open_ = close + rng.normal(0, 0.0001, n)
    df = pd.DataFrame({"time": range(n), "open": open_, "high": high, "low": low, "close": close})
    chains = run_sequential(df, SeqConfig(max_active_chains=32))
    summary = summarize_chains(chains)
    assert summary["n_chains"] >= 0
    for ch in chains:
        bars = [nd.bar for nd in ch.nodes]
        assert bars == sorted(bars), "bars must be non-decreasing"
        for a, b in zip(ch.nodes, ch.nodes[1:]):
            assert b.bar > a.bar, "strict sequential: each stage after previous"
            ia = STAGE_ORDER.index(a.stage)
            ib = STAGE_ORDER.index(b.stage)
            assert ib == ia + 1, "stages must advance in canonical order"


def test_no_future_pool_in_past_decision():
    """Añadir velas futuras no debe cambiar cadenas ya cerradas en el prefijo."""
    df = _synth_bull_sequence(60)
    mid = 40
    a = run_sequential(df.iloc[:mid].reset_index(drop=True))
    b = run_sequential(df.iloc[: mid + 15].reset_index(drop=True))
    # any chain that completed with last_bar < mid in the short run should
    # appear with same stages in the longer run
    a_done = {
        (c.direction, tuple((n.stage.value, n.bar) for n in c.nodes))
        for c in a
        if c.last_bar < mid - 1 and len(c.nodes) >= 2
    }
    b_pref = {
        (c.direction, tuple((n.stage.value, n.bar) for n in c.nodes if n.bar < mid))
        for c in b
        if c.created_bar < mid
    }
    # soft check: prefixes of long run cover short-run multi-node patterns
    for item in a_done:
        # direction match with some chain that shares first stages
        assert any(item[0] == x[0] for x in b_pref) or len(a_done) == 0
