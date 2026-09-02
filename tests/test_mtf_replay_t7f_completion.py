from __future__ import annotations

import json

from audits.codigo.mtf_replay_t7f_completion import aggregate


def _report(year: int) -> dict:
    return {
        "year": year, "status": "PASS_TECHNICAL_BLOCKED_PROVENANCE",
        "gates": {"determinism": True, "full_prefix": True, "schema": True, "chunk_manifest": True},
        "counts": {"complete_records": 2, "eligible_records": 1, "episodes": 1},
        "checksum": f"checksum-{year}", "dataset_hash": f"dataset-{year}",
    }


def test_aggregate_requires_every_year_and_preserves_provenance_block(tmp_path):
    for year in range(2006, 2011):
        target = tmp_path / str(year)
        target.mkdir()
        (target / "t7f_audit.json").write_text(json.dumps(_report(year)), encoding="utf-8")
    result = aggregate(tmp_path)
    assert result["status"] == "PASS_TECHNICAL_BLOCKED_PROVENANCE"
    assert result["population"] == {"complete_records": 10, "eligible_records": 5, "episodes": 5}
    assert result["ai_training_authorized"] is False
    assert result["can_trade"] is False
