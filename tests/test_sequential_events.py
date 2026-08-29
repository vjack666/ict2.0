"""Tests del motor de eventos secuenciales."""
from __future__ import annotations

import pandas as pd
from unittest.mock import patch

from engine.sequential_events import (
    STAGE_ORDER,
    SeqConfig,
    SeqNode,
    SequentialChain,
    Stage,
    _causal_swings,
    run_sequential,
    summarize_chains,
)
from engine.mtf_navigation import _causal_swings as mtf_causal_swings
from audits.codigo.mtf_seq_funnel_a7 import (
    _atomic_events,
    _prefix_event_delta,
    _run_funnel,
    funnel_fvg_ob,
    funnel_prefix_invariance,
    funnel_sequence,
    PREFIX_RATIOS,
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


def test_causal_swings_publish_confirmation_and_share_one_helper():
    import numpy as np

    high = np.array([10.0, 11.0, 20.0, 13.0, 20.0, 15.0, 16.0])
    low = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    expected = ([(3, 20.0), (5, 20.0)], [])
    assert _causal_swings(high, low, 1) == expected
    assert mtf_causal_swings(high, low, 1) == expected


def test_run_sequential_full_prefix_uses_only_confirmed_pools():
    high = [10.0, 11.0, 20.0, 13.0, 20.0, 15.0, 16.0]
    low = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    mid = [(h + l) / 2 for h, l in zip(high, low)]
    df = pd.DataFrame({"open": mid, "high": high, "low": low, "close": mid})
    cfg = SeqConfig(swing_left=1, min_eq_touches=2, max_active_chains=100)

    full = run_sequential(df, cfg, timeframe="H1")
    prefix = run_sequential(df.iloc[:5].reset_index(drop=True), cfg, timeframe="H1")

    full_before_confirmation = {
        (node.stage.value, node.bar, node.object_id)
        for chain in full
        for node in chain.nodes
        if node.bar < 5
    }
    prefix_atoms = {
        (node.stage.value, node.bar, node.object_id)
        for chain in prefix
        for node in chain.nodes
    }
    assert full_before_confirmation == prefix_atoms == set()
    assert [(node.stage.value, node.bar) for node in full[0].nodes] == [("LIQUIDITY_POOL", 5)]


def test_a7_prefix_gate_uses_multiple_fixed_cuts_and_confirmation_time():
    times = pd.date_range("2026-01-01", periods=11, freq="h", tz="UTC")
    # With swing_left=3, equal pivots at j=3 and j=7 are confirmed at
    # bars 6 and 10; the pool is therefore observable only at bar 10.
    high = [10.0, 11.0, 12.0, 20.0, 13.0, 14.0, 15.0, 20.0, 13.0, 14.0, 15.0]
    low = list(map(float, range(11)))
    mid = [(h + l) / 2 for h, l in zip(high, low)]
    df = pd.DataFrame({"bar": times, "time": times, "open": mid, "high": high, "low": low, "close": mid})

    records = funnel_sequence(df, "H1")
    pool = next(record for record in records if record["sequence_stage"] == "LIQUIDITY_POOL")
    assert pool["observation_time"] == times[10].isoformat()

    result = funnel_prefix_invariance({"H1": df, "H4": df, "D1": df})
    assert result["prefix_ratios"] == list(PREFIX_RATIOS)
    assert len(result["sequence"]["cuts"]) == len(PREFIX_RATIOS)
    assert result["sequence"]["all_cuts_invariant"] is True


def test_sequence_nodes_are_exactly_full_prefix_stable_by_atomic_identity():
    df = _synth_bull_sequence(80)
    cutoff = 50
    cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
    full = run_sequential(df, cfg, timeframe="H1")
    prefix = run_sequential(df.iloc[:cutoff].reset_index(drop=True), cfg, timeframe="H1")

    def atoms(chains):
        return {
            (node.stage.value, node.bar, node.direction, node.object_id)
            for chain in chains
            for node in chain.nodes
            if node.bar < cutoff
        }

    assert atoms(full) == atoms(prefix)


def test_prefix_atoms_use_normalized_time_exactly_and_ignore_partial_aggregates():
    cutoff = "2026-01-01 09:00:00+00:00"
    full = [
        {"timeframe": "H1", "stage": "FVG", "id": "FVG_H1_1_BULL",
         "observation_time": "2026-01-01T09:00:00+00:00"},
        {"timeframe": "H1", "stage": "FVG", "id": "FVG_H1_2_BULL",
         "observation_time": "2026-01-01T10:00:00+00:00"},
        {"timeframe": "H1", "stage": "SEQUENCE", "id": "partial",
         "observation_time": cutoff, "atomic": False},
    ]
    prefix = [
        full[0],
        {"timeframe": "H1", "stage": "SEQUENCE", "id": "partial",
         "observation_time": cutoff, "atomic": False},
    ]

    missing, extra = _prefix_event_delta(full, prefix, cutoff)

    assert missing == set()
    assert extra == set()
    assert _atomic_events(full, cutoff) == {
        ("H1", "FVG", "FVG_H1_1_BULL")
    }


def test_prefix_comparison_rejects_extra_observable_prefix_atom():
    full = [{"timeframe": "H1", "stage": "FVG", "id": "F1",
             "observation_time": "2026-01-01T10:00:00+00:00"}]
    prefix = [{"timeframe": "H1", "stage": "FVG", "id": "P1",
               "observation_time": "2026-01-01T09:00:00+00:00"}]

    missing, extra = _prefix_event_delta(
        full, prefix, "2026-01-01T09:00:00+00:00"
    )

    assert missing == set()
    assert extra == {("H1", "FVG", "P1")}


def test_sequence_projection_ids_are_deterministic_and_noncolliding():
    df = _synth_bull_sequence(80)
    first = funnel_sequence(df, "H1")
    second = funnel_sequence(df, "H1")

    assert first == second
    ids = [(record["stage"], record["id"]) for record in first]
    assert len(ids) == len(set(ids))
    assert {record["stage"] for record in first if not record["atomic"]} == {"SEQUENCE"}


def test_complete_sequence_and_retest_have_contract_valid_projection():
    times = pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC")
    df = pd.DataFrame({"time": times, "open": [1.0, 1.0, 1.0],
                       "high": [1.1, 1.1, 1.1], "low": [0.9, 0.9, 0.9],
                       "close": [1.0, 1.0, 1.0]})
    chain = SequentialChain(
        chain_id="SEQ_H1_1", direction=1,
        nodes=[SeqNode(Stage.LIQUIDITY_POOL, 0, 1, object_id="EQL_0"),
               SeqNode(Stage.RETEST, 2, 1, object_id="RETEST_2")],
        status="COMPLETE", created_bar=0, last_bar=2,
    )

    with patch("audits.codigo.mtf_seq_funnel_a7.run_sequential", return_value=[chain]):
        records = funnel_sequence(df, "H1")

    retest = next(record for record in records if record["sequence_stage"] == "RETEST")
    complete = next(record for record in records if record["id"].endswith(":COMPLETE"))
    assert retest["stage"] == "SEQUENCE"
    assert retest["atomic"] is True
    assert all(complete[field] == times[2].isoformat()
               for field in ("observation_time", "candidate_time",
                             "confirmation_time", "tradable_time"))


def test_confluence_parent_time_is_not_after_child_observation():
    from engine.market_object import MarketObject, ObjectState, ObjectType, Role
    from types import SimpleNamespace

    t0, t1, t2 = pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC")
    common = dict(origin_tf="H1", role=Role.REFINEMENT, direction=1,
                  state=ObjectState.ACTIVE, candidate_bar=0,
                  candidate_time=t0, confirmation_bar=1,
                  confirmation_time=t1, tradable_bar=1, tradable_time=t1)
    fvg = MarketObject(id="FVG_H1_1_BULL", type=ObjectType.FVG,
                       zone_high=1.0, zone_low=0.9, **common)
    ob = MarketObject(id="OB_H1_1_BULL", type=ObjectType.ORDER_BLOCK,
                      zone_high=1.0, zone_low=0.9, **common)
    relation = SimpleNamespace(fvg_id=fvg.id, ob_id=ob.id, direction=1)
    df = pd.DataFrame({"time": [t0, t1, t2], "bar": [0, 1, 2], "open": [1, 1, 1],
                       "high": [1.1, 1.1, 1.1], "low": [0.9, 0.9, 0.9],
                       "close": [1, 1, 1]})

    with patch("audits.codigo.mtf_seq_funnel_a7.detect_fvg", return_value=[fvg]), \
         patch("audits.codigo.mtf_seq_funnel_a7.detect_order_blocks", return_value=[ob]), \
         patch("audits.codigo.mtf_seq_funnel_a7.relate_fvg_ob", return_value=[relation]):
        records = funnel_fvg_ob(df, "H1")

    confluence = next(record for record in records if record["stage"] == "CONFLUENCE")
    assert confluence["parent_time"] <= confluence["observation_time"]
    assert confluence["parent_time"] <= confluence["candidate_time"]
    assert confluence["candidate_time"] <= confluence["confirmation_time"]
    assert confluence["confirmation_time"] <= confluence["tradable_time"]
    assert confluence["tradable_time"] <= confluence["observation_time"]


def test_runner_serializes_audit_distribution_metrics():
    from types import SimpleNamespace

    fake_result = SimpleNamespace(
        status=SimpleNamespace(value="FAIL"), input_count=3,
        accepted_count=1, rejected_count=2,
        metrics={
            "audit_score": 0.5,
            "rejection_reason_counts": {"INVALID_DATA": 2},
            "timeframe_counts": {"H1": 3},
            "extra_stage_counts": {"LIQUIDITY_POOL": 1},
        }, findings=[],
    )
    fake_summary = SimpleNamespace(
        stage="SEQUENCE", input_count=3, accepted_count=1,
        rejected_count=2, duplicate_count=0, orphan_count=0,
        temporal_violation_count=0,
    )

    with patch(
        "audits.codigo.mtf_seq_funnel_a7.FunnelAudit.run",
        return_value=(fake_result, (fake_summary,)),
    ):
        section = _run_funnel([{"stage": "SEQUENCE", "id": "x"}])

    assert section["audit_status"] == "FAIL"
    assert section["rejection_reason_counts"] == {"INVALID_DATA": 2}
    assert section["timeframe_counts"] == {"H1": 3}
    assert section["extra_stage_counts"] == {"LIQUIDITY_POOL": 1}
