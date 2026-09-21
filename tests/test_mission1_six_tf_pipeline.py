from __future__ import annotations

from engine.mission1_six_tf_pipeline import (
    Mission1Config,
    build_ai_dataset_artifact,
    build_economic_backtest_artifact,
    build_six_tf_episode_artifact,
    run_mission1_pipeline,
    train_shadow_ai_artifact,
)


def test_f2_builds_only_six_tf_lineage_valid_episodes():
    artifact = build_six_tf_episode_artifact(Mission1Config(rows=6))

    assert artifact["status"] == "PASS"
    assert artifact["gates"]["M1_F2_SIX_TF_LINEAGE"] is True
    assert artifact["gates"]["M1_F2_FULL_PREFIX_LITERAL"] is True
    assert artifact["gates"]["M1_F2_NO_H4_M15_ONLY"] is True
    assert artifact["gates"]["can_trade"] is False
    assert len(artifact["episodes"]) == 6
    for episode in artifact["episodes"]:
        assert episode["lineage_status"] == "LINEAGE_VALID"
        assert episode["six_tfs_complete"] is True
        assert set(episode["lineage_provenance_by_tf"]) == {
            "D1", "H4", "H1", "M15", "M5", "M1"
        }


def test_f3_economic_backtest_is_shadow_and_resolved():
    episodes = build_six_tf_episode_artifact(Mission1Config(rows=6))
    backtest = build_economic_backtest_artifact(episodes)

    assert backtest["status"] == "PASS"
    assert backtest["can_trade"] is False
    assert backtest["economic_edge_claimed"] is False
    assert backtest["aggregates"]["resolved"] == 6
    assert all(trade["net_R"] is not None for trade in backtest["trades"])


def test_f4_dataset_separates_future_label_from_features():
    episodes = build_six_tf_episode_artifact(Mission1Config(rows=60))
    backtest = build_economic_backtest_artifact(episodes)
    dataset = build_ai_dataset_artifact(episodes, backtest)

    assert dataset["status"] == "PASS"
    assert dataset["can_trade"] is False
    assert dataset["aggregates"] == {
        "rows": 60,
        "design": 36,
        "validation": 12,
        "holdout": 12,
        "labels": {"continuation": 20, "reversal": 20, "failure": 20},
    }
    first = dataset["rows"][0]
    assert "label_end_6" in first
    assert "label_end_6" not in first["features_at_t"]
    assert first["label_available_time"] > first["event_time"]


def test_f5_shadow_training_runs_without_production_authority():
    episodes = build_six_tf_episode_artifact(Mission1Config(rows=60))
    backtest = build_economic_backtest_artifact(episodes)
    dataset = build_ai_dataset_artifact(episodes, backtest)
    training = train_shadow_ai_artifact(dataset)

    assert training["status"] == "PASS"
    assert training["fit_executed"] is True
    assert training["production_model_created"] is False
    assert training["can_trade"] is False
    assert training["metrics"]["holdout_rows"] == 12


def test_full_pipeline_writes_all_phase_artifacts(tmp_path):
    summary = run_mission1_pipeline(tmp_path, Mission1Config(rows=60))

    assert summary["status"] == "PASS"
    assert summary["can_trade"] is False
    assert set(summary["phases"].values()) == {"PASS"}
    for name in ("episodes", "backtest", "dataset", "training"):
        assert (tmp_path / f"mission1_{name}.json").exists()
    assert (tmp_path / "mission1_summary.json").exists()

