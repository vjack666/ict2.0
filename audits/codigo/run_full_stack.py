"""CLI reproducible para ejecutar evidencia A0-A9 real o contract-smoke."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .audit_stack import run_stack
from .full_stack import run_real_stack

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "audits"


def smoke_rows():
    return [
        {"id": "bar-1", "time": 1, "open": 1.10, "high": 1.20, "low": 1.00, "close": 1.15},
        {"id": "bar-2", "time": 2, "open": 1.15, "high": 1.25, "low": 1.05, "close": 1.20},
        {"id": "bar-3", "time": 3, "open": 1.20, "high": 1.30, "low": 1.10, "close": 1.25},
    ]


def smoke_events():
    return [
        {"id": "evt-1", "candidate_time": 1, "confirmation_time": 2, "tradable_time": 2, "observation_time": 2},
    ]


def smoke_funnel():
    return [
        {"stage": "VALID_BARS", "id": "b1", "accepted": True, "direction": 1},
        {"stage": "STRUCTURE", "id": "s1", "accepted": True, "direction": 1},
        {"stage": "BOS_CHOCH", "id": "c1", "accepted": True, "direction": 1},
        {"stage": "DISPLACEMENT", "id": "d1", "accepted": True, "direction": 1},
        {"stage": "FVG", "id": "f1", "accepted": True, "direction": 1},
        {"stage": "OB", "id": "o1", "accepted": True, "direction": 1, "ob_type": "CANONICAL"},
        {"stage": "CONFLUENCE", "id": "x1", "accepted": True, "direction": 1},
        {"stage": "LINEAGE", "id": "l1", "accepted": True, "direction": 1},
        {"stage": "SETUP", "id": "u1", "accepted": True, "direction": 1},
        {"stage": "SETUP", "id": "u2", "accepted": True, "direction": -1},
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("real", "smoke"), default="real")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.scope == "real":
        stack = run_real_stack()
    else:
        stack = run_stack(smoke_rows(), smoke_events(), smoke_funnel())
        stack["scope"] = "contract-smoke"
    stack["timestamp"] = datetime.now(timezone.utc).isoformat()
    path = OUT / "A0_A9_audit_stack.json"
    path.write_text(json.dumps(stack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stack, ensure_ascii=False, indent=2))
    return 0 if stack["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
