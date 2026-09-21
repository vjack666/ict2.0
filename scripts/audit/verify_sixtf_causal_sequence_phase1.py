#!/usr/bin/env python3
"""Independent Phase-1 verifier for the six-timeframe causal sequence context.

Scope: D1/H4/H1/M15/M5/M1 closed-only context, strict HTF provenance and
future invariance. This script does NOT certify the full six-TF funnel, episodes,
GRU, MT5 or trading readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.multitf_context import build_multitf_context
from engine.plan import build_multitf_closed_index
from engine.poi_anchor import build_htf_structure_index, resolve_htf_poi_event

TFS = ("D1", "H4", "H1", "M15", "M5", "M1")
EXPECTED_ZIP_SHA256 = "359ef7e3219142422acec473ae786bd07de13043e2cf0e9a532a9e3eb1eab642"
CONTROL_B = pd.Timestamp("2026-08-24T20:35:00Z")
CONTROL_A = pd.Timestamp("2026-09-17T18:20:00Z")
WINDOW_START = {
    "D1": pd.Timestamp("2024-01-01T00:00:00Z"),
    "H4": pd.Timestamp("2026-01-01T00:00:00Z"),
    "H1": pd.Timestamp("2026-06-01T00:00:00Z"),
    "M15": pd.Timestamp("2026-08-10T00:00:00Z"),
    "M5": pd.Timestamp("2026-08-10T00:00:00Z"),
    "M1": pd.Timestamp("2026-08-20T00:00:00Z"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_member(zf: zipfile.ZipFile, member: str) -> str:
    h = hashlib.sha256()
    with zf.open(member) as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_window(zf: zipfile.ZipFile, member: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    chunks = []
    with zf.open(member) as fh:
        for chunk in pd.read_csv(fh, chunksize=200_000):
            times = pd.to_datetime(chunk["time"], utc=True, errors="coerce")
            mask = (times >= start) & (times <= end)
            if mask.any():
                selected = chunk.loc[mask].copy()
                selected["time"] = times.loc[mask]
                chunks.append(selected)
    if not chunks:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    return pd.concat(chunks, ignore_index=True).sort_values("time").reset_index(drop=True)


def context_fingerprint(ctx: dict) -> dict:
    keep = (
        "available", "trend", "close", "high", "low", "sweep_up", "sweep_down",
        "bos_dir", "choch", "fvg_state", "ob_dir", "time", "asof_time", "asof_bar",
        "pd_side", "momentum", "momentum_delta", "bars",
    )
    return {
        tf: {k: ctx.get(tf, {}).get(k) for k in keep if k in ctx.get(tf, {})}
        for tf in TFS
    }


def event_fingerprint(event):
    if event is None:
        return None
    return {
        "time": pd.Timestamp(event.time).isoformat(),
        "direction": int(event.direction),
        "kind": event.kind,
        "tf": event.tf,
        "level": event.level,
        "bar_index": event.bar_index,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Path to the original EURUSD.zip")
    ap.add_argument("--manifest", default="benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json")
    ap.add_argument("--output", default="reports/audits/experiments/temporal/CHATGPT_SIXTF_CAUSAL_SEQUENCE_PHASE1_REAL_B.json")
    args = ap.parse_args()

    source = Path(args.source)
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    selected = manifest["SOURCE_PROFILE_RECENT"]
    by_name = {row["filename"]: row for row in manifest["files"]}

    result = {
        "scope": "SIX_TF_CAUSAL_SEQUENCE_PHASE1_ONLY",
        "controls": {"B": CONTROL_B.isoformat(), "A": CONTROL_A.isoformat()},
        "source_zip": str(source),
        "source_zip_sha256": sha256_file(source),
        "source_zip_sha256_expected": EXPECTED_ZIP_SHA256,
        "source_hashes": {},
        "real_control_b": {},
        "control_a_limitation": {},
        "all_pass": False,
    }
    result["zip_hash_pass"] = result["source_zip_sha256"] == EXPECTED_ZIP_SHA256

    with zipfile.ZipFile(source) as zf:
        for tf in TFS:
            filename = selected[tf]
            member = f"EURUSD/{filename}"
            actual = sha256_member(zf, member)
            expected = by_name[filename]["sha256"]
            result["source_hashes"][tf] = {
                "filename": filename,
                "actual_sha256": actual,
                "expected_sha256": expected,
                "pass": actual == expected,
                "manifest_first_time": by_name[filename].get("first_time"),
                "manifest_last_time": by_name[filename].get("last_time"),
            }

        frames = {
            tf: read_window(
                zf,
                f"EURUSD/{selected[tf]}",
                WINDOW_START[tf],
                CONTROL_B + pd.Timedelta(days=1),
            )
            for tf in TFS
        }

    prefix = {tf: df.loc[df["time"] <= CONTROL_B].reset_index(drop=True) for tf, df in frames.items()}
    full_index = build_multitf_closed_index(frames, CONTROL_B)
    pref_index = build_multitf_closed_index(prefix, CONTROL_B)
    full_ctx = build_multitf_context(frames, CONTROL_B, closed_index=full_index)
    pref_ctx = build_multitf_context(prefix, CONTROL_B, closed_index=pref_index)
    fp_full = context_fingerprint(full_ctx)
    fp_pref = context_fingerprint(pref_ctx)

    layers = {}
    all_closed = True
    all_available = True
    for tf in TFS:
        layer = full_ctx.get(tf, {})
        asof = pd.to_datetime(layer.get("asof_time", layer.get("time")), utc=True, errors="coerce")
        available = bool(layer.get("available"))
        closed = available and pd.notna(asof) and asof <= CONTROL_B
        all_available &= available
        all_closed &= closed
        layers[tf] = {
            "available": available,
            "asof_time": None if pd.isna(asof) else asof.isoformat(),
            "asof_bar": layer.get("asof_bar"),
            "rows_loaded": len(frames[tf]),
            "rows_prefix": len(prefix[tf]),
            "closed_at_or_before_T": bool(closed),
        }

    htf_full = build_htf_structure_index({tf: frames[tf] for tf in ("D1", "H4", "H1")})
    htf_pref = build_htf_structure_index({tf: prefix[tf] for tf in ("D1", "H4", "H1")})
    provenance = {}
    provenance_pass = True
    any_parent = False
    for direction in (1, -1):
        ef = resolve_htf_poi_event(htf_full, CONTROL_B, direction, strict_before=True)
        ep = resolve_htf_poi_event(htf_pref, CONTROL_B, direction, strict_before=True)
        ff = event_fingerprint(ef)
        pf = event_fingerprint(ep)
        stable = ff == pf
        strict = ef is None or pd.Timestamp(ef.time) < CONTROL_B
        any_parent |= ef is not None
        provenance_pass &= stable and strict
        provenance[str(direction)] = {
            "full": ff,
            "prefix": pf,
            "future_invariant": stable,
            "strictly_earlier_than_T": strict,
        }

    m1_last = pd.to_datetime(by_name[selected["M1"]].get("last_time"), utc=True)
    result["control_a_limitation"] = {
        "M1_last_time": m1_last.isoformat(),
        "control_a": CONTROL_A.isoformat(),
        "M1_covers_control_a": bool(m1_last >= CONTROL_A),
        "classification": "OUT_OF_RANGE_NOT_MISSING_DATA" if m1_last < CONTROL_A else "COVERED",
    }

    result["real_control_b"] = {
        "layers": layers,
        "all_six_layers_available": bool(all_available),
        "all_six_layers_closed_only": bool(all_closed),
        "future_invariance": fp_full == fp_pref,
        "full_context_fingerprint": fp_full,
        "prefix_context_fingerprint": fp_pref,
        "htf_provenance": provenance,
        "htf_provenance_future_invariance": bool(provenance_pass),
        "at_least_one_real_htf_parent": bool(any_parent),
    }

    result["all_pass"] = bool(
        result["zip_hash_pass"]
        and all(x["pass"] for x in result["source_hashes"].values())
        and all_available
        and all_closed
        and fp_full == fp_pref
        and provenance_pass
        and any_parent
        and result["control_a_limitation"]["M1_covers_control_a"] is False
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "all_pass": result["all_pass"],
        "zip_hash_pass": result["zip_hash_pass"],
        "source_hashes_pass": all(x["pass"] for x in result["source_hashes"].values()),
        "all_six_layers_available": all_available,
        "all_six_layers_closed_only": all_closed,
        "future_invariance": fp_full == fp_pref,
        "htf_provenance_future_invariance": provenance_pass,
        "at_least_one_real_htf_parent": any_parent,
        "control_a_m1_coverage": result["control_a_limitation"]["M1_covers_control_a"],
        "output": str(out),
    }, indent=2))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
