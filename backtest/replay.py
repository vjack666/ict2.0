"""Causal replay adapter for the new visual backtest.

The adapter deliberately contains no Swing/BOS/CHOCH or trade rules.  It calls
the canonical engine APIs and serializes the decisions they already emitted.
There is no import from ``ict_backtest`` and no compatibility fallback to an
old backtest runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from engine.bos.structure import StructureConfig, detect_market_structure
from engine.market_features import build_features
from engine.multitf_context import build_multitf_context
from engine.sequence import SequenceConfig, run_sequence
from engine.sequential_outcome import OutcomeConfig, TradeLevels, resolve_outcome

from backtest.schema import VisualBacktest, json_safe


REQUIRED_OHLC = ("time", "open", "high", "low", "close")
DEFAULT_TFS = ("D1", "H4", "H1", "M15")


@dataclass(frozen=True)
class ReplayConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M15"
    timeframes: tuple[str, ...] = DEFAULT_TFS
    execution_tf: str = "M5"
    htf_timeframe: str | None = None
    use_multitf_context: bool = False
    structure: StructureConfig = field(default_factory=StructureConfig)
    sequence: SequenceConfig = field(default_factory=SequenceConfig)
    outcome: OutcomeConfig = field(default_factory=OutcomeConfig)


def _canonical_frame(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    missing = set(REQUIRED_OHLC) - set(frame.columns)
    if missing:
        raise KeyError(f"{name} missing OHLC columns: {sorted(missing)}")
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    if out["time"].isna().any():
        raise ValueError(f"{name} contains invalid timestamps")
    out = out.sort_values("time", kind="stable").drop_duplicates("time").reset_index(drop=True)
    for column in ("open", "high", "low", "close"):
        out[column] = pd.to_numeric(out[column], errors="raise").astype(float)
    return out


def load_raw_frames(
    symbol: str,
    timeframes: tuple[str, ...],
    *,
    data_dir: Path | str,
    start: Any | None = None,
    end: Any | None = None,
) -> dict[str, pd.DataFrame]:
    """Load only raw OHLC data from the current repository data boundary."""

    root = Path(data_dir)
    result: dict[str, pd.DataFrame] = {}
    for timeframe in timeframes:
        nested = root / symbol / f"{symbol}_{timeframe}.parquet"
        flat = root / f"{symbol}_{timeframe}.parquet"
        path = nested if nested.exists() else flat
        if not path.exists():
            raise FileNotFoundError(f"missing raw frame for {symbol}/{timeframe}: {nested}")
        frame = _canonical_frame(pd.read_parquet(path), name=str(path))
        if start is not None:
            start_ts = pd.Timestamp(start)
            start_ts = start_ts.tz_localize("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
            frame = frame[frame["time"] >= start_ts].reset_index(drop=True)
        if end is not None:
            end_ts = pd.Timestamp(end)
            end_ts = end_ts.tz_localize("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
            frame = frame[frame["time"] <= end_ts].reset_index(drop=True)
        if frame.empty:
            raise ValueError(f"empty frame after filtering: {path}")
        result[timeframe] = frame
    return result


def _candle_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        record = {str(column): json_safe(value) for column, value in row.items()}
        record["index"] = int(index)
        records.append(record)
    return records


def _direction(value: int) -> str:
    return "bullish" if int(value) > 0 else "bearish" if int(value) < 0 else "neutral"


def _same_price(value: Any, target: Any) -> bool:
    return pd.notna(value) and pd.notna(target) and bool(np.isclose(float(value), float(target), rtol=0.0, atol=1e-12))


def _find_formation_index(frame: pd.DataFrame, index: int, price: float, kind: str) -> int | None:
    """Find a prior raw extreme without exposing any future bar."""

    column = "high" if kind == "HIGH" else "low"
    candidates = frame.iloc[:index]
    hits = candidates.index[np.isclose(candidates[column].to_numpy(float), float(price), atol=1e-12, rtol=0.0)]
    return int(hits[-1]) if len(hits) else None


def extract_structure_events(
    frame: pd.DataFrame,
    *,
    structure: StructureConfig | None = None,
) -> list[dict[str, Any]]:
    """Serialize events emitted by the canonical BOS/CHoCH engine.

    A swing becomes visible only on the row where the canonical frame first
    exposes its level.  ``formation_index`` is informational and always points
    strictly into the already-closed past; ``index`` and
    ``confirmed_index`` are the publication bar used by the viewer.
    """

    raw = _canonical_frame(frame, name="structure")
    result = detect_market_structure(raw, structure or StructureConfig()).frame
    events: list[dict[str, Any]] = []
    swing_high_id: str | None = None
    swing_low_id: str | None = None
    prior_high: float | None = None
    prior_low: float | None = None
    high_swings: list[tuple[float, str]] = []
    low_swings: list[tuple[float, str]] = []
    all_swings: list[tuple[float, str]] = []
    bos_ids: dict[int, str] = {}
    swing_counter = 0
    bos_counter = 0
    choch_counter = 0

    for index in range(len(result)):
        row = result.iloc[index]
        time = json_safe(raw.iloc[index]["time"])

        if pd.notna(row.get("swing_high")) and not _same_price(row["swing_high"], prior_high):
            swing_counter += 1
            swing_high_id = f"SW_H_{swing_counter:04d}"
            price = float(row["swing_high"])
            events.append({
                "id": swing_high_id,
                "kind": "SWING",
                "swing_type": "HIGH",
                "index": index,
                "confirmed_index": index,
                "formation_index": _find_formation_index(raw, index, price, "HIGH"),
                "time": time,
                "confirmed_time": time,
                "parent_id": None,
                "direction": "neutral",
                "price": price,
                "status": "active",
            })
            prior_high = price
            high_swings.append((price, swing_high_id))
            all_swings.append((price, swing_high_id))

        if pd.notna(row.get("swing_low")) and not _same_price(row["swing_low"], prior_low):
            swing_counter += 1
            swing_low_id = f"SW_L_{swing_counter:04d}"
            price = float(row["swing_low"])
            events.append({
                "id": swing_low_id,
                "kind": "SWING",
                "swing_type": "LOW",
                "index": index,
                "confirmed_index": index,
                "formation_index": _find_formation_index(raw, index, price, "LOW"),
                "time": time,
                "confirmed_time": time,
                "parent_id": None,
                "direction": "neutral",
                "price": price,
                "status": "active",
            })
            prior_low = price
            low_swings.append((price, swing_low_id))
            all_swings.append((price, swing_low_id))

        bos_direction = int(row.get("bos_dir", 0) or 0)
        if bos_direction:
            bos_counter += 1
            level = row.get("bos_level")
            candidates = high_swings if bos_direction > 0 else low_swings
            parent_id = next(
                (event_id for price, event_id in reversed(candidates) if _same_price(price, level)),
                candidates[-1][1] if candidates else None,
            )
            event_id = f"BOS_{'UP' if bos_direction > 0 else 'DOWN'}_{bos_counter:04d}"
            bos_ids[index] = event_id
            events.append({
                "id": event_id,
                "kind": "BOS",
                "index": index,
                "confirmed_index": index,
                "time": time,
                "confirmed_time": time,
                "parent_id": parent_id,
                "direction": _direction(bos_direction),
                "price": json_safe(level),
                # Status/quality are deliberately not exported here: the
                # canonical frame also carries post-event annotations that
                # can change after this bar.  The viewer receives the exact
                # causal decision, not a later retrospective label.
                "status": "emitted",
            })

        choch_direction = int(row.get("choch_dir", 0) or 0)
        if choch_direction:
            choch_counter += 1
            level = row.get("choch_proj_level")
            prior_bos = [event_id for event_index, event_id in bos_ids.items() if event_index < index]
            bos_parent_id = prior_bos[-1] if prior_bos else None
            parent_id = next(
                (event_id for price, event_id in reversed(all_swings) if _same_price(price, level)),
                bos_parent_id,
            )
            event_id = f"CHOCH_{'UP' if choch_direction > 0 else 'DOWN'}_{choch_counter:04d}"
            events.append({
                "id": event_id,
                "kind": "CHOCH",
                "index": index,
                "confirmed_index": index,
                "time": time,
                "confirmed_time": time,
                "parent_id": parent_id,
                "direction": _direction(choch_direction),
                "price": json_safe(level),
                "status": "emitted",
                "bos_parent_id": bos_parent_id,
            })

    # Events are emitted in causal order.  The stable kind order makes a bar
    # carrying multiple canonical events deterministic for the visualizer.
    order = {"SWING": 0, "BOS": 1, "CHOCH": 2}
    events.sort(key=lambda event: (int(event["index"]), order.get(str(event["kind"]), 99)))
    return events


def _last_closed_index(frame: pd.DataFrame, timestamp: Any) -> int:
    values = frame["time"].astype("int64").to_numpy()
    target_ts = pd.Timestamp(timestamp)
    target_ts = target_ts.tz_localize("UTC") if target_ts.tzinfo is None else target_ts.tz_convert("UTC")
    target = target_ts.value
    return int(np.searchsorted(values, target, side="right") - 1)


def _trade_records(
    signals: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    config: ReplayConfig,
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    fallback_frame = frames[config.timeframe]
    for signal_index, signal in enumerate(signals):
        entry_index = int(signal["entry_at"])
        entry_time = signal.get("time")
        direction = int(signal.get("direction", 0))
        event_ids = dict(signal.get("event_ids") or {})
        objects = dict(signal.get("event_objects") or {})
        contract_id = event_ids.get("CONTRACT")
        contract = objects.get(contract_id, {}) if contract_id else {}
        meta = dict(contract.get("meta") or {})
        entry = meta.get("entry", signal.get("entry"))
        sl = meta.get("sl")
        tp = meta.get("tp")
        execution_tf = str(meta.get("exec_tf") or config.execution_tf or config.timeframe)
        execution_frame = frames.get(execution_tf, fallback_frame)
        execution_index = _last_closed_index(execution_frame, entry_time)
        levels = TradeLevels(direction=direction, entry=float(entry), sl=float(sl), tp=float(tp)) if all(
            value is not None and np.isfinite(float(value)) for value in (entry, sl, tp)
        ) else None
        if levels is None:
            resolution = {"outcome": "INVALID", "exit_r": None, "exit_bar": None, "bars_held": None}
        else:
            resolution = resolve_outcome(
                execution_frame["high"].to_numpy(float),
                execution_frame["low"].to_numpy(float),
                execution_index,
                levels,
                config.outcome,
            )
        exit_index = resolution.get("exit_bar")
        exit_time = execution_frame.iloc[int(exit_index)]["time"] if exit_index is not None else None
        outcome = str(resolution["outcome"])
        exit_price = None
        if outcome == "TP" and tp is not None:
            exit_price = float(tp)
        elif outcome == "SL" and sl is not None:
            exit_price = float(sl)
        exported_event_ids = {
            role: (f"{role}_{signal_index + 1:04d}" if raw_id else "")
            for role, raw_id in event_ids.items()
        }
        trades.append({
            "id": f"TRADE_{signal_index + 1:04d}",
            "signal_index": signal_index,
            "signal_id": exported_event_ids.get("RETURN"),
            "chain_id": f"CHAIN_{signal_index + 1:04d}",
            "direction": _direction(direction),
            "entry_index": entry_index,
            "entry_time": entry_time,
            "execution_tf": execution_tf,
            "entry": json_safe(entry),
            "sl": json_safe(sl),
            "tp": json_safe(tp),
            "exit_index": int(exit_index) if exit_index is not None else None,
            "exit_time": json_safe(exit_time),
            "exit_price": exit_price,
            "outcome": outcome,
            "exit_r": json_safe(resolution.get("exit_r")),
            "bars_held": resolution.get("bars_held"),
            "result_confirmed_index": int(exit_index) if exit_index is not None else None,
            "event_ids": exported_event_ids,
        })
    return trades


def _signal_records(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Export signal lineage and PIT features without future outcome fields."""

    stage_by_role = (
        ("LIQUIDITY", "LIQUIDITY_POOL"),
        ("SWEEP", "SWEEP"),
        ("DISPLACE", "DISPLACEMENT"),
        ("BOS", "STRUCTURE"),
        ("POI", "OB"),
        ("REFINEMENT", "FVG"),
        ("RETURN", "RETEST"),
        ("CONTRACT", "CONTRACT"),
    )
    result: list[dict[str, Any]] = []
    for signal_index, signal in enumerate(signals):
        direction = int(signal.get("direction", 0))
        event_ids = dict(signal.get("event_ids") or {})
        stages = [stage for role, stage in stage_by_role if event_ids.get(role)]
        htf_alignment = (
            "ALIGNED" if signal.get("htf_aligned") is True
            else "AGAINST" if signal.get("htf_aligned") is False
            else "NEUTRAL"
        )
        features_at_t = {
            "sequence": stages,
            "sequence_depth": len(stages),
            "context_inputs": {
                "sequence_direction": direction,
                "d1_bias": "UNKNOWN",
                "h4_location": "UNKNOWN",
                "h1_alignment": htf_alignment,
            },
        }
        result.append({
            "signal_index": signal_index,
            "episode_id": f"EP_SIGNAL_{signal_index + 1:06d}",
            "decision_time": signal.get("time"),
            "direction": direction,
            "status": "ACCEPTED",
            "features_at_t": features_at_t,
            "lineage": {str(role): str(value) for role, value in event_ids.items() if value},
            "event_objects": json_safe(signal.get("event_objects") or {}),
            "source": "engine.sequence.run_sequence",
            "can_trade": False,
        })
    return result


