#!/usr/bin/env python3
"""Print the causal-gate divergence summary without running any experiment."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "reports" / "audits" / "experiments" / "seq_ctx_01" / "gate_causal.json"


def main() -> int:
    if not GATE.exists():
        print(json.dumps({"status": "MISSING", "path": str(GATE)}))
        return 2
    report = json.loads(GATE.read_text(encoding="utf-8"))
    violations = report.get("violations", [])
    fields = Counter(key for row in violations for key in row.get("diff_keys", []))
    result = {
        "status": report.get("status"),
        "violations": len(violations),
        "diff_fields": fields,
        "interpretation": "No divergence to diagnose" if not violations else "Inspect the listed FULL/PREFIX fields before changing infrastructure",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False, default=dict))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
