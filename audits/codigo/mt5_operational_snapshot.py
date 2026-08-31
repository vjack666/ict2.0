"""Auditoría independiente del ensamblaje operativo MT5 v1.

Verifica el puente sin modificar datasets ni refrescar la terminal. El runner
separa el PASS mecánico del puente de la frescura del feed: esta última depende
del gate fail-closed de ``scripts.daily.brief_lunes`` y no se inventa aquí.

Uso:
    python -m audits.codigo.mt5_operational_snapshot --out <reporte.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from engine.mt5_operational_snapshot import build_mt5_operational_snapshot


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_TFS = ("D1", "H4", "H1", "M15", "M5", "M1")


def _frames(start: str = "2024-01-01", n: int = 8) -> dict[str, pd.DataFrame]:
    times = pd.date_range(start, periods=n, freq="h", tz="UTC")
    rows = [
        (1.1000, 1.1010, 1.0990, 1.0995),
        (1.0995, 1.1000, 1.0990, 1.0998),
        (1.1005, 1.1020, 1.1005, 1.1015),
        (1.1000, 1.1005, 1.0985, 1.0990),
        (1.0990, 1.0995, 1.0975, 1.0980),
        (1.0980, 1.0990, 1.0970, 1.0985),
        (1.0985, 1.1000, 1.0980, 1.0995),
        (1.0995, 1.1000, 1.0985, 1.0990),
    ][:n]
    return {
        tf: pd.DataFrame({
            "time": times,
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "tick_volume": [100] * n,
        })
        for tf in REQUIRED_TFS
    }


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _git_branch() -> str:
    return subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()


def _hash_files(paths: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    hashes: dict[str, str] = {}
    errors: list[str] = []
    for tf, raw in sorted(paths.items()):
        path = Path(raw)
        if not path.is_file():
            errors.append(f"{tf}:missing_file")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[tf] = digest
    return hashes, errors


def _check(name: str, status: str, details: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {"id": name, "status": status, "details": details, "evidence_refs": evidence or []}


def run() -> dict[str, Any]:
    t = pd.Timestamp("2024-01-01 04:00", tz="UTC")
    frames = _frames()
    checks: list[dict[str, Any]] = []

    base = build_mt5_operational_snapshot(
        frames, t, symbol="EURUSD", required_tfs=REQUIRED_TFS, generator_commit=_git_head()
    )
    checks.append(_check(
        "ASSEMBLY",
        "PASS" if base["status"] == "READY" and base["missing_timeframes"] == [] else "BLOCKED",
        f"status={base['status']}; missing={base['missing_timeframes']}; objects={len(base['object_projection'])}",
    ))
    checks.append(_check(
        "POLICY",
        "PASS" if base["policy"] == "OBSERVE_ONLY_NO_ORDER" and base["entry_authorized"] is False else "BLOCKED",
        "no execution fields are authorized",
    ))

    extended = {
        tf: pd.concat([df, _frames("2024-01-02", 2)[tf]], ignore_index=True)
        for tf, df in frames.items()
    }
    future = build_mt5_operational_snapshot(
        extended, t, symbol="EURUSD", required_tfs=REQUIRED_TFS, generator_commit=_git_head()
    )
    checks.append(_check(
        "FULL_PREFIX",
        "PASS" if base == future else "BLOCKED",
        "future rows do not alter the snapshot at decision_time",
    ))
    projection = base["object_projection"]
    authority_ok = all(
        obj.get("authority_tf") == obj.get("origin_tf")
        and pd.to_datetime(obj.get("creation_time"), utc=True) <= t
        for obj in projection
    )
    checks.append(_check(
        "AUTHORITY_AND_PIT",
        "PASS" if authority_ok else "BLOCKED",
        f"projected_objects={len(projection)}; authority_tf=origin_tf; creation<=T",
    ))
    try:
        json.dumps(base, sort_keys=True, allow_nan=False)
        serializable = True
    except (TypeError, ValueError):
        serializable = False
    checks.append(_check("SERIALIZATION", "PASS" if serializable else "BLOCKED", "JSON safe"))

    static_source = (ROOT / "engine" / "mt5_operational_snapshot.py").read_text(encoding="utf-8")
    boundary_ok = "from backtest" not in static_source and "entry_authorized=True" not in static_source
    checks.append(_check(
        "BOUNDARY",
        "PASS" if boundary_ok else "BLOCKED",
        "no backtest authority and no true entry authorization",
    ))

    source_paths = {
        tf: str(ROOT / "data" / "raw" / "EURUSD" / f"EURUSD_{tf}.parquet")
        for tf in REQUIRED_TFS
    }
    hashes, hash_errors = _hash_files(source_paths)
    real: dict[str, Any] | None = None
    if len(hashes) == len(REQUIRED_TFS) and not hash_errors:
        real = build_mt5_operational_snapshot(
            frames,
            t,
            symbol="EURUSD",
            required_tfs=REQUIRED_TFS,
            source_files=source_paths,
            source_hashes=hashes,
            generator_commit=_git_head(),
        )
        provenance_ok = real["provenance"]["status"] == "PASS" and len(real["source_artifacts"]) == 6
        checks.append(_check("PROVENANCE", "PASS" if provenance_ok else "BLOCKED", "six local parquet hashes verified"))
        freshness_status = "REVIEW"
        freshness_detail = "not run: no MT5 refresh authorized in this audit"
    else:
        checks.append(_check("PROVENANCE", "REVIEW", f"errors={hash_errors}"))
        freshness_status = "REVIEW"
        freshness_detail = "local source artifacts incomplete"
    checks.append(_check("MT5_FRESHNESS", freshness_status, freshness_detail))

    worktree_state = "CLEAN" if not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip() else "DIRTY"
    checks.append(_check(
        "REPRODUCIBILITY",
        "PASS" if worktree_state == "CLEAN" else "REVIEW",
        f"generator_commit={_git_head()}; worktree_state={worktree_state}",
    ))

    hard_fail = any(check["status"] == "BLOCKED" for check in checks)
    technical_status = "BLOCKED" if hard_fail else "PASS"
    return {
        "schema_version": "MT5_OPERATIONAL_SNAPSHOT_AUDIT_V1",
        "mode": "AUDIT_ONLY",
        "status": technical_status,
        "operational_freshness": freshness_status,
        "generator_commit": _git_head(),
        "generator": {
            "script": "audits/codigo/mt5_operational_snapshot.py",
            "commit": _git_head(),
            "branch": _git_branch(),
            "worktree_state": worktree_state,
        },
        "source_artifacts": (real or {}).get("source_artifacts", []),
        "source_hashes": (real or {}).get("source_hashes", hashes),
        "checks": checks,
        "scope": {
            "source": "MT5_LOCAL_PARQUET",
            "symbol": "EURUSD",
            "timeframes": list(REQUIRED_TFS),
            "refresh_executed": False,
            "dukascopy_used": False,
            "orders_or_backtest": False,
        },
        "next_action": "Run the local MT5 freshness gate before operational use; then independent GO for publication.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = run()
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"], "operational_freshness": report["operational_freshness"], "out": str(path)}))
    return 0 if report["status"] != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
