"""New visual-backtest consumer for the canonical ICT engine.

This package is intentionally a consumer boundary.  Strategy and detector
decisions remain in ``engine/``; this package only replays them and serializes
their causal observability for ICT Structure Lab.
"""

from backtest.replay import ReplayConfig, load_raw_frames, run_visual_replay
from backtest.mtf_replay import MTFReplayOrchestrator, ReplayConfig as MTFReplayConfig

__all__ = [
    "ReplayConfig",
    "load_raw_frames",
    "run_visual_replay",
    "MTFReplayConfig",
    "MTFReplayOrchestrator",
]
