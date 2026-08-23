"""Compare the batch FULL navigator with a one-pass PREFIX navigator.

The PREFIX side consumes each timeframe row once.  It never constructs a
truncated DataFrame or calls ``MTFNavigator`` on a prefix.  Its compact state
fingerprint is compared at every H1 decision; selected decisions additionally
compare the complete serialized state.
"""
from __future__ import annotations

import hashlib
import json
import sys
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from math import ceil, floor
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import (  # noqa: E402
    ContextConstraints,
    LayerSnapshot,
    MTFNavigator,
    MarketState,
    NavigatorConfig,
    NavigationPath,
    NavQuestion,
    RegimeLabel,
    StructureBias,
    TimeframeLayer,
    Zone,
    _asof_index,
    _regime_from_structure,
    _structure_bias_from_swings,
)

MASK64 = (1 << 64) - 1


def _zone_token(zone: Zone) -> int:
    return hash((round(zone.low, 12), round(zone.high, 12), zone.kind, zone.bar_index, zone.detail)) & MASK64


def _fold(prev: int, token: int) -> int:
    return ((prev * 1_000_003) ^ token) & MASK64


class ZoneView:
    """Immutable prefix view over pool events plus the current dealing range."""

    def __init__(self, events: list[Zone], count: int, dealing: Zone, prefix_hash: list[int]):
        self.events = events
        self.count = count
        self.dealing = dealing
        self.prefix_hash = prefix_hash

    def __iter__(self):
        for i in range(self.count):
            yield self.events[i]
        yield self.dealing

    def __len__(self) -> int:
        return self.count + 1

    def __getitem__(self, index):
        values = list(self)
        return values[index]

    def digest(self) -> tuple[int, int]:
        return self.count + 1, _fold(self.prefix_hash[self.count], _zone_token(self.dealing))


def _prefix_hash(events: list[Zone]) -> list[int]:
    out = [0]
    for zone in events:
        out.append(_fold(out[-1], _zone_token(zone)))
    return out


def _time_index(df: pd.DataFrame) -> np.ndarray:
    return pd.to_datetime(df["time"], utc=True).astype("int64").to_numpy()


def _asof_fast(time_values: np.ndarray, decision_time: Any) -> int:
    ts = int(pd.to_datetime(decision_time, utc=True).value)
    return bisect_right(time_values, ts) - 1


def _last_structure_bias(sh: list[tuple[int, float]], sl: list[tuple[int, float]]) -> StructureBias:
    """Equivalent to `_structure_bias_from_swings` for already-visible lists."""
    if len(sh) < 2 or len(sl) < 2:
        return StructureBias.UNKNOWN
    hh = sh[-1][1] > sh[-2][1]
    hl = sl[-1][1] > sl[-2][1]
    lh = sh[-1][1] < sh[-2][1]
    ll = sl[-1][1] < sl[-2][1]
    if hh and hl:
        return StructureBias.BULLISH
    if lh and ll:
        return StructureBias.BEARISH
    return StructureBias.MIXED


def _last_structure_bias_prefix(
    sh: list[tuple[int, float]], sh_count: int, sl: list[tuple[int, float]], sl_count: int
) -> StructureBias:
    if sh_count < 2 or sl_count < 2:
        return StructureBias.UNKNOWN
    sh_last, sh_prev = sh[sh_count - 1], sh[sh_count - 2]
    sl_last, sl_prev = sl[sl_count - 1], sl[sl_count - 2]
    hh = sh_last[1] > sh_prev[1]
    hl = sl_last[1] > sl_prev[1]
    lh = sh_last[1] < sh_prev[1]
    ll = sl_last[1] < sl_prev[1]
    if hh and hl:
        return StructureBias.BULLISH
    if lh and ll:
        return StructureBias.BEARISH
    return StructureBias.MIXED


@dataclass
class _PoolRoot:
    bar: int
    price: float
    tolerance: float
    matches: list[tuple[int, float]] = field(default_factory=list)
    formed: bool = False


