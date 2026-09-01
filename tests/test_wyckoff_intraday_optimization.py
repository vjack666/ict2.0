from __future__ import annotations

from scripts.lab.experiments.wyckoff_intraday_optimize import (
    candidate_grid,
    selection_key,
)


def _candidate(profile: str, validation_log_loss: float, validation_accuracy: float) -> dict:
    return {
        "profile": profile,
        "learning_rate": 0.05,
        "l2": 0.0001,
        "metrics": {
            "validation": {
                "log_loss": validation_log_loss,
                "accuracy": validation_accuracy,
            },
            "test_oos": {"log_loss": 0.0, "accuracy": 0.0},
        },
    }


def test_grid_is_frozen_to_twelve_candidates():
    grid = list(candidate_grid())
    assert len(grid) == 12
    assert {item["profile"] for item in grid} == {
        "ICT_ONLY", "WYCKOFF_ONLY", "WYCKOFF_ICT_COMBINED"
    }
    assert {item["learning_rate"] for item in grid} == {0.02, 0.05}
    assert {item["l2"] for item in grid} == {0.0001, 0.001}


def test_selection_uses_validation_not_test_metrics():
    chosen = min(
        [
            _candidate("ICT_ONLY", 1.0, 0.5),
            _candidate("WYCKOFF_ONLY", 0.9, 0.1),
            _candidate("WYCKOFF_ICT_COMBINED", 0.9, 0.2),
        ],
        key=selection_key,
    )
    assert chosen["profile"] == "WYCKOFF_ICT_COMBINED"
