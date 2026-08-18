"""Auditor determinista de integridad OHLC."""
from __future__ import annotations

from typing import Any, Iterable

from .gate import AuditResult, Finding, GateStatus

REQUIRED = ("time", "open", "high", "low", "close")


def audit_ohlc(rows: Iterable[dict[str, Any]], audit_id: str = "A0_DATA_INTEGRITY") -> AuditResult:
    rows = list(rows)
    findings: list[Finding] = []
    accepted = 0
    previous_time = None
    for idx, row in enumerate(rows):
        rid = str(row.get("id", idx))
        missing = [c for c in REQUIRED if c not in row]
        if missing:
            findings.append(Finding("MISSING_COLUMN", "CRITICAL", f"missing columns: {missing}", "A0", rid))
            continue
        try:
            o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            if not all(v == v and abs(v) != float("inf") for v in (o, h, l, c)):
                findings.append(Finding("NONFINITE_OHLC", "CRITICAL", "OHLC contains NaN/inf", "A0", rid))
                continue
            if h < max(o, c) or l > min(o, c) or h < l:
                findings.append(Finding("INVALID_OHLC", "CRITICAL", "high/low violate OHLC invariants", "A0", rid))
                continue
            t = row["time"]
            if previous_time is not None and t <= previous_time:
                findings.append(Finding("NON_MONOTONIC_TIME", "CRITICAL", "timestamps are not strictly increasing", "A0", rid))
                continue
            previous_time = t
            accepted += 1
        except (TypeError, ValueError):
            findings.append(Finding("INVALID_NUMERIC", "CRITICAL", "OHLC is not numeric", "A0", rid))
    status = GateStatus.FAIL if findings else GateStatus.PASS
    invalid_rate = (len(rows) - accepted) / len(rows) if rows else 0.0
    score = max(0.0, 1.0 - invalid_rate)
    return AuditResult(audit_id, status, len(rows), accepted, len(rows) - accepted, tuple(findings), {
        "invalid_rate": invalid_rate,
        "audit_score": score,
    })
