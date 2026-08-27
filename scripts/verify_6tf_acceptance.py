"""Acceptance checks for the causal visual replay.

The FULL/PREFIX gate is intentionally an artifact-to-artifact comparison. A
single artifact can prove that it has no obvious future timestamp, but it cannot
prove that a PREFIX run reconstructs the same state as a FULL run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TFS = ["D1", "H4", "H1", "M15", "M5", "M1"]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compare_full_prefix(full: dict[str, Any], prefix: dict[str, Any]) -> dict[str, Any]:
    """Compare overlapping causal projections from a FULL and PREFIX artifact."""

    result = {"pass": False, "checked_snapshots": 0, "reason": ""}
    for key in ("symbol", "timeframe", "authority_tf", "schema_version"):
        if full.get(key) != prefix.get(key):
            result["reason"] = f"{key} differs"
            return result

    full_ms = full.get("market_state") or []
    prefix_ms = prefix.get("market_state") or []
    full_setups = full.get("setups") or []
    prefix_setups = prefix.get("setups") or []
    if not prefix_ms or len(prefix_ms) > len(full_ms):
        result["reason"] = "PREFIX must be non-empty and no longer than FULL"
        return result
    if len(prefix_setups) > len(full_setups):
        result["reason"] = "PREFIX setups must be no longer than FULL setups"
        return result

    full_candles = full.get("candles") or []
    prefix_candles = prefix.get("candles") or []
    if len(prefix_candles) > len(full_candles):
        result["reason"] = "PREFIX candles must be no longer than FULL candles"
        return result

    for index, prefix_snapshot in enumerate(prefix_ms):
        if prefix_snapshot.get("decision_time") != full_ms[index].get("decision_time"):
            result["reason"] = f"decision_time differs at snapshot {index}"
            return result
        if _canonical(prefix_snapshot) != _canonical(full_ms[index]):
            result["reason"] = f"market_state differs at snapshot {index}"
            return result
        if index >= len(prefix_setups) or index >= len(full_setups):
            result["reason"] = f"setup projection missing at snapshot {index}"
            return result
        if _canonical(prefix_setups[index]) != _canonical(full_setups[index]):
            result["reason"] = f"setup projection differs at snapshot {index}"
            return result
        result["checked_snapshots"] = index + 1

    result["pass"] = True
    result["reason"] = "FULL and PREFIX market_state/setup projections are identical on overlap"
    return result


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("full_artifact", type=Path, help="FULL visual_backtest.json")
    parser.add_argument(
        "--prefix-artifact",
        type=Path,
        help="PREFIX visual_backtest.json generated with the same start/config and a shorter end",
    )
    return parser


def main(path: str | Path, prefix_path: str | Path | None = None) -> int:
    payload = _load(path)
    checks: dict[str, bool] = {}

    # 1. origin_tf present in entities of market_state
    ms = payload.get("market_state") or []
    origin_tfs = set()
    for snap in ms:
        for ent in (snap.get("entities") or []):
            ot = ent.get("origin_tf")
            if ot:
                origin_tfs.add(ot)
    checks["1_origin_tf_6tf"] = origin_tfs.issuperset(set(REQUIRED_TFS))

    # 2. persistence: some entity lives in more than one snapshot
    ent_first: dict[str, int] = {}
    ent_last: dict[str, int] = {}
    for i, snap in enumerate(ms):
        for ent in (snap.get("entities") or []):
            eid = ent.get("id")
            if eid is None:
                continue
            ent_first.setdefault(eid, i)
            ent_last[eid] = i
    max_span = max((ent_last[e] - ent_first[e] for e in ent_first), default=0)
    checks["2_persistence_multibar"] = max_span >= 1

    # 3. lifecycle: more than one state is visible in the run
    states = set()
    for snap in ms:
        for ent in (snap.get("entities") or []):
            st = ent.get("state") or ent.get("object_state")
            if st:
                states.add(st)
    checks["3_lifecycle_varied"] = len(states) >= 2

    # 4. relation HTF -> LTF: setups expose the canonical navigation chain
    setups = payload.get("setups") or []
    checks["4_htf_ltf_chain"] = any("cadena_htf_ltf" in s for s in setups)

    # 5. AHF/Setup State: projection exposes state and present/missing context
    checks["5_ahf_setup_state"] = any(
        s.get("estado") and ("presentes" in s or "condiciones_presentes" in s)
        for s in setups
    )

    # 6. delta T-1 -> T: at least one entity change is visible
    checks["6_delta_T_minus_1"] = any(
        (snap.get("delta") or {}).get("created")
        or (snap.get("delta") or {}).get("transitioned")
        or (snap.get("delta") or {}).get("terminal")
        for snap in ms
    )

    # 7. no obvious future timestamp relative to the artifact's visible window
    candles = payload.get("candles") or []
    last_close = candles[-1]["bar_close_time"] if candles else None
    future_leak = any(
        snap.get("decision_time") and last_close and snap["decision_time"] > last_close
        for snap in ms
    )
    checks["7_zero_future_leak"] = not future_leak

    # 8. FULL == PREFIX must be proven by two artifacts, never inferred.
    comparison = {"pass": False, "checked_snapshots": 0, "reason": "PREFIX artifact not supplied"}
    if prefix_path is not None:
        comparison = compare_full_prefix(payload, _load(prefix_path))
    checks["8_full_eq_prefix"] = bool(comparison["pass"])

    all_pass = all(checks.values())
    print("=== GATE DE ACEPTACION 6 CAPAS ===")
    for key, value in checks.items():
        print(f"  {key}: {'PASS' if value else 'FAIL'}")
    print(f"ORIGIN_TFS={sorted(origin_tfs)}")
    print(f"MAX_PERSISTENCE_BARS={max_span}")
    print(f"LIFECYCLE_STATES={sorted(states)}")
    print(f"FULL_PREFIX_SNAPSHOTS={comparison['checked_snapshots']}")
    print(f"FULL_PREFIX_REASON={comparison['reason']}")
    print(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    args = _parser().parse_args()
    raise SystemExit(main(args.full_artifact, args.prefix_artifact))
