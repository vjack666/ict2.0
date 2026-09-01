from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lab.experiments.ai_outcome_train import TrainingRunnerBlocked, run_training


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = (
    ROOT
    / "runtime"
    / "ai_learning"
    / "snapshots"
    / "seq_ctx_01"
    / "canonical_bos"
    / "720b16a56e41a139317ba7687fe2b28e6345c7a6634f6183e2b5aef7321926d6"
)
OOS_GATE = ROOT / "data" / "learning" / "seq_ctx_01" / "OOS_EXPANSION" / "OOS_REDTEAM_VERDICT.json"


def test_current_snapshot_is_blocked_without_training_eligible_authorization(tmp_path):
    output = tmp_path / "outcome_classifier.json"

    with pytest.raises(TrainingRunnerBlocked, match="TRAINING_ELIGIBLE"):
        run_training(
            snapshot_path=SNAPSHOT,
            research_gate_path=OOS_GATE,
            output_path=output,
            registry_root=tmp_path / "registry",
            checkpoint_root=tmp_path / "checkpoints",
        )

    assert not output.exists()
    assert not (tmp_path / "registry").exists()
