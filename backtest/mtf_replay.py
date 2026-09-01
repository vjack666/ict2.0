"""Causal multi-timeframe replay consumer.

This module coordinates closed bars and public engine authorities. It contains
no detector or strategy rule and never mutates engine semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import heapq
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional

import numpy as np
import pandas as pd

from backtest.schema import MTFReplayArtifact, json_safe, logical_checksum
from engine.episodes import build_episodes
from engine.market_state import MarketState
from engine.sequential_outcome import OutcomeConfig, TradeLevels, resolve_outcome
from engine.setup_builder import Setup, SetupEligibility, build_setups_at
from engine.market_object import ObjectType


TF_RANK = {"D1": 0, "H4": 1, "H1": 2, "M15": 3, "M5": 4, "M1": 5}
LIFECYCLE_MANAGED_TYPES = {
    ObjectType.FVG, ObjectType.ORDER_BLOCK, ObjectType.BREAKER, ObjectType.BPR,
}


@dataclass(frozen=True)
class ReplayProfile:
    profile_id: str
    htf: str
    itf: str
    exec_tf: str
    refine_tf: str | None = None

    def __post_init__(self) -> None:
        for tf in (self.htf, self.itf, self.exec_tf):
            if tf not in TF_RANK:
                raise ValueError(f"unsupported timeframe: {tf}")
        if self.refine_tf is not None and self.refine_tf not in TF_RANK:
            raise ValueError(f"unsupported refine timeframe: {self.refine_tf}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "htf": self.htf,
            "itf": self.itf,
            "exec_tf": self.exec_tf,
            "refine_tf": self.refine_tf,
        }


INTRADAY_H4_M15 = ReplayProfile("INTRADAY_H4_M15", "H4", "M15", "M15")
INTRADAY_H4_M15_M5_REFINEMENT = ReplayProfile(
    "INTRADAY_H4_M15_M5_REFINEMENT", "H4", "M15", "M5", "M5"
)


@dataclass
class ReplayConfig:
    symbol: str
    profile: ReplayProfile = INTRADAY_H4_M15
    checkpoint_every: int = 250
    chunk_size: int = 1000
    dataset_hash: str = "SYNTHETIC"
    code_commit: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if self.checkpoint_every <= 0 or self.chunk_size <= 0:
            raise ValueError("checkpoint_every and chunk_size must be positive")

    def stable_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "profile": self.profile.to_dict(),
            "checkpoint_every": self.checkpoint_every,
            "dataset_hash": self.dataset_hash,
            "code_commit": self.code_commit,
        }

    @property
    def config_hash(self) -> str:
        encoded = json.dumps(self.stable_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


ContextProvider = Callable[[pd.Timestamp], Any]
SetupProvider = Callable[[MarketState, pd.Timestamp, Any], list[Setup]]
ExecutionPlanProvider = Callable[[Setup, pd.Timestamp], TradeLevels | None]


def _utc(value: Any) -> pd.Timestamp:
    result = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(result):
        raise ValueError(f"invalid close time: {value!r}")
    return result


def canonical_setup_id(setup: Setup) -> str:
    """Stable replay identity derived from canonical component lineage."""

    component_ids = [
        getattr(setup.context_htf, "id", "NONE"),
        getattr(setup.poi, "id", "NONE"),
        getattr(setup.refinement, "id", "NONE"),
        getattr(setup.confirmation, "id", "NONE"),
        getattr(setup.trigger, "id", "NONE"),
    ]
    raw = "|".join([setup.symbol, str(setup.direction), *component_ids])
    return "SETUP-" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def _bar_record(tf: str, index: int, row: Mapping[str, Any]) -> dict[str, Any]:
    close_time = _utc(row.get("close_time", row.get("time")))
    return {
        "index": index,
        "tf": tf,
        "observation_time": close_time.isoformat(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
    }


def canonical_frames(frames: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for tf, frame in frames.items():
        if tf not in TF_RANK:
            raise ValueError(f"unsupported timeframe: {tf}")
        rows: list[dict[str, Any]] = []
        if isinstance(frame, pd.DataFrame):
            iterator = (row for _, row in frame.iterrows())
        else:
            iterator = iter(frame)
        last: pd.Timestamp | None = None
        for index, row in enumerate(iterator):
            record = _bar_record(tf, index, row)
            now = _utc(record["observation_time"])
            if last is not None and now <= last:
                raise ValueError(f"OUT_OF_ORDER_EVENT in {tf}")
            last = now
            rows.append(record)
        if rows:
            out[tf] = rows
    if not out:
        raise ValueError("MISSING_LAYER: no closed bars supplied")
    return out


def iter_close_batches(candles_by_tf: Mapping[str, list[dict[str, Any]]]) -> Iterator[tuple[pd.Timestamp, list[dict[str, Any]]]]:
    """Streaming k-way merge with deterministic HTF-to-LTF close batches."""

    heap: list[tuple[int, int, str, int]] = []
    for tf, rows in candles_by_tf.items():
        if rows:
            heapq.heappush(heap, (_utc(rows[0]["observation_time"]).value, TF_RANK[tf], tf, 0))
    while heap:
        timestamp_ns = heap[0][0]
        batch: list[dict[str, Any]] = []
        while heap and heap[0][0] == timestamp_ns:
            _, _, tf, index = heapq.heappop(heap)
            batch.append(candles_by_tf[tf][index])
            next_index = index + 1
            if next_index < len(candles_by_tf[tf]):
                nxt = candles_by_tf[tf][next_index]
                heapq.heappush(heap, (_utc(nxt["observation_time"]).value, TF_RANK[tf], tf, next_index))
        batch.sort(key=lambda row: (TF_RANK[row["tf"]], row["index"]))
        yield pd.Timestamp(timestamp_ns, tz="UTC"), batch


@dataclass
class ReplayCheckpoint:
    cursor: int
    observation_time: str
    config_hash: str
    dataset_hash: str
    market_state: dict[str, Any]
    seen_setup_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return json_safe(self.__dict__)


class MTFReplayOrchestrator:
    def __init__(
        self,
        config: ReplayConfig,
        market_state: MarketState,
        *,
        context_provider: Optional[ContextProvider] = None,
        setup_provider: Optional[SetupProvider] = None,
        execution_plan_provider: Optional[ExecutionPlanProvider] = None,
        outcome_config: OutcomeConfig | None = None,
    ) -> None:
        self.config = config
        self.market_state = market_state
        self.context_provider = context_provider or (lambda _t: None)
        self.setup_provider = setup_provider or build_setups_at
        self.execution_plan_provider = execution_plan_provider or (lambda _setup, _t: None)
        self.outcome_config = outcome_config or OutcomeConfig()
        self._seen_setups: dict[str, str] = {}
        self._last_setup_record: dict[str, str] = {}
        self._filled_setups: set[str] = set()
        self._pending_plans: dict[str, dict[str, Any]] = {}

    def _apply_bar(self, bar: dict[str, Any]) -> list[dict[str, Any]]:
        tf = bar["tf"]
        engine_bar = {
            **bar,
            "time": bar["observation_time"],
            "__index__": bar["index"],
        }
        transitions: list[dict[str, Any]] = []
        for obj in list(self.market_state.all_objects()):
            # Terminal lifecycle states are immutable. Skipping them avoids
            # replaying and serializing irrelevant dedupe events.
            if obj.is_terminal:
                continue
            # BOS and displacement are immutable published events, not price
            # zones governed by FVG/OB mitigation lifecycle.
            if obj.type not in LIFECYCLE_MANAGED_TYPES:
                continue
            if obj.creation_time is not None and _utc(obj.creation_time) > _utc(bar["observation_time"]):
                continue
            before = obj.state.value
            try:
                if tf == obj.authority_tf:
                    self.market_state.advance_bar(obj.id, engine_bar)
                elif TF_RANK[tf] > TF_RANK.get(obj.authority_tf, -1):
                    self.market_state.observe(obj.id, engine_bar, observed_tf=tf)
                else:
                    continue
            except ValueError as exc:
                transitions.append({"object_id": obj.id, "reason": str(exc), "rejected": True})
                continue
            after = obj.state.value
            if after != before:
                transitions.append({"object_id": obj.id, "from": before, "to": after, "rejected": False})
        return transitions

    def run(
        self,
        frames: Mapping[str, Any],
        *,
        stop_after_batches: int | None = None,
        resume: ReplayCheckpoint | None = None,
    ) -> dict[str, Any]:
        candles_by_tf = canonical_frames(frames)
        required_layers = {self.config.profile.htf, self.config.profile.itf, self.config.profile.exec_tf}
        if not required_layers.issubset(candles_by_tf):
            raise ValueError(f"MISSING_LAYER: {sorted(required_layers - set(candles_by_tf))}")
        start_cursor = 0
        checkpoints: list[dict[str, Any]] = []
        if resume is not None:
            if resume.config_hash != self.config.config_hash or resume.dataset_hash != self.config.dataset_hash:
                raise ValueError("CONFIG_MISMATCH: checkpoint hashes do not match")
            self.market_state = MarketState.from_dict(resume.market_state)
            self._seen_setups = {setup_id: "ELIGIBLE" for setup_id in resume.seen_setup_ids}
            start_cursor = resume.cursor + 1

        timeline: list[dict[str, Any]] = []
        deltas: list[dict[str, Any]] = []
        setup_rows: list[dict[str, Any]] = []
        episode_rows: list[dict[str, Any]] = []
        invalidations: list[dict[str, Any]] = []
        rejections: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        exec_rows = candles_by_tf[self.config.profile.exec_tf]

        for cursor, (now, batch) in enumerate(iter_close_batches(candles_by_tf)):
            if cursor < start_cursor:
                continue
            if stop_after_batches is not None and len(timeline) >= stop_after_batches:
                break
            transition_rows: list[dict[str, Any]] = []
            for bar in batch:
                transition_rows.extend(self._apply_bar(bar))
            ctx = self.context_provider(now)
            setups = self.setup_provider(self.market_state, now, ctx)
            current: dict[str, Setup] = {canonical_setup_id(setup): setup for setup in setups}
            for setup_id, previous in list(self._seen_setups.items()):
                setup = current.get(setup_id)
                current_state = setup.eligibility.value if setup is not None else "CANCELLED_BEFORE_ENTRY"
                if previous == SetupEligibility.ELIGIBLE.value and current_state != previous:
                    if setup_id in self._filled_setups:
                        reason = "AUTHORITY_INVALIDATION_AFTER_ENTRY"
                    else:
                        reason = "SUPERSEDED_BEFORE_ENTRY" if current_state == SetupEligibility.SUPERSEDED.value else "CANCELLED_BEFORE_ENTRY"
                        self._pending_plans.pop(setup_id, None)
                    invalidations.append({
                        "id": f"INV-{setup_id}-{cursor}",
                        "observation_time": now.isoformat(),
                        "authority_tf": self.config.profile.itf,
                        "setup_id": setup_id,
                        "reason": reason,
                        "parent_ids": [self._last_setup_record[setup_id]] if setup_id in self._last_setup_record else [],
                    })
            for setup_id, setup in current.items():
                self._seen_setups[setup_id] = setup.eligibility.value
                record_id = f"SETUPREC-{setup_id}-{cursor}"
                previous_record = self._last_setup_record.get(setup_id)
                row = setup.to_dict()
                row.update({
                    "id": record_id,
                    "setup_id": setup_id,
                    "observation_time": now.isoformat(),
                    "authority_tf": getattr(setup.poi, "authority_tf", self.config.profile.itf),
                    "parent_ids": [previous_record] if previous_record else [],
                })
                setup_rows.append(row)
                self._last_setup_record[setup_id] = record_id
                if setup.eligibility is SetupEligibility.ELIGIBLE and setup_id not in self._pending_plans and setup_id not in self._filled_setups:
                    levels = self.execution_plan_provider(setup, now)
                    if levels is not None:
                        if not levels.is_valid():
                            rejections.append({
                                "id": f"REJ-LEVELS-{cursor}-{len(rejections)}",
                                "observation_time": now.isoformat(),
                                "authority_tf": self.config.profile.exec_tf,
                                "reason": "AMBIGUOUS_FILL",
                                "parent_ids": [record_id],
                            })
                        else:
                            self._pending_plans[setup_id] = {
                                "levels": levels,
                                "created_at": now,
                                "setup_record_id": record_id,
                            }

            funnel = build_episodes(self.market_state, [now], ctx, config={"profile_id": self.config.profile.profile_id})
            for episode in funnel["episodes"]:
                episode_id = str(episode["episode_id"])
                episode_rows.append({
                    **episode,
                    "id": f"EP-{episode_id}-{cursor}",
                    "observation_time": now.isoformat(),
                    "authority_tf": episode.get("component_tfs", {}).get("poi", self.config.profile.itf),
                    "parent_ids": [],
                })
            for rejection in funnel["rejections"]:
                rejections.append({
                    **rejection,
                    "id": f"REJ-{cursor}-{len(rejections)}",
                    "observation_time": now.isoformat(),
                    "authority_tf": self.config.profile.itf,
                    "parent_ids": [],
                })

            # EXECUTION phase: only plans from a strictly earlier close may fill.
            exec_bar = next((row for row in batch if row["tf"] == self.config.profile.exec_tf), None)
            if exec_bar is not None:
                for setup_id, pending in list(self._pending_plans.items()):
                    if pending["created_at"] >= now:
                        continue
                    levels: TradeLevels = pending["levels"]
                    if exec_bar["low"] <= levels.entry <= exec_bar["high"]:
                        entry_index = int(exec_bar["index"])
                        high = np.array([row["high"] for row in exec_rows], dtype=float)
                        low = np.array([row["low"] for row in exec_rows], dtype=float)
                        outcome = resolve_outcome(high, low, entry_index, levels, self.outcome_config)
                        exit_index = outcome["exit_bar"]
                        result_time = exec_rows[int(exit_index)]["observation_time"] if exit_index is not None else None
                        trades.append({
                            "id": f"TRADE-{setup_id}",
                            "observation_time": now.isoformat(),
                            "confirmation_time": now.isoformat(),
                            "authority_tf": self.config.profile.exec_tf,
                            "setup_id": setup_id,
                            "entry_index": entry_index,
                            "entry": levels.entry,
                            "sl": levels.sl,
                            "tp": levels.tp,
                            "direction": levels.direction,
                            **outcome,
                            "result_observation_time": result_time,
                            "parent_ids": [pending["setup_record_id"]],
                        })
                        self._filled_setups.add(setup_id)
                        del self._pending_plans[setup_id]
            delta_id = f"DELTA-{cursor}"
            deltas.append({
                "id": delta_id,
                "observation_time": now.isoformat(),
                "authority_tf": batch[0]["tf"],
                "transitions": transition_rows,
                "parent_ids": [],
            })
            timeline.append({
                "id": f"TICK-{cursor}",
                "index": cursor,
                "observation_time": now.isoformat(),
                "authority_tf": batch[0]["tf"],
                "closed_tfs": [row["tf"] for row in batch],
                "phases": ["CLOSE_BATCH", "APPLY_AUTHORITY", "SNAPSHOT", "DECISION", "EXECUTION", "EMIT"],
                "parent_ids": [delta_id],
            })
            if cursor % self.config.checkpoint_every == 0:
                checkpoints.append(ReplayCheckpoint(
                    cursor=cursor,
                    observation_time=now.isoformat(),
                    config_hash=self.config.config_hash,
                    dataset_hash=self.config.dataset_hash,
                    market_state=self.market_state.to_dict(),
                    seen_setup_ids=sorted(self._seen_setups),
                ).to_dict())

        artifact = MTFReplayArtifact(
            run_metadata={
                "symbol": self.config.symbol,
                "profile_id": self.config.profile.profile_id,
                "dataset_hash": self.config.dataset_hash,
                "config_hash": self.config.config_hash,
                "code_commit": self.config.code_commit,
                "chunk_size": self.config.chunk_size,
            },
            profiles=[self.config.profile.to_dict()],
            candles_by_tf=candles_by_tf,
            timeline=timeline,
            market_state_checkpoints=checkpoints,
            state_deltas=deltas,
            setups=setup_rows,
            episodes=episode_rows,
            invalidations=invalidations,
            trades=trades,
            rejections=rejections,
        ).to_dict()
        return artifact


def make_chunks(payload: dict[str, Any], chunk_size: int) -> dict[str, Any]:
    """Create deterministic logical chunks without changing artifact checksum."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    chunks = []
    timeline = payload["timeline"]
    for start in range(0, len(timeline), chunk_size):
        rows = timeline[start : start + chunk_size]
        chunks.append({
            "id": f"CHUNK-{start // chunk_size:06d}",
            "start": start,
            "end": start + len(rows) - 1,
            "start_time": rows[0]["observation_time"],
            "end_time": rows[-1]["observation_time"],
            "path": f"chunks/CHUNK-{start // chunk_size:06d}.json",
            "checksum": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        })
    return {"artifact_checksum": logical_checksum(payload), "chunks": chunks}