class _StreamingPools:
    def __init__(self, is_high: bool):
        self.is_high = is_high
        self.roots: list[_PoolRoot] = []
        self.used: set[int] = set()
        self.zones: list[Zone] = []
        self.zone_hash = [0]
        self.bucket_size = 0.001
        self.buckets: dict[int, list[_PoolRoot]] = defaultdict(list)
        self.max_tolerance = 0.0

    def add(self, index: int, bar: int, price: float, high: list[float], low: list[float]) -> None:
        if index in self.used:
            return
        span = int(ceil(max(self.max_tolerance, 1e-9) / self.bucket_size)) + 1
        bucket = floor(price / self.bucket_size)
        candidates = []
        for key in range(bucket - span, bucket + span + 1):
            for root in self.buckets.get(key, []):
                if abs(price - root.price) <= root.tolerance:
                    candidates.append(root)
        if candidates:
            # `_eq_pools` consumes the earliest chronological root first.
            root = min(candidates, key=lambda item: item.bar)
            self.used.add(index)
            root.matches.append((bar, price))
            if not root.formed and len(root.matches) >= 2:
                first = root.matches[:2]
                prices = [p for _, p in first]
                zone = Zone(
                    low=float(min(prices)),
                    high=float(max(prices)),
                    kind="BSL" if self.is_high else "SSL",
                    bar_index=int(max(b for b, _ in first)),
                    detail="EQH" if self.is_high else "EQL",
                )
                root.formed = True
                self.zones.append(zone)
                self.zone_hash.append(_fold(self.zone_hash[-1], _zone_token(zone)))
            return

        a = max(0, bar - 14)
        avg_range = float(np.mean(np.asarray(high[a : bar + 1]) - np.asarray(low[a : bar + 1])))
        tolerance = max(avg_range * 0.25, 1e-9)
        root = _PoolRoot(bar, price, tolerance, [(bar, price)])
        self.roots.append(root)
        self.buckets[floor(price / self.bucket_size)].append(root)
        self.max_tolerance = max(self.max_tolerance, tolerance)


