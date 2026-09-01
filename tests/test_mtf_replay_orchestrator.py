from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from backtest.mtf_replay import (
    INTRADAY_H4_M15,
    INTRADAY_H4_M15_M5_REFINEMENT,
    MTFReplayOrchestrator,
    ReplayConfig,
    ReplayCheckpoint,
    canonical_frames,
    iter_close_batches,
    make_chunks,
    write_chunks,
)
from backtest.schema import validate_mtf_replay
from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState
from engine.sequential_outcome import TradeLevels
from engine.setup_builder import Setup


def _row(time: str, close: float = 1.1) -> dict:
    return {"time": time, "open": close, "high": close + 0.01, "low": close - 0.01, "close": close}


def _frames() -> dict:
    return {
        "H4": [_row("2024-01-01T04:00:00Z"), _row("2024-01-01T08:00:00Z")],
        "M15": [
            _row("2024-01-01T03:45:00Z"),
            _row("2024-01-01T04:00:00Z"),
            _row("2024-01-01T04:15:00Z"),
            _row("2024-01-01T04:30:00Z"),
        ],
    }


def _config(**overrides) -> ReplayConfig:
    values = dict(symbol="EURUSD", profile=INTRADAY_H4_M15, checkpoint_every=1, chunk_size=2)
    values.update(overrides)
    return ReplayConfig(**values)


def test_clock_batches_simultaneous_closes_htf_first_independent_of_input_order():
    canonical = canonical_frames(_frames())
    batches = list(iter_close_batches(canonical))
    simultaneous = next(rows for timestamp, rows in batches if timestamp.isoformat().startswith("2024-01-01T04:00"))
    assert [row["tf"] for row in simultaneous] == ["H4", "M15"]
    reversed_frames = {"M15": _frames()["M15"], "H4": _frames()["H4"]}
    assert list(iter_close_batches(canonical_frames(reversed_frames))) == batches


def test_orchestrator_emits_valid_deterministic_artifact_and_chunks():
    first = MTFReplayOrchestrator(_config(), MarketState()).run(_frames())
    second = MTFReplayOrchestrator(_config(), MarketState()).run(deepcopy(_frames()))
    validate_mtf_replay(first)
    assert first["checksum"] == second["checksum"]
    assert make_chunks(first, 1)["artifact_checksum"] == make_chunks(first, 3)["artifact_checksum"]
    assert all(tick["phases"][0] == "CLOSE_BATCH" for tick in first["timeline"])


def test_full_prefix_is_identical_for_every_observable_batch():
    full = MTFReplayOrchestrator(_config(), MarketState()).run(_frames())
    all_batches = list(iter_close_batches(canonical_frames(_frames())))
    for cut in range(1, len(all_batches) + 1):
        cutoff = all_batches[cut - 1][0]
        prefix_frames = {
            tf: [row for row in rows if __import__("pandas").to_datetime(row["time"], utc=True) <= cutoff]
            for tf, rows in _frames().items()
        }
        if any(not rows for rows in prefix_frames.values()):
            continue
        prefix = MTFReplayOrchestrator(_config(), MarketState()).run(prefix_frames)
        assert prefix["timeline"] == full["timeline"][:cut]
        assert prefix["state_deltas"] == full["state_deltas"][:cut]


def test_lower_tf_observation_cannot_kill_h4_object():
    created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    obj = MarketObject(
        id="OB-H4",
        symbol="EURUSD",
        type=ObjectType.ORDER_BLOCK,
        origin_tf="H4",
        role=Role.POI,
        direction=1,
        zone_low=1.0,
        zone_high=1.2,
        creation_time=created,
        state=ObjectState.ACTIVE,
        bar_index=0,
        candidate_bar=0,
        candidate_time=created,
        confirmation_bar=0,
        confirmation_time=created,
        tradable_bar=0,
        tradable_time=created,
    )
    state = MarketState()
    state.ingest(obj)
    frames = {
        "H4": [_row("2024-01-01T04:00:00Z", 1.5)],
        "M15": [{"time": "2024-01-01T04:00:00Z", "open": 1.01, "high": 1.02, "low": 0.98, "close": 0.99}],
    }
    MTFReplayOrchestrator(_config(), state).run(frames)
    assert state.all_objects()[0].state is ObjectState.ACTIVE
    assert len(state.all_objects()[0].meta["observations"]["M15"]) == 1


