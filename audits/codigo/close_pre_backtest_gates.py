"""Close the two remaining pre-backtest gate conditions without running a backtest."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports" / "audits"


def _read(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def close() -> dict:
    stack = _read("A0_A9_audit_stack.json")
    freeze = _read("execution_freeze_2026-08-22.json")
    tna = _read("tna_streaming_prefix_2026-08-22.json")
    funnel = _read("mtf_seq_funnel.json")
    stack_pass = stack.get("status") == "PASS" and all(value == "PASS" for value in stack.get("gates", {}).values())
    funnel_pass = funnel.get("status") == "COMPLETE" and funnel.get("mtf_navigation", {}).get("ok_rate") == 1.0
    tna_pass = tna.get("gate") == "PASS" and tna.get("full_prefix") == "PASS_BY_LAYER_INDUCTION"
    freeze_pass = freeze.get("status") == "PASS" and freeze.get("freeze_id") == "EXECUTION_INTRADAY_M15_V1"
    conditions = {
        "A0_A9_FULL_STACK": stack_pass,
        "FUNNEL_20Y": funnel_pass,
        "TNA_FULL_PREFIX": tna_pass,
        "EXECUTION_FREEZE": freeze_pass,
    }
    return {
        "audit": "PRE_BACKTEST_GATE_CLOSE",
        "status": "PASS" if all(conditions.values()) else "BLOCKED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conditions": conditions,
        "backtest_authorization": "REQUIRES_EXPLICIT_CLIENT_DECISION",
        "policy": "NO_PNL_NO_ENTRY_NO_AUTOMATIC_PROMOTION",
        "scope_limitations": freeze.get("limitations", []),
        "artifacts": {
            "A0_A9": "reports/audits/A0_A9_audit_stack.json",
            "Funnel": "reports/audits/mtf_seq_funnel.json",
            "TNA": "reports/audits/tna_streaming_prefix_2026-08-22.json",
            "Execution": "reports/audits/execution_freeze_2026-08-22.json",
        },
    }


def main() -> int:
    result = close()
    path = REPORTS / "pre_backtest_gate_close_2026-08-22.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
