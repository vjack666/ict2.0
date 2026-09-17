import pandas as pd

from scripts.lab.experiments.displacement_phase1 import panel


def bars(n=40):
    t = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = pd.Series([1 + i * .00001 for i in range(n)])
    return pd.DataFrame({"time": t, "open": close - .00002, "high": close + .00003, "low": close - .00003, "close": close})


def test_m15_prefix_is_stable_for_past_rows():
    x = bars()
    a = panel(x.iloc[:30]).iloc[:-1].reset_index(drop=True)
    b = panel(x).iloc[:len(a)].reset_index(drop=True)
    causal = [c for c in a.columns if not c.startswith("outcome_")]
    pd.testing.assert_frame_equal(a[causal], b[causal], check_dtype=False)


def test_warmup_is_unknown_not_positive():
    out = panel(bars(10))
    assert not out.episode_available.iloc[:2].any()
    assert not out.episode_breakout_positive.iloc[:2].any()


def test_outcome_is_separate_from_causal_columns():
    out = panel(bars(40))
    assert "outcome_up_4x_body" in out
    assert "outcome_up_4x_body" not in {"geometry_positive", "episode_breakout_positive"}
    assert set(out.reconciliation.unique()) <= {"AGREE", "ENGINE_ONLY", "RANGE_ONLY", "NEITHER"}
