"""Evidencia reproducible A0-A9 sobre snapshot y artefactos versionados.

No calcula PnL, no descarga datos y no ejecuta un backtest. A0/A1/A5 leen el
snapshot Dukascopy; A2/A6/A7/A8 validan artefactos reales ya producidos por los
runners canónicos; A3/A4/A9 validan contratos, determinismo y gobernanza.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .audit_stack import a3_semantics, a4_metamorphic
from .data_integrity import audit_ohlc
from .gate import GateStatus

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "eurusd_dukascopy_20y"
REPORTS = ROOT / "reports" / "audits"
TFS = ("H1", "H4", "D1")


def _load_frames() -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for tf in TFS:
        path = DATASET / f"EURUSD_{tf}.csv"
        frame = pd.read_csv(path, parse_dates=["time"])
        frames[tf] = frame.sort_values("time").reset_index(drop=True)
    return frames


def _git_blob_sha(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    blob = subprocess.check_output(["git", "cat-file", "blob", f"HEAD:{rel}"])
    return hashlib.sha256(blob).hexdigest()


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _real_a0(frames: dict[str, pd.DataFrame]) -> tuple[str, dict[str, Any]]:
    per_tf: dict[str, Any] = {}
    ok = True
    for tf, frame in frames.items():
        result = audit_ohlc(frame.to_dict("records"), audit_id=f"A0_DATA_INTEGRITY_{tf}")
        per_tf[tf] = {
            "status": result.status.value,
            "rows": len(frame),
            "accepted": result.accepted_count,
            "findings": [f.__dict__ for f in result.findings],
            "audit_score": result.metrics.get("audit_score"),
        }
        ok = ok and result.status is GateStatus.PASS
    return _status(ok), per_tf


def _real_a1(frames: dict[str, pd.DataFrame]) -> tuple[str, dict[str, Any]]:
    required = ["time", "open", "high", "low", "close"]
    per_tf: dict[str, Any] = {}
    ok = True
    for tf, frame in frames.items():
        columns_ok = list(frame.columns) == required
        time_ok = frame["time"].notna().all() and frame["time"].is_monotonic_increasing and not frame["time"].duplicated().any()
        numeric_ok = all(pd.api.types.is_numeric_dtype(frame[col]) for col in required[1:])
        per_tf[tf] = {
            "columns": list(frame.columns),
            "columns_ok": columns_ok,
            "time_monotonic_unique": bool(time_ok),
            "numeric_ohlc": bool(numeric_ok),
            "rows": len(frame),
        }
        ok = ok and columns_ok and bool(time_ok) and bool(numeric_ok)
    return _status(ok), per_tf


def _real_a2() -> tuple[str, dict[str, Any]]:
    path = REPORTS / "tna_streaming_prefix_2026-08-22.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    event_checks = report.get("exact_event_checks", {})
    ok = (
        report.get("coverage") == "ALL_H1_DECISIONS"
        and report.get("mismatch_count_reported") == 0
        and report.get("full_prefix") == "PASS_BY_LAYER_INDUCTION"
        and bool(event_checks)
        and all(event_checks.values())
    )
    return _status(ok), {
        "artifact": str(path.relative_to(ROOT)),
        "coverage": report.get("coverage"),
        "decisions_checked": report.get("decisions_checked"),
        "mismatch_count_reported": report.get("mismatch_count_reported"),
        "event_checks_all_true": bool(event_checks) and all(event_checks.values()),
    }


def _real_a3() -> tuple[str, dict[str, Any]]:
    result = a3_semantics()
    required = [
        ROOT / "docs" / "contratos" / "CONTRATO_FUNNEL_AUDIT.md",
        ROOT / "docs" / "planificacion" / "SDD_FVG_OB_ARCHITECTURE_MAP.md",
        ROOT / "docs" / "PLAN_PRE_BACKTEST_AUDIT_STACK.md",
    ]
    ok = result.status is GateStatus.PASS and all(path.exists() for path in required)
    return _status(ok), {"required_contracts": [str(p.relative_to(ROOT)) for p in required]}


def _real_a5(frames: dict[str, pd.DataFrame]) -> tuple[str, dict[str, Any]]:
    h1 = frames["H1"]["time"].to_numpy()
    parents: dict[str, int] = {}
    ok = True
    for tf in ("H4", "D1"):
        parent = frames[tf]["time"].to_numpy()
        indices = parent.searchsorted(h1, side="right") - 1
        valid = bool((indices >= 0).all())
        if valid:
            valid = bool((parent[indices] <= h1).all())
        parents[tf] = int((indices >= 0).sum())
        ok = ok and valid
    return _status(ok), {"h1_decisions": len(h1), "mapped_parent_rows": parents, "no_future_parent": ok}


def _real_a6() -> tuple[str, dict[str, Any]]:
    path = REPORTS / "fvg_ob_funnel.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    per_tf: dict[str, Any] = {}
    ok = True
    for tf, item in report.get("timeframes", {}).items():
        links_ok = item.get("causal_links") == item.get("relation_count")
        status_ok = item.get("audit_status") == "PASS"
        per_tf[tf] = {
            "audit_status": item.get("audit_status"),
            "relation_count": item.get("relation_count"),
            "causal_links": item.get("causal_links"),
            "valid": links_ok and status_ok,
        }
        ok = ok and links_ok and status_ok
    return _status(ok), {"artifact": str(path.relative_to(ROOT)), "timeframes": per_tf}


def _real_a7() -> tuple[str, dict[str, Any]]:
    path = REPORTS / "mtf_seq_funnel.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    fvg_ok = all(item.get("audit_status") in {"GateStatus.PASS", "PASS"} for item in report.get("fvg_ob", {}).values())
    seq = report.get("sequence", {}).get("H1", {})
    nav = report.get("mtf_navigation", {})
    ok = report.get("status") == "COMPLETE" and fvg_ok and seq.get("audit_status") == "PASS" and nav.get("complete") is True and nav.get("ok_rate") == 1.0
    return _status(ok), {
        "artifact": str(path.relative_to(ROOT)),
        "status": report.get("status"),
        "fvg_pass": fvg_ok,
        "sequence_pass": seq.get("audit_status"),
        "mtf_complete": nav.get("complete"),
        "mtf_ok_rate": nav.get("ok_rate"),
    }


def _real_a8(frames: dict[str, pd.DataFrame]) -> tuple[str, dict[str, Any]]:
    path = REPORTS / "fvg_ob_funnel.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    per_tf: dict[str, Any] = {}
    ok = True
    for tf, item in report.get("timeframes", {}).items():
        frame = frames.get(tf)
        direction_ok = all(item.get(key, 0) > 0 for key in ("fvg_bull", "fvg_bear", "ob_bull", "ob_bear"))
        bars_ok = frame is not None and item.get("bars") == len(frame)
        per_tf[tf] = {
            "bars_match": bars_ok,
            "directional_coverage": direction_ok,
            "fvg_count": item.get("fvg_count"),
            "ob_count": item.get("ob_count"),
        }
        ok = ok and direction_ok and bars_ok
    return _status(ok), {"artifact": str(path.relative_to(ROOT)), "timeframes": per_tf}


def _real_a9() -> tuple[str, dict[str, Any]]:
    required = [
        ROOT / ".hermes-index.md",
        ROOT / "docs" / "PLAN_PRE_BACKTEST_AUDIT_STACK.md",
        ROOT / "docs" / "contratos" / "CONTRATO_FUNNEL_AUDIT.md",
        ROOT / ".hermes-worklog",
    ]
    reports = [REPORTS / "fvg_ob_funnel.json", REPORTS / "mtf_seq_funnel.json"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ok = all(path.exists() for path in required) and all(path.exists() for path in reports)
    return _status(ok), {
        "required_paths": [str(p.relative_to(ROOT)) for p in required],
        "commit": commit,
        "reports_present": ok,
        "policy": "NO_PNL_NO_ENTRY",
    }


def run_real_stack() -> dict[str, Any]:
    frames = _load_frames()
    statuses: dict[str, str] = {}
    evidence: dict[str, Any] = {}
    statuses["A0_DATA_INTEGRITY"], evidence["A0_DATA_INTEGRITY"] = _real_a0(frames)
    statuses["A1_SCHEMA"], evidence["A1_SCHEMA"] = _real_a1(frames)
    statuses["A2_POINT_IN_TIME"], evidence["A2_POINT_IN_TIME"] = _real_a2()
    statuses["A3_SEMANTICS"], evidence["A3_SEMANTICS"] = _real_a3()
    a4 = a4_metamorphic()
    statuses["A4_DETECTOR_METAMORPHIC"] = a4.status.value
    evidence["A4_DETECTOR_METAMORPHIC"] = {"status": a4.status.value, "findings": [f.__dict__ for f in a4.findings]}
    statuses["A5_CROSS_TIMEFRAME"], evidence["A5_CROSS_TIMEFRAME"] = _real_a5(frames)
    statuses["A6_LINEAGE"], evidence["A6_LINEAGE"] = _real_a6()
    statuses["A7_FUNNEL"], evidence["A7_FUNNEL"] = _real_a7()
    statuses["A8_COVERAGE_REGIME"], evidence["A8_COVERAGE_REGIME"] = _real_a8(frames)
    statuses["A9_GOVERNANCE"], evidence["A9_GOVERNANCE"] = _real_a9()

    csv_hashes = {
        name: {"manifest": digest, "git_blob": _git_blob_sha(DATASET / name)}
        for digest, name in (line.split()[:2] for line in (DATASET / "SHA256SUMS").read_text().splitlines())
    }
    hash_ok = all(item["manifest"] == item["git_blob"] for item in csv_hashes.values())
    payload = {"gates": statuses, "evidence": evidence, "hashes_match_git_blobs": hash_ok}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "audit": "A0_A9_FULL_STACK",
        "status": "PASS" if all(status == "PASS" for status in statuses.values()) and hash_ok else "FAIL",
        "scope": "versioned Dukascopy snapshot + versioned real Funnel/TNA evidence; no PnL/no entry",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "dataset": str(DATASET.relative_to(ROOT)),
        "csv_hashes": csv_hashes,
        "hashes_match_git_blobs": hash_ok,
        "gates": statuses,
        "evidence": evidence,
        "fingerprint": fingerprint,
    }
