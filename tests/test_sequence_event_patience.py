import pandas as pd

from engine.sequence import (
    SequenceConfig, SequenceRunner, SequenceState, _candle_objects,
    run_sequence, run_sequence_traced,
)


def _frame(n=14, *, displacement_at=None, close_at=None):
    rows = []
    for i in range(n):
        rows.append({
            "time": f"2026-01-01T00:{i:02d}:00Z",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "atr": 1.0,
            "liquidity_sweep_down": i == 1,
            "liquidity_sweep_up": False,
            "displacement_bullish": i == displacement_at,
            "displacement_bearish": False,
            "bos_dir": 0,
            "choch_dir": 0,
            "fvg_bullish": False,
            "fvg_bearish": False,
            "ob_bullish": False,
            "ob_bearish": False,
        })
    if close_at is not None:
        rows[close_at]["close"] = 98.0
    return pd.DataFrame(rows)


def _bullish(_i):
    return {"trend": "BULLISH"}


def test_event_driven_wait_accepts_displacement_after_legacy_six_bars():
    audit = {}
    _, phase_seen, _, state = run_sequence_traced(
        _frame(displacement_at=9), _bullish, SequenceConfig(), audit=audit,
    )

    assert phase_seen["SWEEP"] == 1
    assert phase_seen["DISPLACE"] == 1
    assert state.phase == "DISPLACE_DONE"
    assert audit["policy"]["mode"] == "EVENT_DRIVEN"
    assert audit["policy"]["displace_gap"] is None
    assert audit["pending_end"][-1]["status"] == "PENDING_END_OF_DATA"
    assert audit["invalidations"] == []


def test_sweep_freezes_closed_h4_reference_and_snapshot_round_trips():
    def h4(i):
        return {
            "tf": "H4", "available": True, "trend": "BULLISH",
            "asof_time": "2026-01-01T00:00:00Z", "asof_bar": 7,
        }

    _, _, _, state = run_sequence_traced(
        _frame(displacement_at=9), h4, SequenceConfig(), audit={}, htf="H4",
    )

    anchor = state.context_anchor
    assert anchor["anchor_htf"] == "H4"
    assert anchor["layers"]["H4"]["asof_bar"] == 7
    assert anchor["layers"]["H4"]["asof_time"] == "2026-01-01T00:00:00Z"
    assert SequenceState.from_snapshot(state.to_snapshot()).context_anchor == anchor


def test_event_driven_wait_accepts_bos_after_an_extended_confirmation_gap():
    frame = _frame(n=18, displacement_at=3)
    frame.loc[12, "bos_dir"] = 1
    audit = {}
    _, phase_seen, _, state = run_sequence_traced(
        frame, _bullish, SequenceConfig(), audit=audit,
    )

    assert phase_seen["BOS"] == 1
    assert state.phase == "BOS_DONE"
    assert audit["invalidations"] == []


def test_explicit_legacy_window_still_expires_and_is_audited():
    audit = {}
    _, _, expedientes, state = run_sequence_traced(
        _frame(), _bullish, SequenceConfig(displace_gap=2), audit=audit,
    )

    assert state.phase == "IDLE"
    assert len(expedientes) == 1
    assert expedientes[0].outcome == "INVALID"
    assert audit["invalidations"][0]["reason"] == "TIMEOUT"


def _frame_with_confirmed_swing_break():
    frame = _frame(n=12)
    # El low de la barra 2 queda confirmado en la barra 4 (lookback causal=2)
    # antes del sweep de la barra 5; la barra 7 rompe ese nivel.
    frame.loc[0, "low"] = 100.0
    frame.loc[1, "low"] = 99.0
    frame.loc[2, "low"] = 95.0
    frame.loc[3, "low"] = 98.0
    frame.loc[4, "low"] = 99.0
    frame.loc[:, "liquidity_sweep_down"] = False
    frame.loc[5, "liquidity_sweep_down"] = True
    frame.loc[7, "close"] = 94.0
    return frame


def test_confirmed_opposite_swing_break_is_identical_in_batch_and_traced_paths():
    frame = _frame_with_confirmed_swing_break()
    audit = {}
    _, batch_phase = run_sequence(
        frame, _bullish, SequenceConfig(), audit=audit,
    )

    traced_audit = {}
    _, traced_phase, traced_expedientes, traced_state = run_sequence_traced(
        frame, _bullish, SequenceConfig(), audit=traced_audit,
    )

    assert batch_phase == traced_phase
    assert traced_state.phase == "IDLE"
    assert len(traced_expedientes) == 1
    assert traced_expedientes[0].invalidation_reason
    assert audit["invalidations"][0]["reason"] == "OPPOSITE_SWING_BREAK"
    assert traced_audit["invalidations"][0]["reason"] == "OPPOSITE_SWING_BREAK"


def test_htf_range_suspends_then_resumes_event_driven_wait():
    def htf(i):
        return {"trend": "RANGING" if 4 <= i <= 8 else "BULLISH"}

    audit = {}
    _, phase_seen, expedientes, state = run_sequence_traced(
        _frame(displacement_at=9), htf, SequenceConfig(), audit=audit,
    )

    assert state.phase == "DISPLACE_DONE"
    assert phase_seen["DISPLACE"] == 1
    assert expedientes == []
    assert audit["invalidations"] == []
    assert len(audit["suspensions"]) == 1
    assert audit["suspensions"][0]["count"] == 5


def test_config_rejects_non_positive_or_boolean_legacy_windows():
    for value in (0, -1, True):
        try:
            SequenceConfig(displace_gap=value)
        except ValueError:
            continue
        raise AssertionError(f"expected invalid legacy gap: {value!r}")


def test_snapshot_resume_and_repeated_finalization_preserve_one_pending_record():
    frame = _frame(displacement_at=9)
    first_audit = {}
    _, _, _, first_state = run_sequence_traced(
        frame.iloc[:6].copy(), _bullish, SequenceConfig(), audit=first_audit,
    )
    restored = SequenceState.from_snapshot(first_state.to_snapshot())
    resumed_audit = {}
    _, phase_seen, _, resumed_state = run_sequence_traced(
        frame, _bullish, SequenceConfig(), initial_state=restored,
        start_i=5, audit=resumed_audit,
    )
    assert phase_seen["DISPLACE"] == 1
    assert resumed_state.phase == "DISPLACE_DONE"

    audit = {}
    runner = SequenceRunner(
        _candle_objects(frame, "M15"), None, SequenceConfig(),
        est_htf_fn=_bullish, audit=audit,
    )
    runner.run_all()
    runner.run_all(start_i=len(frame) - 1)
    assert len(audit["pending_end"]) == 1
