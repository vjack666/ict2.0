#!/usr/bin/env python3
"""Certificador reproducible del gate jerárquico D1→H4→H1→M15→M5→M1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.lineage import (
    SIX_TF_CHAIN,
    build_six_tf_lineage_spine,
    validate_six_tf_lineage,
)
from engine.market_object import MarketObject

CONTROL_B = pd.Timestamp("2026-08-24T20:35:00Z")
EXPECTED_ZIP_SHA256 = "359ef7e3219142422acec473ae786bd07de13043e2cf0e9a532a9e3eb1eab642"
WINDOW_START = {
    "D1": pd.Timestamp("2026-08-01T00:00:00Z"),
    "H4": pd.Timestamp("2026-08-15T00:00:00Z"),
    "H1": pd.Timestamp("2026-08-20T00:00:00Z"),
    "M15": pd.Timestamp("2026-08-23T00:00:00Z"),
    "M5": pd.Timestamp("2026-08-23T00:00:00Z"),
    "M1": pd.Timestamp("2026-08-24T00:00:00Z"),
}
TF_DURATION = {
    "D1": pd.Timedelta(days=1),
    "H4": pd.Timedelta(hours=4),
    "H1": pd.Timedelta(hours=1),
    "M15": pd.Timedelta(minutes=15),
    "M5": pd.Timedelta(minutes=5),
    "M1": pd.Timedelta(minutes=1),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_member(zf: zipfile.ZipFile, member: str) -> str:
    h = hashlib.sha256()
    with zf.open(member) as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_window(
    zf: zipfile.ZipFile,
    member: str,
    tf: str,
    start: pd.Timestamp,
    decision_time: pd.Timestamp,
) -> pd.DataFrame:
    chunks = []
    duration = TF_DURATION[str(tf).upper()]
    with zf.open(member) as handle:
        for chunk in pd.read_csv(handle, chunksize=200_000):
            times = pd.to_datetime(chunk["time"], utc=True, errors="coerce")
            # Keep some future rows deliberately. The lineage builder itself
            # must exclude them by close_time <= decision_time.
            mask = (times >= start) & (times <= decision_time + duration * 3)
            if mask.any():
                part = chunk.loc[mask].copy()
                part["time"] = times.loc[mask]
                chunks.append(part)
    if not chunks:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    return pd.concat(chunks, ignore_index=True).sort_values("time").reset_index(drop=True)


def read_parquet_window(
    path: Path,
    tf: str,
    start: pd.Timestamp,
    decision_time: pd.Timestamp,
) -> pd.DataFrame:
    columns = ["time", "open", "high", "low", "close"]
    frame = pd.read_parquet(path, columns=columns)
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    duration = TF_DURATION[str(tf).upper()]
    mask = (times >= start) & (times <= decision_time + duration * 3)
    out = frame.loc[mask].copy()
    out["time"] = times.loc[mask]
    return out.sort_values("time").reset_index(drop=True)


def _fingerprint(objects: list[MarketObject]) -> list[dict]:
    return [
        {
            "id": obj.id,
            "tf": obj.origin_tf,
            "parent": obj.parent_object,
            "time": str(obj.tradable_time),
            "bar_index": obj.bar_index,
        }
        for obj in objects
    ]


def _prefix(frames: dict[str, pd.DataFrame], t: pd.Timestamp) -> dict[str, pd.DataFrame]:
    out = {}
    for tf, frame in frames.items():
        times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
        close_times = times + TF_DURATION[tf]
        out[tf] = frame.loc[close_times <= t].copy().reset_index(drop=True)
    return out


def run_checks(frames: dict[str, pd.DataFrame], decision_time: pd.Timestamp) -> dict:
    full_objects, full_layers = build_six_tf_lineage_spine(
        frames, decision_time, symbol="EURUSD"
    )
    full = validate_six_tf_lineage(full_objects, decision_time=decision_time)

    pref_frames = _prefix(frames, decision_time)
    pref_objects, pref_layers = build_six_tf_lineage_spine(
        pref_frames, decision_time, symbol="EURUSD"
    )
    pref = validate_six_tf_lineage(pref_objects, decision_time=decision_time)

    roundtrip_payload = json.loads(json.dumps([obj.to_dict() for obj in full_objects]))
    restored = [MarketObject.from_dict(item) for item in roundtrip_payload]
    restored_result = validate_six_tf_lineage(restored, decision_time=decision_time)

    edge_checks = {}
    for idx in range(1, len(SIX_TF_CHAIN)):
        broken = [MarketObject.from_dict(obj.to_dict()) for obj in full_objects]
        broken[idx].parent_object = None
        verdict = validate_six_tf_lineage(broken, decision_time=decision_time)
        edge = f"{SIX_TF_CHAIN[idx - 1]}→{SIX_TF_CHAIN[idx]}"
        edge_checks[edge] = not verdict.valid

    missing_checks = {}
    for tf in SIX_TF_CHAIN:
        broken = [
            MarketObject.from_dict(obj.to_dict())
            for obj in full_objects
            if obj.origin_tf != tf
        ]
        verdict = validate_six_tf_lineage(broken, decision_time=decision_time)
        missing_checks[tf] = (not verdict.valid) and tf in verdict.missing_tfs

    future_objects = [MarketObject.from_dict(obj.to_dict()) for obj in full_objects]
    if future_objects:
        leaf = future_objects[-1]
        future_time = decision_time + pd.Timedelta(minutes=1)
        leaf.creation_time = future_time
        leaf.bar_time = future_time
        leaf.candidate_time = future_time
        leaf.confirmation_time = future_time
        leaf.tradable_time = future_time
    future_result = validate_six_tf_lineage(future_objects, decision_time=decision_time)

    full_fp = _fingerprint(full_objects)
    pref_fp = _fingerprint(pref_objects)
    result = {
        "decision_time": decision_time.isoformat(),
        "required_chain": list(SIX_TF_CHAIN),
        "full": full.to_dict(),
        "prefix": pref.to_dict(),
        "full_layers": full_layers,
        "prefix_layers": pref_layers,
        "full_prefix_identical": full_fp == pref_fp,
        "save_load_roundtrip": restored_result.valid and _fingerprint(restored) == full_fp,
        "edge_fail_closed": edge_checks,
        "missing_tf_fail_closed": missing_checks,
        "future_object_rejected": not future_result.valid,
    }
    result["all_pass"] = bool(
        full.valid
        and pref.valid
        and result["full_prefix_identical"]
        and result["save_load_roundtrip"]
        and all(edge_checks.values())
        and all(missing_checks.values())
        and result["future_object_rejected"]
        and all(layer.get("closed_only") for layer in full_layers.values())
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--source", help="Original EURUSD.zip benchmark package")
    source_group.add_argument(
        "--parquet-dir",
        default=None,
        help="Directory containing EURUSD_D1/H4/H1/M15/M5/M1.parquet",
    )
    parser.add_argument(
        "--manifest",
        default="benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json",
    )
    parser.add_argument(
        "--output",
        default="reports/audits/experiments/temporal/CHATGPT_FULL_SIXTF_LINEAGE_GATE_20260921.json",
    )
    args = parser.parse_args()

    hashes = {}
    frames = {}
    provenance = {}

    if args.source:
        source = Path(args.source)
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
        selected = manifest["SOURCE_PROFILE_RECENT"]
        by_name = {row["filename"]: row for row in manifest["files"]}
        source_hash = sha256_file(source)

        with zipfile.ZipFile(source) as zf:
            for tf in SIX_TF_CHAIN:
                filename = selected[tf]
                member = f"EURUSD/{filename}"
                actual = sha256_member(zf, member)
                expected = by_name[filename]["sha256"]
                hashes[tf] = {
                    "filename": filename,
                    "actual_sha256": actual,
                    "expected_sha256": expected,
                    "pass": actual == expected,
                }
                frames[tf] = read_window(zf, member, tf, WINDOW_START[tf], CONTROL_B)

        provenance = {
            "mode": "BENCHMARK_ZIP",
            "source": str(source),
            "source_zip_sha256": source_hash,
            "source_zip_expected": EXPECTED_ZIP_SHA256,
            "source_zip_pass": source_hash == EXPECTED_ZIP_SHA256,
            "source_hashes": hashes,
        }
        provenance_pass = bool(
            provenance["source_zip_pass"]
            and all(item["pass"] for item in hashes.values())
        )
    else:
        parquet_dir = Path(args.parquet_dir or "data/raw/EURUSD")
        missing_files = []
        local_files = {}
        for tf in SIX_TF_CHAIN:
            path = parquet_dir / f"EURUSD_{tf}.parquet"
            if not path.is_file():
                missing_files.append(str(path))
                continue
            local_files[tf] = {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            frames[tf] = read_parquet_window(path, tf, WINDOW_START[tf], CONTROL_B)

        provenance = {
            "mode": "LOCAL_PARQUET",
            "parquet_dir": str(parquet_dir),
            "files": local_files,
            "missing_files": missing_files,
        }
        provenance_pass = not missing_files and len(frames) == len(SIX_TF_CHAIN)

    checks = run_checks(frames, CONTROL_B) if provenance_pass else {
        "all_pass": False,
        "required_chain": list(SIX_TF_CHAIN),
        "error": "source_provenance_incomplete",
    }
    result = {
        "schema_version": "FULL_SIXTF_LINEAGE_GATE_V1",
        "provenance": provenance,
        **checks,
    }
    result["all_pass"] = bool(provenance_pass and checks["all_pass"])

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "all_pass": result["all_pass"],
        "provenance_mode": provenance.get("mode"),
        "provenance_pass": provenance_pass,
        "full_lineage": result.get("full", {}).get("valid", False),
        "full_prefix_identical": result.get("full_prefix_identical", False),
        "save_load_roundtrip": result.get("save_load_roundtrip", False),
        "edges": result.get("edge_fail_closed", {}),
        "missing_tfs": result.get("missing_tf_fail_closed", {}),
        "future_object_rejected": result.get("future_object_rejected", False),
        "output": str(out),
    }, indent=2))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
