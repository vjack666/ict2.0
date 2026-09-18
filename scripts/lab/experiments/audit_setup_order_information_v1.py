"""Read-only feature-information audit; does not train or change data.

Execute only the existing pure feature functions from their AST, avoiding
TensorFlow initialization and the trainer's output-writing entrypoint.
Print evidence to stdout; no model predictions or market-frequency claims.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent.parent.parents[3]s[3]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    trainer = ROOT / "scripts/lab/experiments/train_setup_quality_v1.py"
    tree = ast.parse(trainer.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef)
        and node.name in {"source_family", "extract_features"}
    ) or (
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SEQ_FEATURES" for t in node.targets)
    )]
    assert len(nodes) == 3, "Feature implementation changed; inspect before auditing"
    namespace: dict[str, Any] = {"Any": Any}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(trainer), "exec"), namespace)
    extract = namespace["extract_features"]
    result: dict[str, Any] = {
        "schema": "SETUP_ORDER_INFORMATION_AUDIT_V1",
        "can_trade": False, "entry_authorized": False,
        "trainer_sha256": digest(trainer), "splits": {},
        "scope": "feature extraction only; not prediction, edge, or causal certification",
    }
    record_path = ROOT / "data/ml/tensorflow/setup_quality_v1/training_record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    for split in ("train", "validation", "test_oos"):
        path = ROOT / f"data/ml/tensorflow/setup_grammar_v1/dataset_{split}.jsonl"
        before = digest(path)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        tested = unchanged = 0
        for row in rows:
            sequence = row.get("features_at_t", {}).get("sequence", [])
            if sequence == list(reversed(sequence)):
                continue
            changed = copy.deepcopy(row)
            changed["features_at_t"]["sequence"] = list(reversed(sequence))
            tested += 1
            unchanged += extract(row) == extract(changed)
        result["splits"][split.upper()] = {
            "n": len(rows), "reversed_sequences_tested": tested,
            "identical_feature_outputs": unchanged,
            "setup_decision_counts": dict(Counter(r["grammar_labels"]["setup_decision"] for r in rows)),
            "zone_counts": dict(Counter(r["grammar_labels"]["pd_array_zone"] for r in rows)),
            "sha256": before, "unchanged_after_read": before == digest(path),
            "matches_training_record": before == record["dataset_hashes"][split.upper()],
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