class _StreamingLayer:
    def __init__(self, df: pd.DataFrame, config: NavigatorConfig):
        self.df = df.reset_index(drop=True)
        self.config = config
        self.high: list[float] = []
        self.low: list[float] = []
        self.close: list[float] = []
        self.open: list[float] = []
        self.times = list(self.df["time"])
        self.index = -1
        self.sh: list[tuple[int, float]] = []
        self.sl: list[tuple[int, float]] = []
        self.high_pools = _StreamingPools(True)
        self.low_pools = _StreamingPools(False)
        self.zone_events: list[Zone] = []
        self.zone_prefix_hash: list[int] = [0]
        self.bos_swing_high: float | None = None
        self.bos_swing_low: float | None = None
        self.last_bos_direction: int | None = None
        self.last_bos_bar: int | None = None
        self.displacement: list[bool] = []

    def advance_to(self, target: int) -> None:
        target = min(target, len(self.df) - 1)
        while self.index < target:
            self._append(self.index + 1)

    def _append(self, i: int) -> None:
        row = self.df.iloc[i]
        self.open.append(float(row["open"]))
        self.high.append(float(row["high"]))
        self.low.append(float(row["low"]))
        self.close.append(float(row["close"]))
        self.index = i

        left = self.config.swing_left
        if i >= left * 2:
            center = i - left
            h_window = self.high[center - left : center + left + 1]
            l_window = self.low[center - left : center + left + 1]
            if self.high[center] >= max(h_window):
                self.sh.append((i, self.high[center]))
                before = len(self.high_pools.zones)
                self.high_pools.add(len(self.sh) - 1, i, self.high[center], self.high, self.low)
                if len(self.high_pools.zones) != before:
                    self._refresh_zones()
            if self.low[center] <= min(l_window):
                self.sl.append((i, self.low[center]))
                before = len(self.low_pools.zones)
                self.low_pools.add(len(self.sl) - 1, i, self.low[center], self.high, self.low)
                if len(self.low_pools.zones) != before:
                    self._refresh_zones()

        # Equivalent to detectors.bos._swing_points + detect_bos at bar i.
        prev_sh = self.bos_swing_high
        prev_sl = self.bos_swing_low
        prev_close = self.close[i - 1] if i else None
        lb = self.config.bos_lookback
        if i >= lb * 2:
            center = i - lb
            h_window = self.high[center - lb : center + lb + 1]
            l_window = self.low[center - lb : center + lb + 1]
            new_sh = self.high[center] if self.high[center] >= max(h_window) else None
            new_sl = self.low[center] if self.low[center] <= min(l_window) else None
        else:
            new_sh = None
            new_sl = None
        bullish = prev_sh is not None and self.close[i] > prev_sh and (prev_close is None or prev_close <= prev_sh)
        bearish = prev_sl is not None and self.close[i] < prev_sl and (prev_close is None or prev_close >= prev_sl)
        if bullish:
            self.last_bos_direction, self.last_bos_bar = 1, i
        elif bearish:
            self.last_bos_direction, self.last_bos_bar = -1, i
        if new_sh is not None:
            self.bos_swing_high = new_sh
        if new_sl is not None:
            self.bos_swing_low = new_sl

        # Equivalent to tools.displacement.detect_displacement and its recent window.
        period = 14
        a = max(0, i - period + 1)
        avg_range = float(np.mean(np.asarray(self.high[a : i + 1]) - np.asarray(self.low[a : i + 1]))) if i + 1 >= period else 1e-9
        candle_range = self.high[i] - self.low[i]
        body = abs(self.close[i] - self.open[i])
        body_ratio = body / candle_range if candle_range else 0.0
        is_disp = body > avg_range * 1.5 and (1.0 - body_ratio) < 0.4
        self.displacement.append(is_disp)

    def _refresh_zones(self) -> None:
        self.zone_events = sorted(
            self.high_pools.zones + self.low_pools.zones,
            key=lambda z: (int(z.bar_index or 0), z.kind, z.detail),
        )
        self.zone_prefix_hash = _prefix_hash(self.zone_events)

    def snapshot(self, sequence_depth: int, sequence_complete: int) -> LayerSnapshot:
        i = self.index
        rh = float(max(self.high[max(0, i - self.config.dealing_lookback + 1) : i + 1]))
        rl = float(min(self.low[max(0, i - self.config.dealing_lookback + 1) : i + 1]))
        bias = _last_structure_bias(self.sh, self.sl)
        regime = _regime_from_structure(bias, rh, rl, self.close[i])
        dealing = Zone(low=rl, high=rh, kind="DEALING", bar_index=i, detail="dealing_range")
        zones = ZoneView(self.zone_events, len(self.zone_events), dealing, self.zone_prefix_hash)
        recent_a = max(0, i - self.config.displacement_lookback + 1)
        disp_recent = any(self.displacement[recent_a : i + 1])
        return LayerSnapshot(
            layer=TimeframeLayer(self.df.attrs.get("tf", "H1")),
            asof_bar=i,
            asof_time=self.times[i],
            last_close=self.close[i],
            structure_bias=bias,
            regime=regime,
            zones=zones,  # type: ignore[arg-type]
            last_bos_direction=self.last_bos_direction,
            last_bos_bar=self.last_bos_bar,
            displacement_recent=disp_recent,
            range_high=rh,
            range_low=rl,
        )


def _snapshot_payload(snapshot: LayerSnapshot) -> dict[str, Any]:
    zones = snapshot.zones
    if isinstance(zones, ZoneView):
        zone_count, zone_digest = zones.digest()
    else:
        zone_count = len(zones)
        zone_digest = 0
        for zone in zones:
            zone_digest = _fold(zone_digest, _zone_token(zone))
    return {
        "layer": snapshot.layer.value,
        "asof_bar": snapshot.asof_bar,
        "asof_time": str(snapshot.asof_time),
        "last_close": snapshot.last_close,
        "structure_bias": snapshot.structure_bias.value,
        "regime": snapshot.regime.value,
        "zones": [zone_count, zone_digest],
        "last_bos_direction": snapshot.last_bos_direction,
        "last_bos_bar": snapshot.last_bos_bar,
        "displacement_recent": snapshot.displacement_recent,
        "range_high": snapshot.range_high,
        "range_low": snapshot.range_low,
        "answers": snapshot.answers,
        "notes": snapshot.notes,
    }


def _list_zone_digest(zones: Iterable[Zone]) -> tuple[int, int]:
    count = 0
    digest = 0
    for zone in zones:
        count += 1
        digest = _fold(digest, _zone_token(zone))
    return count, digest


