"""Read-only readiness check for the next market opening.

This command never connects to a market feed, runs a strategy, places orders,
changes datasets, or enables trading. It validates local governance evidence.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "status": "PASS" if passed else "BLOCK", "detail": detail}


def run() -> tuple[int, dict[str, object]]:
    checks: list[dict[str, object]] = []

    state_path = ROOT / ".hermes" / "audit_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        score = float(state.get("audit_score", 0.0))
        passed = state.get("status") == "PASS" and score >= 0.80 and not state.get("temporal_violations")
        checks.append(check("audit_bootstrap", passed, f"status={state.get('status')} score={score:.3f}"))
    except (OSError, ValueError, TypeError) as error:
        checks.append(check("audit_bootstrap", False, f"unreadable: {error}"))

    guard = subprocess.run(
        [sys.executable, "scripts/architecture_guard.py"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    checks.append(check("architecture_guard", guard.returncode == 0, guard.stdout.strip() or guard.stderr.strip()))

    registry_path = ROOT / "governance" / "DEPARTMENT_REGISTRY.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        departments = registry.get("departments", [])
        ids = {item.get("id") for item in departments}
        checks.append(check("department_registry", ids == {f"D{i}" for i in range(8)}, f"departments={len(departments)}"))
    except (OSError, ValueError, TypeError) as error:
        checks.append(check("department_registry", False, f"unreadable: {error}"))

    graph_files = [ROOT / "graphify-out" / name for name in ("graph.json", "GRAPH_REPORT.md")]
    checks.append(check("graphify", all(path.is_file() for path in graph_files), "graph.json + GRAPH_REPORT.md"))

    scan_roots = [
        ROOT / name for name in (
            "AGENTS.md", "README.md", "start_hermes.py", "governance",
            "orchestration", "runtime", "engine", "analysis", "scripts",
        )
    ]
    source_files = []
    for scan_root in scan_roots:
        if scan_root.is_file():
            source_files.append(scan_root)
        elif scan_root.is_dir():
            source_files.extend(path for path in scan_root.rglob("*") if path.is_file())
    trade_enabled = False
    for path in source_files:
        if path == Path(__file__).resolve():
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yml", ".yaml", ".toml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "can_trade=true" in text.replace(" ", "").lower() or "can_trade: true" in text.lower():
            trade_enabled = True
            break
    checks.append(check("shadow_mode", not trade_enabled, "no can_trade=true found" if not trade_enabled else f"enabled in {path}"))

    checks.append(check("market_access", True, "not attempted; readiness check is local and read-only"))
    result = {"status": "PASS" if all(item["status"] == "PASS" for item in checks) else "BLOCK", "checks": checks}
    return (0 if result["status"] == "PASS" else 1), result


if __name__ == "__main__":
    code, result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(code)