def write_chunks(payload: dict[str, Any], output_dir: Path, chunk_size: int) -> dict[str, Any]:
    """Materialize lazy-load chunks and an atomic manifest.

    Chunk boundaries only affect storage. The manifest always carries the
    canonical artifact checksum, so changing chunk_size cannot change meaning.
    """

    manifest = make_chunks(payload, chunk_size)
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    temporal_collections = (
        "timeline", "state_deltas", "setups", "episodes", "invalidations", "trades", "rejections"
    )
    for chunk in manifest["chunks"]:
        start_time = _utc(chunk["start_time"])
        end_time = _utc(chunk["end_time"])

        def inside(row: dict[str, Any]) -> bool:
            timestamp = _utc(row["observation_time"])
            return start_time <= timestamp <= end_time

        content = {
            "schema_version": "2.0",
            "artifact_kind": "MTF_REPLAY_CHUNK",
            "artifact_checksum": manifest["artifact_checksum"],
            "chunk": dict(chunk),
            "candles_by_tf": {
                tf: [row for row in rows if inside(row)]
                for tf, rows in payload["candles_by_tf"].items()
            },
        }
        for collection in temporal_collections:
            content[collection] = [row for row in payload[collection] if inside(row)]
        target = output_dir / chunk["path"]
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(json_safe(content), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(target)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_manifest.replace(manifest_path)
    return manifest


__all__ = [
    "INTRADAY_H4_M15",
    "INTRADAY_H4_M15_M5_REFINEMENT",
    "MTFReplayOrchestrator",
    "ReplayCheckpoint",
    "ReplayConfig",
    "ReplayProfile",
    "canonical_frames",
    "canonical_setup_id",
    "iter_close_batches",
    "make_chunks",
    "write_chunks",
]
