"""Validate the frozen intraday M15 execution contract.

This is a configuration/invariant gate, not a performance backtest. It verifies
source hashes, the frozen profile, and that execution levels do not change when
future candles are appended to a synthetic closed-candle frame.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from engine.execution import fine_execution

ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "docs" / "planificacion" / "EXECUTION_FREEZE_2026-08-22.json"


def _sha256(path: Path) -> str:
    """Hash the committed Git blob when clean; use worktree bytes for a draft."""
    rel = path.relative_to(ROOT).as_posix()
    try:
        dirty = subprocess.run(
            ["git", "diff", "--quiet", "--", rel],
            cwd=ROOT,
            check=False,
        ).returncode != 0
        if not dirty:
            blob = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT)
            return hashlib.sha256(blob).hexdigest()
    except (OSError, subprocess.CalledProcessError):
        pass
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_frames() -> dict[str, pd.DataFrame]:
    times = pd.date_range("2026-01-05 12:00", periods=12, freq="15min", tz="UTC")
    close = [1.1000, 1.1050, 1.0980, 1.1080, 1.1020, 1.1120, 1.1060, 1.1160, 1.1090, 1.1190, 1.1130, 1.1230]
    rows = [{"time": t, "open": c - 0.001, "high": c + 0.003, "low": c - 0.004, "close": c} for t, c in zip(times, close)]
    return {"M15": pd.DataFrame(rows)}


def validate() -> dict:
    config = json.loads(FREEZE.read_text(encoding="utf-8"))
    profile = config["profile"]
    expected = config["source_hashes_sha256"]
    hashes = {path: _sha256(ROOT / path) for path in expected}
    hash_ok = hashes == expected
    contract_ok = (
        config["status"] == "FROZEN"
        and profile["htf"] == ["H1", "H4"]
        and profile["itf"] == "M15"
        and profile["exec_tf"] == "M15"
        and profile["timestamp_basis"] == "closed UTC candle; time <= decision_time"
        and profile["rr_min"] == 3.0
        and bool(config["prohibited"])
    )

    frames = _synthetic_frames()
    t = frames["M15"]["time"].iloc[-2]
    base = fine_execution(frames, t, 1, exec_tf="M15", rr=3.0)
    future = frames["M15"].iloc[[-1]].copy()
    future.loc[:, ["high", "low", "close"]] = [9.0, 0.1, 8.0]
    extended = {"M15": pd.concat([frames["M15"], future], ignore_index=True)}
    replay = fine_execution(extended, t, 1, exec_tf="M15", rr=3.0)
    result_ok = base.get("ok") and replay.get("ok") and base == replay and abs((base["tp"] - base["entry"]) / (base["entry"] - base["sl"]) - 3.0) < 1e-9
    return {
        "audit": "EXECUTION_FREEZE",
        "status": "PASS" if hash_ok and contract_ok and result_ok else "FAIL",
        "freeze_id": config["freeze_id"],
        "profile": profile,
        "source_hashes_match": hash_ok,
        "contract_valid": bool(contract_ok),
        "closed_candle_invariance": result_ok,
        "base_result": base,
        "replay_result": replay,
        "limitations": config["limitations"],
    }