def test_checkpoint_resume_preserves_market_state_and_rejects_hash_mismatch():
    import pytest

    state = MarketState()
    partial = MTFReplayOrchestrator(_config(), state).run(_frames(), stop_after_batches=2)
    checkpoint = ReplayCheckpoint(**partial["market_state_checkpoints"][-1])
    resumed = MTFReplayOrchestrator(_config(), MarketState()).run(_frames(), resume=checkpoint)
    continuous = MTFReplayOrchestrator(_config(), MarketState()).run(_frames())
    assert resumed["market_state_checkpoints"][-1]["market_state"] == continuous["market_state_checkpoints"][-1]["market_state"]
    bad = ReplayCheckpoint(**{**checkpoint.to_dict(), "dataset_hash": "OTHER"})
    with pytest.raises(ValueError, match="CONFIG_MISMATCH"):
        MTFReplayOrchestrator(_config(), MarketState()).run(_frames(), resume=bad)


def test_execution_waits_one_bar_and_post_entry_invalidation_is_separate():
    def setups(_state, now, _ctx):
        if now.isoformat().startswith("2024-01-01T03:45") or now.isoformat().startswith("2024-01-01T04:00"):
            return [Setup(id="ephemeral", symbol="EURUSD", direction=1, created_at=now)]
        return []

    orchestrator = MTFReplayOrchestrator(
        _config(),
        MarketState(),
        setup_provider=setups,
        execution_plan_provider=lambda _setup, _now: TradeLevels(1, 1.1, 1.0, 1.3),
    )
    artifact = orchestrator.run(_frames())
    validate_mtf_replay(artifact)
    assert len(artifact["trades"]) == 1
    assert artifact["trades"][0]["observation_time"].startswith("2024-01-01T04:00")
    assert any(row["reason"] == "AUTHORITY_INVALIDATION_AFTER_ENTRY" for row in artifact["invalidations"])


def test_cancel_before_entry_removes_pending_plan_and_same_bar_never_fills():
    first_time = "2024-01-01T03:45"

    def setups(_state, now, _ctx):
        return [Setup(symbol="EURUSD", direction=1, created_at=now)] if now.isoformat().startswith(first_time) else []

    artifact = MTFReplayOrchestrator(
        _config(),
        MarketState(),
        setup_provider=setups,
        execution_plan_provider=lambda _setup, _now: TradeLevels(1, 1.1, 1.0, 1.3),
    ).run(_frames())
    assert artifact["trades"] == []
    assert any(row["reason"] == "CANCELLED_BEFORE_ENTRY" for row in artifact["invalidations"])


def test_m5_refinement_profile_uses_same_clock_without_extra_authority():
    frames = {
        **_frames(),
        "M5": [_row("2024-01-01T04:00:00Z"), _row("2024-01-01T04:05:00Z")],
    }
    config = _config(profile=INTRADAY_H4_M15_M5_REFINEMENT)
    artifact = MTFReplayOrchestrator(config, MarketState()).run(frames)
    validate_mtf_replay(artifact)
    tick = next(row for row in artifact["timeline"] if row["observation_time"].startswith("2024-01-01T04:00"))
    assert tick["closed_tfs"] == ["H4", "M15", "M5"]


def test_chunk_writer_materializes_lazy_files_without_semantic_drift(tmp_path):
    artifact = MTFReplayOrchestrator(_config(), MarketState()).run(_frames())
    manifest = write_chunks(artifact, tmp_path, 2)
    assert (tmp_path / "manifest.json").exists()
    assert all((tmp_path / chunk["path"]).exists() for chunk in manifest["chunks"])
    assert manifest["artifact_checksum"] == artifact["checksum"]
