from __future__ import annotations

import json

from runtime.ai_learning.diagnostic_training import run_diagnostic_training
from runtime.ai_learning.outcome_classifier import (
    INTRADAY_FEATURE_PROFILES,
    INTRADAY_FEATURE_NAMES,
    OUTCOME_CLASSES,
)


def _row(index: int) -> dict:
    phase = ("ACCUMULATION", "DISTRIBUTION", "TRANSITION")[index % 3]
    event = ("SPRING", "UPTHRUST", "SOS")[index % 3]
    label = OUTCOME_CLASSES[index % 3]
    return {
        "episode_id": f"E{index:03d}",
        "event_time": f"2006-01-{(index // 3) + 1:02d}T00:{index % 3 * 15:02d}:00+00:00",
        "label_available_time": f"2006-01-{(index // 3) + 1:02d}T01:{index % 3 * 15:02d}:00+00:00",
        "direction": 1,
        "sequence_depth": 4,
        "features_at_t": {
            "context_inputs": {
                "sequence_direction": 1,
                "context_bucket": "ALIGNED",
                "h1_alignment": "ALIGNED",
                "d1_bias": "UNKNOWN",
                "h4_location": "UNKNOWN",
            },
            "sequence": ["STRUCTURE", "DISPLACEMENT", "FVG"],
            "intraday": {
                "ict_m15": {
                    "bos_bullish": True,
                    "bos_bearish": False,
                    "choch_bullish": False,
                    "choch_bearish": False,
                    "displacement_bullish": True,
                    "displacement_bearish": False,
                    "fvg_bullish": True,
                    "fvg_bearish": False,
                    "sweep_up": False,
                    "sweep_down": True,
                },
                "wyckoff": {
                    "H1": {"phase": phase, "events": [{"event_type": event}]},
                    "M15": {"phase": phase, "events": [{"event_type": event}]},
                },
            },
        },
        "label_end_12": label,
        "can_trade": False,
    }


def test_intraday_profile_trains_and_is_deterministic(tmp_path):
    source = tmp_path / "rows.jsonl"
    source.write_text(
        "\n".join(json.dumps(_row(i), sort_keys=True) for i in range(90)) + "\n",
        encoding="utf-8",
    )
    first = run_diagnostic_training(
        source,
        target="label_end_12",
        feature_names=INTRADAY_FEATURE_NAMES,
        code_commit="a" * 40,
    )
    second = run_diagnostic_training(
        source,
        target="label_end_12",
        feature_names=INTRADAY_FEATURE_NAMES,
        code_commit="a" * 40,
    )
    assert first == second
    assert first["status"] == "DIAGNOSTIC_ONLY_COMPLETED"
    assert first["fit_executed"] is True
    assert first["model"]["feature_names"] == list(INTRADAY_FEATURE_NAMES)
    assert first["can_trade"] is False


def test_registered_comparison_profiles_train_on_the_same_causal_rows(tmp_path):
    source = tmp_path / "rows.jsonl"
    source.write_text(
        "\n".join(json.dumps(_row(i), sort_keys=True) for i in range(90)) + "\n",
        encoding="utf-8",
    )
    results = {
        name: run_diagnostic_training(
            source,
            target="label_end_12",
            feature_names=features,
            code_commit="b" * 40,
        )
        for name, features in INTRADAY_FEATURE_PROFILES.items()
    }
    assert set(results) == {"ICT_ONLY", "WYCKOFF_ONLY", "WYCKOFF_ICT_COMBINED"}
    assert {result["input"]["sha256"] for result in results.values()} == {
        next(iter(results.values()))["input"]["sha256"]
    }
    assert len({
        json.dumps(result["temporal_split"], sort_keys=True)
        for result in results.values()
    }) == 1
    for name, result in results.items():
        assert result["status"] == "DIAGNOSTIC_ONLY_COMPLETED", name
        assert result["fit_executed"] is True
        assert result["can_trade"] is False
        assert result["model"]["feature_names"] == list(INTRADAY_FEATURE_PROFILES[name])