def run_visual_replay(
    raw_frames: dict[str, pd.DataFrame],
    config: ReplayConfig | None = None,
) -> VisualBacktest:
    """Run the canonical engine and return a visual-backtest artifact."""

    config = config or ReplayConfig()
    if config.timeframe not in raw_frames:
        raise KeyError(f"main timeframe {config.timeframe!r} not supplied")
    frames = {tf: _canonical_frame(frame, name=tf) for tf, frame in raw_frames.items()}
    featured = {tf: build_features(frame) for tf, frame in frames.items()}
    main = featured[config.timeframe]
    main_raw = frames[config.timeframe]

    closed_index: dict[str, int] = {}
    context_tfs = tuple(featured)

    def context_at(index: int) -> dict[str, Any]:
        timestamp = main.iloc[index]["time"]
        for tf, frame in featured.items():
            closed_index[tf] = _last_closed_index(frame, timestamp)
        return build_multitf_context(
            featured,
            timestamp,
            tfs=context_tfs,
            closed_index=closed_index,
        )

    sequence_config = config.sequence
    htf = config.htf_timeframe or (
        "H1" if config.timeframe != "H1" and "H1" in featured else config.timeframe
    )
    if htf not in featured:
        htf = config.timeframe
    htf_frame = featured[htf]

    def htf_at(index: int) -> dict[str, Any]:
        htf_index = _last_closed_index(htf_frame, main.iloc[index]["time"])
        if htf_index < 0:
            return {"trend": "RANGING", "sweep_up": False, "sweep_down": False}
        row = htf_frame.iloc[htf_index]
        return {
            "trend": str(row.get("trend", "RANGING")),
            "sweep_up": bool(row.get("liquidity_sweep_up", False)),
            "sweep_down": bool(row.get("liquidity_sweep_down", False)),
            "pd_zones": [],
        }

    replay_kwargs: dict[str, Any] = {
        "ltf_tf": config.timeframe,
        "htf": htf,
        "exec_frames": {tf: featured[tf] for tf in ("M5", "M1") if tf in featured},
    }
    est_htf_fn = htf_at
    if config.use_multitf_context:
        replay_kwargs["est_htf_ctx_fn"] = context_at
        est_htf_fn = None
    signals, phase_seen = run_sequence(main, est_htf_fn, sequence_config, **replay_kwargs)
    structure_events = extract_structure_events(main_raw, structure=config.structure)
    trades = _trade_records(signals, featured, config)
    signal_records = _signal_records(signals)
    artifact = VisualBacktest(
        symbol=config.symbol,
        timeframe=config.timeframe,
        candles=_candle_records(main_raw),
        events=structure_events,
        trades=trades,
        signals=signal_records,
        metadata={
            "causal": True,
            "engine": {
                "structure": "engine.bos.structure.detect_market_structure",
                "features": "engine.market_features.build_features",
                "replay": "engine.sequence.run_sequence",
                "outcome": "engine.sequential_outcome.resolve_outcome",
            },
            "timeframes": list(frames),
            "htf_timeframe": htf,
            "multitf_context": config.use_multitf_context,
            "phase_seen": phase_seen,
            "expedientes": sum(1 for signal in signals if signal.get("expediente") is not None),
            "config": json_safe(config.sequence.__dict__),
            "legacy_backtest": False,
            "promotion_authorized": False,
        },
    )
    return artifact