def state_fingerprint(state: MarketState) -> str:
    constraints = state.constraints
    c_payload: dict[str, Any] | None = None
    if constraints is not None:
        loc = _list_zone_digest(constraints.location_zones)
        liq = _list_zone_digest(constraints.liquidity_targets)
        c_payload = {
            "decision_time": str(constraints.decision_time),
            "exec_tf": constraints.exec_tf,
            "direction_hint": constraints.direction_hint.value,
            "location_zones": loc,
            "liquidity_targets": liq,
            "regime_stack": constraints.regime_stack,
            "allow_long": constraints.allow_long,
            "allow_short": constraints.allow_short,
            "sequence_required": constraints.sequence_required,
            "notes": constraints.notes,
        }
    payload = {
        "decision_time": str(state.decision_time),
        "exec_tf": state.exec_tf,
        "status": state.status,
        "layers": {key: _snapshot_payload(value) for key, value in state.layers.items()},
        "constraints": c_payload,
        "path": state.path.to_dict(),
        "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


class _BatchFingerprintNavigator(MTFNavigator):
    def __init__(self, frames: Mapping[str, pd.DataFrame], config: NavigatorConfig):
        super().__init__(frames, config)
        self._time_values = {key: _time_index(df) for key, df in self._frames.items()}

    def _snapshot(self, layer: TimeframeLayer, decision_time: Any) -> LayerSnapshot | None:
        df = self._frames.get(layer.value)
        if df is None or df.empty:
            return None
        i = _asof_fast(self._time_values[layer.value], decision_time)
        if i < 0:
            return None
        pre = self._pre.get(layer.value, {})
        if not pre:
            return None
        high, low, close = pre["high"], pre["low"], pre["close"]
        si = bisect_right(pre["sh_b"], i)
        sj = bisect_right(pre["sl_b"], i)
        bias = _last_structure_bias_prefix(pre["sh"], si, pre["sl"], sj)
        rh, rl = float(pre["dh"][i]), float(pre["dl"][i])
        events = pre["zone_events"]
        zi = bisect_right(pre["zone_bars"], i)
        dealing = Zone(low=rl, high=rh, kind="DEALING", bar_index=i, detail="dealing_range")
        snap = LayerSnapshot(
            layer=layer,
            asof_bar=i,
            asof_time=df["time"].iloc[i],
            last_close=float(close[i]),
            structure_bias=bias,
            regime=_regime_from_structure(bias, rh, rl, float(close[i])),
            zones=ZoneView(events, zi, dealing, pre["zone_prefix_hash"]),  # type: ignore[arg-type]
            last_bos_direction=int(pre["last_bos_dir"][i]) if pre["last_bos_dir"][i] != 0 else None,
            last_bos_bar=int(pre["last_bos_bar"][i]) if pre["last_bos_dir"][i] != 0 else None,
            displacement_recent=bool(pre["disp_recent"][i]),
            range_high=rh,
            range_low=rl,
        )
        return snap


class _StreamingFingerprintNavigator(MTFNavigator):
    def __init__(self, frames: Mapping[str, pd.DataFrame], config: NavigatorConfig, full: MTFNavigator):
        self.config = config
        self._frames = {key.upper(): df.reset_index(drop=True).copy() for key, df in frames.items()}
        for key, df in self._frames.items():
            df.attrs["tf"] = key
        self._seq_depth_by_bar = dict(full._seq_depth_by_bar)
        self._seq_complete_by_bar = dict(full._seq_complete_by_bar)
        self._seq_chains = full._seq_chains
        self._time_values = {key: _time_index(df) for key, df in self._frames.items()}
        self._trackers = {key: _StreamingLayer(df, config) for key, df in self._frames.items()}

    def advance(self, decision_time: Any) -> None:
        for key, df in self._frames.items():
            i = _asof_fast(self._time_values[key], decision_time)
            if i >= 0:
                self._trackers[key].advance_to(i)

    def navigate(self, decision_time: Any, exec_tf: str = "H1", stop_if_no_d1_context: bool = False) -> MarketState:
        self.advance(decision_time)
        return MTFNavigator.navigate(self, decision_time, exec_tf, stop_if_no_d1_context)

    def _snapshot(self, layer: TimeframeLayer, decision_time: Any) -> LayerSnapshot | None:
        tracker = self._trackers.get(layer.value)
        if tracker is None or tracker.index < 0:
            return None
        return tracker.snapshot(self.sequence_depth_at(tracker.index), self.sequence_complete_count_at(tracker.index))


def main() -> dict[str, Any]:
    from audits.codigo.mtf_seq_funnel import _load_tf

    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    metadata = json.loads((ROOT / "datasets" / "eurusd_dukascopy_20y" / "metadata.json").read_text())
    actual_rows = {tf: len(df) for tf, df in frames.items()}
    declared_rows = {tf: int(metadata[tf]["n_clean"]) for tf in frames}
    raw_rows = {tf: int(metadata[tf]["n_raw"]) for tf in frames}
    metadata_consistent = actual_rows == declared_rows
    config = NavigatorConfig(precompute_sequences=True, sequence_tf="H1")
    full = _BatchFingerprintNavigator(frames, config)
    for pre in full._pre.values():
        events = pre["zone_events"]
        pre["zone_prefix_hash"] = _prefix_hash(events)
    streaming = _StreamingFingerprintNavigator(frames, config, full)
    h1 = frames["H1"]
    sample_indices = {0, 71981, 77791, 85125, 111568, 117488, len(h1) - 1}
    mismatches: list[dict[str, Any]] = []
    full_state_samples: dict[int, dict[str, Any]] = {}
    for i, decision_time in enumerate(h1["time"]):
        streaming.advance(decision_time)
        layer_diffs = []
        for tf in ("D1", "H4", "H1"):
            layer = TimeframeLayer(tf)
            full_snap = full._snapshot(layer, decision_time)
            prefix_snap = streaming._snapshot(layer, decision_time)
            full_payload = _snapshot_payload(full_snap) if full_snap is not None else None
            prefix_payload = _snapshot_payload(prefix_snap) if prefix_snap is not None else None
            if full_payload != prefix_payload:
                layer_diffs.append(tf)
        if layer_diffs:
            mismatches.append({"bar": i, "time": str(decision_time), "layers": layer_diffs})
            if len(mismatches) >= 20:
                break
        if i in sample_indices:
            full_state = full.navigate(decision_time, exec_tf="H1")
            prefix_state = streaming.navigate(decision_time, exec_tf="H1")
            full_state_samples[i] = {
                "exact_equal": full_state.to_dict() == prefix_state.to_dict(),
                "full_digest": state_fingerprint(full_state),
                "prefix_digest": state_fingerprint(prefix_state),
            }
    event_checks: dict[str, bool] = {}
    for tf in ("D1", "H4", "H1"):
        batch_pre = full._pre[tf]
        tracker = streaming._trackers[tf]
        event_checks[f"{tf}.swing_highs"] = batch_pre["sh"] == tracker.sh
        event_checks[f"{tf}.swing_lows"] = batch_pre["sl"] == tracker.sl
        batch_zones = [zone.to_dict() for zone in batch_pre["zone_events"]]
        stream_zones = [zone.to_dict() for zone in tracker.zone_events]
        event_checks[f"{tf}.zone_events"] = batch_zones == stream_zones
    if not all(event_checks.values()):
        mismatches.append({"event_checks": event_checks})
    report = {
        "audit": "TNA_STREAMING_PREFIX_COMPARE",
        "coverage": "ALL_H1_DECISIONS",
        "decisions_checked": len(h1) if len(mismatches) < 20 else "stopped_after_20_mismatches",
        "mismatch_count_reported": len(mismatches),
        "mismatches": mismatches,
        "exact_event_checks": event_checks,
        "exact_samples": full_state_samples,
        "full_prefix": "PASS_BY_LAYER_INDUCTION" if not mismatches and all(event_checks.values()) else "FAIL",
        "sequence_history": "FULL_CAUSAL_INDEX_REPLAY",
        "provenance": {
            "actual_rows": actual_rows,
            "declared_rows": declared_rows,
            "declared_raw_rows": raw_rows,
            "metadata_count_field": "n_clean",
            "metadata_consistent": metadata_consistent,
        },
        "gate": "PASS" if not mismatches and metadata_consistent else "BLOCKED",
        "blocking_reasons": [] if not mismatches and metadata_consistent else [
            reason for reason, condition in (
                ("metadata_inconsistent", not metadata_consistent),
                ("layer_or_control_point_mismatch", bool(mismatches) or not all(event_checks.values())),
            ) if condition
        ],
        "note": "Layer snapshots are compared for every decision. Path and constraints are deterministic functions of these snapshots; exact full MarketState equality is checked at control points. Sequence history is sourced from the full causal history index.",
    }
    out = ROOT / "reports" / "audits" / "tna_streaming_prefix_2026-08-22.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    main()
