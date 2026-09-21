#!/usr/bin/env python3
"""Independent real-data H4/M15 acceptance for causal replay (NO funnel PASS).

Run from any directory with --source ORIGINAL_EURUSD_ZIP [--manifest ...].
Stores A/B FULL/PREFIX, future injection, object metadata and source SHA.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.audit.ict_event_inventory import CONTROLS, MEMBERS, TFS, WARMUP, verify_sha256_manifest
from engine.causal_replay import replay_closed_bars
from engine.historical_event_objects import build_historical_event_objects
from engine.market_state import MarketState

WINDOW = {"H4": 120, "M15": 21}
PERIOD = {"H4": pd.Timedelta("4h"), "M15": pd.Timedelta("15min")}


def _object_signature(objects, at):
    return {o.id: o.to_dict() for o in objects if pd.Timestamp(o.tradable_time) <= at}


def _projection(projection):
    return {oid: obj.to_dict() for oid, obj in projection.items()}


def _frames(raw, cutoff, *, future=pd.Timedelta(0)):
    result = {}
    for tf, days in WINDOW.items():
        d = raw[tf]
        close = d["time"] + PERIOD[tf]
        mask = (d["time"] >= cutoff - pd.Timedelta(days=days)) & (close <= cutoff + future)
        f = d.loc[mask].copy()
        f["time"] = close.loc[mask]
        if f.empty:
            raise ValueError(f"NO_SOURCE_COVERAGE_{tf}_{cutoff}")
        result[tf] = f.reset_index(drop=True)
    return result


def verify(source: Path, manifest: Path, output: Path) -> dict:
    with ZipFile(source) as archive:
        hashes = verify_sha256_manifest(archive, manifest)
        raw = {}
        for tf in WINDOW:
            with archive.open(MEMBERS[tf]) as handle:
                d = pd.read_csv(handle, usecols=["time", "open", "high", "low", "close"])
            d["time"] = pd.to_datetime(d["time"], utc=True, errors="raise")
            if d["time"].duplicated().any() or not d["time"].is_monotonic_increasing:
                raise ValueError(f"DUPLICATE_OR_UNSORTED_{tf}")
            if d[["open", "high", "low", "close"]].isna().any().any():
                raise ValueError(f"MISSING_OHLC_{tf}")
            raw[tf] = d
    results = []
    for name in ("A", "B"):
        cutoff = pd.Timestamp(CONTROLS[name])
        frames = _frames(raw, cutoff)
        producer = build_historical_event_objects(frames)
        full = replay_closed_bars(frames, producer["objects"], as_of=cutoff)
        ms = full["market_state"]
        if type(ms) is not MarketState:
            raise AssertionError("not the real MarketState")
        projection = full["projection"]
        anchors = []
        for days in (14, 10, 7, 3, 1, 0):
            at = cutoff - pd.Timedelta(days=days)
            prefix_frames = {tf: frame.loc[frame["time"] <= at].reset_index(drop=True)
                             for tf, frame in frames.items()}
            prefix_producer = build_historical_event_objects(prefix_frames)
            expected = _object_signature(producer["objects"], at)
            observed = _object_signature(prefix_producer["objects"], at)
            from_full = _projection(ms.projection_at(at))
            from_prefix = _projection(replay_closed_bars(prefix_frames,
                                          prefix_producer["objects"], as_of=at)["projection"])
            leaks = [obj.id for obj in ms.projection_at(at).values()
                     if obj.invalidated_time is not None and pd.Timestamp(obj.invalidated_time) > at]
            anchors.append({"at": at.isoformat(), "full_prefix_producer": expected == observed,
                            "full_prefix_projection": from_full == from_prefix,
                            "future_invalidation_metadata_leaks": leaks,
                            "objects_at_T": len(from_full)})
        backwards = replay_closed_bars(dict(reversed(list(frames.items()))),
                                       list(reversed(producer["objects"])), as_of=cutoff)
        reverse_ok = _projection(backwards["projection"]) == _projection(projection)
        extended = _frames(raw, cutoff, future=pd.Timedelta("1d"))
        future_bars = sum(len(extended[tf]) - len(frames[tf]) for tf in frames)
        extended_producer = build_historical_event_objects(extended)
        future_producer_ok = (_object_signature(producer["objects"], cutoff) ==
                              _object_signature(extended_producer["objects"], cutoff))
        injected = replay_closed_bars(extended, extended_producer["objects"], as_of=cutoff)
        future_replay_ok = _projection(injected["projection"]) == _projection(projection)
        restored = MarketState.from_dict(ms.to_dict())
        roundtrip_ok = all(_projection(ms.projection_at(pd.Timestamp(row["at"]))) ==
                           _projection(restored.projection_at(pd.Timestamp(row["at"])))
                           for row in anchors)
        birth_leaks = []
        for obj in projection.values():
            at = pd.Timestamp(obj.tradable_time)
            snapshot = ms.projection_at(at)
            for old in snapshot.values():
                if old.invalidated_time is not None and pd.Timestamp(old.invalidated_time) > at:
                    birth_leaks.append({"birth_object": obj.id, "leaking_object": old.id})
        same_close_links = [o.id for o in producer["objects"] if o.parent_object
                            and next((p for p in producer["objects"] if p.id == o.parent_object
                                      and pd.Timestamp(p.tradable_time) >= pd.Timestamp(o.tradable_time)), None)]
        checks_pass = (all(row["full_prefix_producer"] and row["full_prefix_projection"]
                           and not row["future_invalidation_metadata_leaks"] for row in anchors)
                       and reverse_ok and future_bars > 0 and future_producer_ok
                       and future_replay_ok and roundtrip_ok and not birth_leaks
                       and not same_close_links)
        results.append({"control": name, "cutoff_utc": cutoff.isoformat(),
                        "rows": {tf: len(frame) for tf, frame in frames.items()},
                        "producer_counts": producer["counts"], "marketobjects": full["objects"],
                        "objects_with_parent": full["linked_objects"],
                        "states_as_of": dict(Counter(o.state.value for o in projection.values())),
                        "replay_stats": full["stats"],
                        "full_prefix_anchors": anchors,
                        "roundtrip_full_metadata": roundtrip_ok,
                        "reversed_input_order": reverse_ok,
                        "future_real_bars_injected": future_bars,
                        "future_injection_producer": future_producer_ok,
                        "future_injection_replay": future_replay_ok,
                        "future_metadata_leaks_at_birth": birth_leaks,
                        "same_close_parent_links": same_close_links,
                        "result": "PASS_H4_M15_PIT_PILOT" if checks_pass else "FAIL_H4_M15_PIT_PILOT"})
    package = {"scope": "H4_M15_PILOT_ONLY; NO SIX_TF/FUNNEL/EPISODES/GPU/MT5",
               "source": str(source), "manifest": str(manifest), "source_hashes": hashes,
               "results": results, "all_pass": all(x["result"] == "PASS_H4_M15_PIT_PILOT" for x in results)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.source, args.manifest, args.output)
    print(json.dumps({"all_pass": result["all_pass"],
                      "controls": [{"control": r["control"], "result": r["result"],
                                    "objects": r["marketobjects"]} for r in result["results"]]}))
    raise SystemExit(0 if result["all_pass"] else 1)
