"""Read-only availability preflight for CME 6E/OI and EURUSD lineage.

This command never downloads data, calls a paid API, changes data/, or runs a
research workload. It writes only its own JSON audit artifact.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/audits/data/wyckoff_cme6e_availability_preflight.json"
ALLOWLIST = {
    "scripts/audit/wyckoff_cme6e_availability_preflight.py",
    "reports/audits/data/wyckoff_cme6e_availability_preflight.json",
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return result.stdout.strip()


def path_record(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "exists": path.exists()}


def local_files() -> list[Path]:
    result: list[Path] = []
    for root_name in ("data", "datasets"):
        root = ROOT / root_name
        if root.is_dir():
            result.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(result, key=lambda item: rel(item).lower())


def source_inventory(files: list[Path]) -> dict[str, Any]:
    cme: list[Path] = []
    oi: list[Path] = []
    eurusd: list[Path] = []
    for path in files:
        value = rel(path).lower()
        name = path.name.lower()
        is_6e = bool(re.search(r"(^|[/_.-])6e([/_.-]|$)", value))
        is_oi = any(token in value for token in ("open_interest", "open-interest", "openinterest"))
        if is_6e and ("cme" in value or "/6e" in value):
            cme.append(path)
        if is_oi:
            oi.append(path)
        if "eurusd" in value:
            eurusd.append(path)
    candidates = [
        "data/raw/CME/6E", "data/raw/CME/6E.csv", "data/raw/CME/6E.parquet",
        "data/raw/6E", "data/raw/6E.csv", "datasets/cme_6e",
        "datasets/cme_6e.csv", "datasets/6E.parquet",
    ]
    return {
        "cme_6e": {
            "status": "PASS" if cme else "BLOCKED",
            "found": [rel(path) for path in cme],
            "candidates": [path_record(ROOT / item) for item in candidates],
            "reason": "Local CME 6E source found." if cme else "No local CME 6E source; no substitution inferred.",
        },
        "open_interest": {
            "status": "PASS" if oi else "BLOCKED",
            "found": [rel(path) for path in oi],
            "reason": "Local open-interest source found." if oi else "No local open-interest source.",
        },
        "eurusd_local": [rel(path) for path in eurusd],
    }


def csv_schema(path: Path) -> dict[str, Any]:
    if path.suffix.lower() not in {".csv", ".tsv"}:
        return {"path": rel(path), "status": "REVIEW", "reason": "Non-text schema not decoded by stdlib preflight."}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
            row = next(csv.reader(handle, delimiter=delimiter))
        columns = [re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_") for value in row]
        required = {"timestamp": any(x in columns for x in ("time", "timestamp", "datetime", "date")),
                    "open": "open" in columns, "high": "high" in columns,
                    "low": "low" in columns, "close": "close" in columns,
                    "volume": any(x in columns for x in ("volume", "vol", "tick_volume")),
                    "open_interest": any(x in columns for x in ("open_interest", "oi", "openinterest"))}
        return {"path": rel(path), "status": "PASS", "columns": columns, "fields": required}
    except (OSError, UnicodeError, csv.Error, StopIteration) as exc:
        return {"path": rel(path), "status": "REVIEW", "reason": str(exc)}


def parse_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]{64})\s+[* ]?(.+?)\s*$", line)
        if match:
            result[Path(match.group(2)).name] = match.group(1).lower()
    return result


def dukascopy_audit() -> dict[str, Any]:
    root = ROOT / "datasets/eurusd_dukascopy_20y"
    manifest_path = root / "SHA256SUMS"
    metadata_path = root / "metadata.json"
    expected = parse_manifest(manifest_path)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        metadata = {}
    files = sorted(root.glob("EURUSD_*.csv")) if root.is_dir() else []
    checks = []
    for path in files:
        actual = sha256(path)
        expected_hash = expected.get(path.name)
        checks.append({"path": rel(path), "sha256_actual": actual,
                       "sha256_manifest": expected_hash,
                       "sha256_match": actual == expected_hash if expected_hash else False,
                       "metadata_present": path.stem.split("_")[-1] in metadata})
    ok = bool(files) and all(item["sha256_match"] and item["metadata_present"] for item in checks)
    return {"status": "PASS" if ok else ("REVIEW" if files else "BLOCKED"),
            "reason": "Dukascopy hashes and metadata agree." if ok else "Dukascopy evidence is incomplete or inconsistent.",
            "files": checks, "scope_note": "EURUSD spot bid OHLC is not a CME 6E/OI substitute."}


def contract_audit() -> dict[str, Any]:
    paths = [ROOT / "docs/tesis/SDD_LTF_ENTRY_LAYER.md", ROOT / "docs/tesis/PLAN_LTF_ENTRY_LAYER.md",
             ROOT / ".codex/skills/market-data-provenance/SKILL.md"]
    content = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths if path.is_file())
    rules = {name: bool(re.search(pattern, content, flags=re.IGNORECASE)) for name, pattern in {
        "timezone": r"timezone|zona horaria|UTC", "sessions": r"session|sesiones",
        "rollover": r"rollover|roll", "join_pit": r"join_id|join.*PIT|PIT.*join|snapshot_at",
        "volume_oi": r"CME_CENTRALIZED|open_interest",
    }.items()}
    return {"status": "PASS" if all(rules.values()) else "BLOCKED", "rules": rules,
            "paths": [rel(path) for path in paths if path.is_file()]}


def worktree_audit() -> dict[str, Any]:
    lines = [line for line in git("status", "--porcelain=v1", "--untracked-files=all").splitlines() if line]
    changed = []
    for line in lines:
        value = line[3:] if len(line) >= 4 else line
        changed.append(value.replace("\\", "/"))
    unexpected = sorted(path for path in changed if path not in ALLOWLIST)
    return {"status": "PASS" if not unexpected else "BLOCKED", "branch": git("branch", "--show-current") or "DETACHED_HEAD",
            "commit": git("rev-parse", "HEAD"), "changed_paths": changed,
            "unexpected_paths": unexpected, "allowlist": sorted(ALLOWLIST)}


def build_report() -> dict[str, Any]:
    files = local_files()
    inventory = source_inventory(files)
    schemas = [csv_schema(path) for path in files if "eurusd" in rel(path).lower() and path.suffix.lower() in {".csv", ".tsv"}]
    checks = {
        "CME_6E_LOCAL_SOURCE": inventory["cme_6e"],
        "OPEN_INTEREST_LOCAL_SOURCE": inventory["open_interest"],
        "EURUSD_LOCAL_SOURCE": {"status": "PASS" if inventory["eurusd_local"] else "BLOCKED", "found": inventory["eurusd_local"]},
        "EURUSD_SCHEMAS": {"status": "PASS" if schemas and all(item["status"] == "PASS" for item in schemas) else "REVIEW", "items": schemas},
        "DUKASCOPY_HASHES": dukascopy_audit(),
        "MARKET_DATA_CONTRACT": contract_audit(),
        "WORKTREE_STATE": worktree_audit(),
    }
    blocking = [name for name, item in checks.items() if item.get("status") == "BLOCKED"]
    return {
        "schema_version": "1.0", "preflight": "WYCKOFF-8", "mode": "AUDIT_ONLY",
        "status": "BLOCKED" if blocking else "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "blocking_checks": blocking,
        "not_run": ["download_or_network_access", "paid_api", "experiment_backtest_training", "data_mutation"],
        "next_action": "Register CME 6E OHLCV/OI with source, license, contract, roll, session and PIT join metadata; then rerun.",
    }


def main() -> int:
    report = build_report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": rel(REPORT), "blocking_checks": report["blocking_checks"]}, ensure_ascii=False))
    return 0 if report["status"] in {"PASS", "REVIEW"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
