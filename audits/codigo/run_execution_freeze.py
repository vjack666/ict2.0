"""CLI for the frozen execution contract gate."""
from __future__ import annotations

import json
from pathlib import Path

from .execution_freeze import ROOT, validate


def main() -> int:
    result = validate()
    path = ROOT / "reports" / "audits" / "execution_freeze_2026-08-22.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
