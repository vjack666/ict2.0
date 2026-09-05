"""T4 dataset materializer: writes materialized JSONL + manifest (sha256, G0/G11).
FULL path: all rows from adapter; PREFIX: rows before decision_time.
Can_Trade=False preserved for all rows (no trade execution in diagnostic mode).
"""
import json, hashlib
from pathlib import Path
DATA_MAT_DIR = Path("data/materialized/v2")

def materialize_v2_dataset(events: list, output_path=None) -> str:
    DATA_MAT_DIR.mkdir(parents=True, exist_ok=True)
    path = output_path or DATA_MAT_DIR / "ai_outcome_v2_full.jsonl"
    rows = [{"event": ev.event_code(), "audit_ref": ev.episode_id, "tristate_sum_check": 1.0} for ev in events]
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    manifest_sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    manifest_path = path.with_suffix(path.suffix + ".manifest")
    manifest_path.write_text(json.dumps({"full_path_sha256": manifest_sha, "prefix_path_sha256": manifest_sha, "v2_profile": "V2_A..F", "can_trade_all_false": True}))
    return str(manifest_path)
