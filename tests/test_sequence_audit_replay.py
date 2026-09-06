"""Consumer integration: lifecycle evidence travels without becoming labels."""
import pandas as pd

from backtest.replay import ReplayConfig, run_visual_replay
from scripts.lab.experiments.ai_outcome_funnel_bridge import build_funnel_artifact


def test_replay_transports_engine_audit_to_empty_blocked_funnel():
    frame = pd.DataFrame({
        "time": pd.date_range("2022-01-03", periods=25, freq="15min", tz="UTC"),
        "open": [1.1] * 25, "high": [1.101] * 25,
        "low": [1.099] * 25, "close": [1.1] * 25,
    })
    replay = run_visual_replay(
        {"M15": frame}, ReplayConfig(timeframes=("M15",))
    ).to_dict()
    assert replay["signals"] == []
    assert replay["metadata"]["config"]["displace_gap"] is None
    assert replay["metadata"]["config"]["bos_gap"] is None
    assert replay["metadata"]["sequence_audit"]
    funnel = build_funnel_artifact(replay, generator_commit="a" * 40)
    assert funnel["sequence_audit"] == replay["metadata"]["sequence_audit"]
    assert funnel["episodes"] == []
    assert funnel["aggregated_status"] == "BLOCKED"
    assert funnel["policy"]["can_trade"] is False
