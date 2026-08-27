"""Causal replay consumer for the canonical ICT and Wyckoff engines.

The module owns data availability, warmup, visible-index projection and
serialization.  It contains no strategy, phase, event, entry or outcome rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import hashlib
import platform
from pathlib import Path
import re
import subprocess
from typing import Any

import numpy as np
import pandas as pd

from backtest.schema import REQUIRED_POLICY, VisualBacktest, json_safe, stable_sha256
from backtest.wyckoff_timeline import build_wyckoff_timeline
from backtest.market_state import build_market_state
from backtest.setup_builder import build_setup_state
from engine.bos.structure import StructureConfig, detect_market_structure
from engine.market_features import build_features
from engine.multitf_context import build_multitf_context
from engine.sequence import SequenceConfig, run_sequence_traced
from engine.sequential_outcome import OutcomeConfig, TradeLevels, resolve_outcome
from engine.ahf import AdaptiveHierarchicalFunnel, AHFConfig


REQUIRED_OHLC = ("time", "open", "high", "low", "close")
DEFAULT_TFS = ("D1", "H4", "H1", "M15", "M5", "M1")
TIMEFRAME_MINUTES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


@dataclass(frozen=True)
class ReplayConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M15"
    timeframes: tuple[str, ...] = DEFAULT_TFS
    execution_tf: str = "M5"
    htf_timeframe: str | None = None
    authority_tf: str = "H1"
    wyckoff_layers: tuple[str, ...] = ("D1", "H4", "H1", "M15")
    timestamp_semantics: str = "open"
    timezone: str = "UTC"
    warmup_bars: int = 200
    visible_start: str | None = None
    visible_end: str | None = None
    wyckoff_enabled: bool = True
    use_multitf_context: bool = False
    git_commit: str = "UNKNOWN"
    git_branch: str = "UNKNOWN"
    generator_worktree_clean_before_run: bool = False
    python_version: str = field(default_factory=platform.python_version)
    node_version: str = "NOT_APPLICABLE"
    structure: StructureConfig = field(default_factory=StructureConfig)
    sequence: SequenceConfig = field(default_factory=SequenceConfig)
    outcome: OutcomeConfig = field(default_factory=OutcomeConfig)


def _utc(value: Any, *, name: str) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        raise ValueError(f"invalid UTC timestamp for {name}: {value!r}")
    return timestamp


def timeframe_duration(timeframe: str) -> pd.Timedelta:
    tf = timeframe.upper()
    if tf not in TIMEFRAME_MINUTES:
        raise ValueError(f"unsupported timeframe duration: {timeframe!r}")
    return pd.Timedelta(minutes=TIMEFRAME_MINUTES[tf])


def _canonical_frame(
    frame: pd.DataFrame,
    *,
    name: str,
    timeframe: str,
    timestamp_semantics: str,
) -> pd.DataFrame:
    """Normalize source timestamps to closed-bar availability timestamps."""

    missing = set(REQUIRED_OHLC) - set(frame.columns)
    if missing:
        raise KeyError(f"{name} missing OHLC columns: {sorted(missing)}")
    semantics = timestamp_semantics.lower()
    if semantics not in {"open", "close"}:
        raise ValueError("timestamp_semantics must be explicitly 'open' or 'close'")

    attrs = dict(frame.attrs)
    if attrs.get("normalized_close_time") is True:
        out = frame.copy()
        out.attrs = attrs
        return out

    out = frame.copy()
    source_time = pd.to_datetime(out["time"], utc=True, errors="coerce")
    if source_time.isna().any():
        raise ValueError(f"{name} contains invalid timestamps")
    out["source_time"] = source_time
    out["source_index"] = np.arange(len(out), dtype="int64")
    out = out.sort_values("source_time", kind="stable").drop_duplicates("source_time").reset_index(drop=True)
    duration = timeframe_duration(timeframe)
    if semantics == "open":
        out["bar_open_time"] = out["source_time"]
        out["bar_close_time"] = out["source_time"] + duration
    else:
        out["bar_close_time"] = out["source_time"]
        out["bar_open_time"] = out["source_time"] - duration
    out["time"] = out["bar_close_time"]
    out["available_time"] = out["bar_close_time"]
    out["timestamp_semantics"] = "OPEN_TIME" if semantics == "open" else "CLOSE_TIME"
    for column in ("open", "high", "low", "close"):
        out[column] = pd.to_numeric(out[column], errors="raise").astype(float)
    for column in ("volume", "tick_volume", "spread"):
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    if not out["time"].is_monotonic_increasing or out["time"].duplicated().any():
        raise ValueError(f"{name} could not be normalized to a strict closed-time index")
    out.attrs = attrs | {
        "normalized_close_time": True,
        "timeframe": timeframe.upper(),
        "timestamp_semantics": "OPEN_TIME" if semantics == "open" else "CLOSE_TIME",
    }
    return out


def _end_exclusive(value: Any | None) -> pd.Timestamp | None:
    if value is None:
        return None
    timestamp = _utc(value, name="end")
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return timestamp + pd.Timedelta(days=1)
    return timestamp


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_sha256(frame: pd.DataFrame) -> str:
    columns = [
        column for column in (
            "source_index", "source_time", "bar_open_time", "bar_close_time",
            "open", "high", "low", "close", "tick_volume", "volume", "spread",
        ) if column in frame.columns
    ]
    records = [
        {column: json_safe(row[column]) for column in columns}
        for _, row in frame[columns].iterrows()
    ]
    return stable_sha256(records)


def _volume_source(frame: pd.DataFrame) -> str:
    if "volume" in frame.columns and pd.to_numeric(frame["volume"], errors="coerce").notna().any():
        return "REAL_EXCHANGE_VOLUME"
    if "tick_volume" in frame.columns and pd.to_numeric(frame["tick_volume"], errors="coerce").notna().any():
        return "TICK_VOLUME_PROXY"
    return "UNAVAILABLE"


def load_raw_frames(
    symbol: str,
    timeframes: tuple[str, ...],
    *,
    data_dir: Path | str,
    start: Any | None = None,
    end: Any | None = None,
    warmup_bars: int = 200,
    timestamp_semantics: str,
) -> dict[str, pd.DataFrame]:
    """Load local Parquet data, preserving warmup and complete provenance."""

    if warmup_bars < 0:
        raise ValueError("warmup_bars must be non-negative")
    root = Path(data_dir).resolve()
    start_ts = _utc(start, name="start") if start is not None else None
    end_ts = _end_exclusive(end)
    if start_ts is not None and end_ts is not None and start_ts >= end_ts:
        raise ValueError("visible start must precede end")

    result: dict[str, pd.DataFrame] = {}
    for timeframe in tuple(dict.fromkeys(tf.upper() for tf in timeframes)):
        nested = root / symbol / f"{symbol}_{timeframe}.parquet"
        flat = root / f"{symbol}_{timeframe}.parquet"
        path = nested if nested.exists() else flat
        if not path.is_file():
            raise FileNotFoundError(f"missing raw frame for {symbol}/{timeframe}: {nested}")
        source = pd.read_parquet(path)
        frame = _canonical_frame(
            source,
            name=str(path),
            timeframe=timeframe,
            timestamp_semantics=timestamp_semantics,
        )
        visible = pd.Series(True, index=frame.index)
        if start_ts is not None:
            visible &= frame["bar_close_time"] >= start_ts
        if end_ts is not None:
            visible &= frame["bar_close_time"] < end_ts
        positions = np.flatnonzero(visible.to_numpy())
        if len(positions) == 0:
            raise ValueError(f"no visible closed bars for {symbol}/{timeframe}")
        first = int(positions[0])
        last = int(positions[-1])
        if first < warmup_bars:
            raise ValueError(
                f"insufficient warmup for {symbol}/{timeframe}: "
                f"required={warmup_bars} available={first}"
            )
        used_start = max(0, first - warmup_bars)
        sliced = frame.iloc[used_start : last + 1].copy().reset_index(drop=True)
        visible_start = first - used_start
        visible_end = last - used_start
        relative_path = path.relative_to(root).as_posix()
        manifest = {
            "relative_source_path": relative_path,
            "symbol": symbol,
            "timeframe": timeframe,
            "timezone": "UTC",
            "timestamp_semantics": frame.attrs["timestamp_semantics"],
            "source_rows": int(len(frame)),
            "used_rows": int(len(sliced)),
            "warmup_rows": int(visible_start),
            "visible_rows": int(visible_end - visible_start + 1),
            "source_first_time": json_safe(frame.iloc[0]["source_time"]),
            "source_last_time": json_safe(frame.iloc[-1]["source_time"]),
            "used_first_time": json_safe(sliced.iloc[0]["bar_close_time"]),
            "used_last_time": json_safe(sliced.iloc[-1]["bar_close_time"]),
            "warmup_first_time": (
                json_safe(sliced.iloc[0]["bar_close_time"]) if visible_start else None
            ),
            "warmup_last_time": (
                json_safe(sliced.iloc[visible_start - 1]["bar_close_time"]) if visible_start else None
            ),
            "visible_first_time": json_safe(sliced.iloc[visible_start]["bar_close_time"]),
            "visible_last_time": json_safe(sliced.iloc[visible_end]["bar_close_time"]),
            "last_asof_available": json_safe(sliced.iloc[visible_end]["bar_close_time"]),
            "source_file_sha256": _file_sha256(path),
            "slice_sha256": _frame_sha256(sliced),
            "volume_source": _volume_source(sliced),
        }
        sliced.attrs = frame.attrs | {
            "manifest": manifest,
            "visible_start_index": visible_start,
            "visible_end_index": visible_end,
        }
        result[timeframe] = sliced
    first_common = max(
        _utc(frame.attrs["manifest"]["visible_first_time"], name=f"{tf}.visible_first")
        for tf, frame in result.items()
    )
    last_common = min(
        _utc(frame.attrs["manifest"]["visible_last_time"], name=f"{tf}.visible_last")
        for tf, frame in result.items()
    )
    if first_common > last_common:
        raise ValueError("required timeframes have no common closed-bar intersection")
    return result


def _candle_records(frame: pd.DataFrame, start: int, end: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    keep = (
        "source_index", "source_time", "bar_open_time", "bar_close_time", "available_time",
        "timestamp_semantics", "open", "high", "low", "close",
        "tick_volume", "volume", "spread",
    )
    for visible_index, (_, row) in enumerate(frame.iloc[start : end + 1].iterrows()):
        record = {column: json_safe(row[column]) for column in keep if column in row.index}
        record["index"] = visible_index
        records.append(record)
    return records


def _direction(value: int) -> str:
    return "bullish" if int(value) > 0 else "bearish" if int(value) < 0 else "neutral"


def _same_price(value: Any, target: Any) -> bool:
    return pd.notna(value) and pd.notna(target) and bool(
        np.isclose(float(value), float(target), rtol=0.0, atol=1e-12)
    )


def _find_formation_index(frame: pd.DataFrame, index: int, price: float, kind: str) -> int | None:
    column = "high" if kind == "HIGH" else "low"
    candidates = frame.iloc[:index]
    hits = candidates.index[
        np.isclose(candidates[column].to_numpy(float), float(price), atol=1e-12, rtol=0.0)
    ]
    return int(hits[-1]) if len(hits) else None


def extract_structure_events(
    frame: pd.DataFrame,
    *,
    structure: StructureConfig | None = None,
) -> list[dict[str, Any]]:
    """Serialize events emitted by the canonical structure engine."""

    timeframe = str(frame.attrs.get("timeframe") or "H1")
    semantics = "open" if frame.attrs.get("timestamp_semantics") == "OPEN_TIME" else "close"
    raw = _canonical_frame(frame, name="structure", timeframe=timeframe, timestamp_semantics=semantics)
    result = detect_market_structure(raw, structure or StructureConfig()).frame
    events: list[dict[str, Any]] = []
    prior_high: float | None = None
    prior_low: float | None = None
    high_swings: list[tuple[float, str]] = []
    low_swings: list[tuple[float, str]] = []
    all_swings: list[tuple[float, str]] = []
    bos_ids: dict[int, str] = {}
    swing_counter = bos_counter = choch_counter = 0

    for index in range(len(result)):
        row = result.iloc[index]
        time = json_safe(raw.iloc[index]["time"])
        if pd.notna(row.get("swing_high")) and not _same_price(row["swing_high"], prior_high):
            swing_counter += 1
            event_id = f"SW_H_{swing_counter:04d}"
            price = float(row["swing_high"])
            events.append({
                "id": event_id, "kind": "SWING", "swing_type": "HIGH",
                "index": index, "confirmed_index": index,
                "formation_index": _find_formation_index(raw, index, price, "HIGH"),
                "time": time, "confirmed_time": time, "parent_id": None,
                "direction": "neutral", "price": price, "status": "active",
            })
            prior_high = price
            high_swings.append((price, event_id))
            all_swings.append((price, event_id))
        if pd.notna(row.get("swing_low")) and not _same_price(row["swing_low"], prior_low):
            swing_counter += 1
            event_id = f"SW_L_{swing_counter:04d}"
            price = float(row["swing_low"])
            events.append({
                "id": event_id, "kind": "SWING", "swing_type": "LOW",
                "index": index, "confirmed_index": index,
                "formation_index": _find_formation_index(raw, index, price, "LOW"),
                "time": time, "confirmed_time": time, "parent_id": None,
                "direction": "neutral", "price": price, "status": "active",
            })
            prior_low = price
            low_swings.append((price, event_id))
            all_swings.append((price, event_id))
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
                "id": event_id, "kind": "BOS", "index": index,
                "confirmed_index": index, "time": time, "confirmed_time": time,
                "parent_id": parent_id, "direction": _direction(bos_direction),
                "price": json_safe(level), "status": "emitted",
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
                "id": event_id, "kind": "CHOCH", "index": index,
                "confirmed_index": index, "time": time, "confirmed_time": time,
                "parent_id": parent_id, "direction": _direction(choch_direction),
                "price": json_safe(level), "status": "emitted", "bos_parent_id": bos_parent_id,
            })
    order = {"SWING": 0, "BOS": 1, "CHOCH": 2}
    events.sort(key=lambda event: (int(event["index"]), order.get(str(event["kind"]), 99)))
    return events


def _visible_structure_events(
    events: list[dict[str, Any]], visible_start: int, visible_end: int
) -> list[dict[str, Any]]:
    visible_ids = {
        event["id"] for event in events
        if visible_start <= int(event["confirmed_index"]) <= visible_end
    }
    projected: list[dict[str, Any]] = []
    for event in events:
        confirmed = int(event["confirmed_index"])
        if not visible_start <= confirmed <= visible_end:
            continue
        item = dict(event)
        item["index"] = int(item["index"]) - visible_start
        item["confirmed_index"] = confirmed - visible_start
        formation = item.get("formation_index")
        if formation is not None:
            item["source_formation_index"] = int(formation)
            if int(formation) < visible_start:
                item["formation_index"] = None
                item["formation_visibility"] = "outside_visible_window"
            else:
                item["formation_index"] = int(formation) - visible_start
                item["formation_visibility"] = "visible"
        parent = item.get("parent_id")
        if parent is not None and parent not in visible_ids:
            item["source_parent_id"] = parent
            item["parent_id"] = None
            item["parent_visibility"] = "outside_visible_window"
        elif parent is not None:
            item["parent_visibility"] = "visible"
        bos_parent = item.get("bos_parent_id")
        if bos_parent is not None and bos_parent not in visible_ids:
            item["source_bos_parent_id"] = bos_parent
            item["bos_parent_id"] = None
        projected.append(item)
    return projected


def _last_closed_index(frame: pd.DataFrame, timestamp: Any) -> int:
    values = np.fromiter(
        (pd.Timestamp(value).value for value in pd.to_datetime(frame["time"], utc=True)),
        dtype="int64",
        count=len(frame),
    )
    target = _utc(timestamp, name="decision_time").value
    return int(np.searchsorted(values, target, side="right") - 1)


def _first_closed_at_or_after(frame: pd.DataFrame, timestamp: Any) -> int | None:
    values = np.fromiter(
        (pd.Timestamp(value).value for value in pd.to_datetime(frame["time"], utc=True)),
        dtype="int64",
        count=len(frame),
    )
    target = _utc(timestamp, name="available_time").value
    index = int(np.searchsorted(values, target, side="left"))
    return index if index < len(frame) else None


def _trade_records(
    signals: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    config: ReplayConfig,
    visible_start: int,
    visible_end: int,
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    main = frames[config.timeframe]
    fallback = main
    for signal_index, signal in enumerate(signals):
        source_entry_index = int(signal["entry_at"])
        if not visible_start <= source_entry_index <= visible_end:
            continue
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
        execution_tf = str(meta.get("exec_tf") or config.execution_tf or config.timeframe).upper()
        execution_frame = frames.get(execution_tf, fallback)
        execution_index = _last_closed_index(execution_frame, entry_time)
        levels = None
        if all(value is not None and np.isfinite(float(value)) for value in (entry, sl, tp)):
            levels = TradeLevels(direction=direction, entry=float(entry), sl=float(sl), tp=float(tp))
        resolution = (
            resolve_outcome(
                execution_frame["high"].to_numpy(float),
                execution_frame["low"].to_numpy(float),
                execution_index,
                levels,
                config.outcome,
            )
            if levels is not None
            else {"outcome": "INVALID", "exit_r": None, "exit_bar": None, "bars_held": None}
        )
        execution_exit = resolution.get("exit_bar")
        exit_time = execution_frame.iloc[int(execution_exit)]["time"] if execution_exit is not None else None
        main_exit = _first_closed_at_or_after(main, exit_time) if exit_time is not None else None
        result_visible = main_exit is not None and visible_start <= main_exit <= visible_end
        outcome = str(resolution["outcome"]) if result_visible else "PENDING"
        exit_price = None
        if result_visible and outcome == "TP":
            exit_price = float(tp)
        elif result_visible and outcome == "SL":
            exit_price = float(sl)
        export_number = len(trades) + 1
        exported_event_ids = {
            role: (f"{role}_{export_number:04d}" if raw_id else "")
            for role, raw_id in event_ids.items()
        }
        trades.append({
            "id": f"TRADE_{export_number:04d}",
            "signal_id": exported_event_ids.get("RETURN"),
            "chain_id": f"CHAIN_{export_number:04d}",
            "direction": _direction(direction),
            "entry_index": source_entry_index - visible_start,
            "source_entry_index": source_entry_index,
            "entry_time": json_safe(entry_time),
            "execution_tf": execution_tf,
            "entry": json_safe(entry), "sl": json_safe(sl), "tp": json_safe(tp),
            "exit_index": int(main_exit - visible_start) if result_visible else None,
            "exit_time": json_safe(exit_time) if result_visible else None,
            "exit_price": exit_price,
            "outcome": outcome,
            "exit_r": json_safe(resolution.get("exit_r")) if result_visible else None,
            "bars_held": resolution.get("bars_held") if result_visible else None,
            "result_confirmed_index": int(main_exit - visible_start) if result_visible else None,
            "event_ids": exported_event_ids,
        })
    return trades


def _git_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _config_dict(config: ReplayConfig) -> dict[str, Any]:
    def convert(value: Any) -> Any:
        if is_dataclass(value):
            return {key: convert(item) for key, item in asdict(value).items()}
        if isinstance(value, tuple):
            return [convert(item) for item in value]
        return json_safe(value)
    payload = convert(config)
    for key in (
        "git_commit", "git_branch", "generator_worktree_clean_before_run",
        "python_version", "node_version",
    ):
        payload.pop(key, None)
    return payload


def _manifest(frames: dict[str, pd.DataFrame], config: ReplayConfig) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for tf, frame in frames.items():
        existing = dict(frame.attrs.get("manifest") or {})
        if not existing:
            start = int(frame.attrs.get("visible_start_index", 0))
            end = int(frame.attrs.get("visible_end_index", len(frame) - 1))
            existing = {
                "relative_source_path": "IN_MEMORY",
                "symbol": config.symbol,
                "timeframe": tf,
                "timezone": "UTC",
                "timestamp_semantics": frame.attrs.get("timestamp_semantics", "CLOSE_TIME"),
                "source_rows": len(frame), "used_rows": len(frame),
                "warmup_rows": start, "visible_rows": end - start + 1,
                "source_first_time": json_safe(frame.iloc[0]["source_time"]),
                "source_last_time": json_safe(frame.iloc[-1]["source_time"]),
                "used_first_time": json_safe(frame.iloc[0]["bar_close_time"]),
                "used_last_time": json_safe(frame.iloc[-1]["bar_close_time"]),
                "warmup_first_time": json_safe(frame.iloc[0]["bar_close_time"]) if start else None,
                "warmup_last_time": json_safe(frame.iloc[start - 1]["bar_close_time"]) if start else None,
                "visible_first_time": json_safe(frame.iloc[start]["bar_close_time"]),
                "visible_last_time": json_safe(frame.iloc[end]["bar_close_time"]),
                "last_asof_available": json_safe(frame.iloc[end]["bar_close_time"]),
                "source_file_sha256": None,
                "slice_sha256": _frame_sha256(frame),
                "volume_source": _volume_source(frame),
            }
        items[tf] = existing
    return {
        "symbol": config.symbol,
        "timezone": "UTC",
        "timestamp_semantics": "OPEN_TIME" if config.timestamp_semantics == "open" else "CLOSE_TIME",
        "timeframes": items,
        "mutation_policy": "READ_ONLY_NO_DOWNLOADS",
    }


def _disabled_wyckoff_timeline(
    frames: dict[str, pd.DataFrame], main_tf: str, start: int, end: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    timeline: list[dict[str, Any]] = []
    main = frames[main_tf]
    for visible_index, source_index in enumerate(range(start, end + 1)):
        decision = _utc(main.iloc[source_index]["time"], name="decision_time")
        asof_by_tf: dict[str, str | None] = {}
        for tf, frame in frames.items():
            index = _last_closed_index(frame, decision)
            asof_by_tf[tf] = json_safe(frame.iloc[index]["time"]) if index >= 0 else None
        snapshot = {
            "phase": "UNKNOWN", "phase_state": "NEUTRAL", "authority_tf": "",
            "range_ref": {}, "events": [], "evidence_refs": [], "effort_result": {},
            "volume_mode": "UNAVAILABLE", "ict_alignment": "UNRESOLVED",
            "conflict": False, "explanation": "Wyckoff timeline disabled by CLI",
            "layers": {}, "decision_time": decision.isoformat(),
            "policy": "WYCKOFF_DISABLED", "range_id": None, "episode_id": None,
            "fsm_contract": "RUNTIME_BASIC_NOT_WYCKOFF_7",
        }
        timeline.append({
            "index": visible_index, "decision_time": decision.isoformat(),
            "asof_by_tf": asof_by_tf,
            "ict": {
                "context": {"status": "NOT_REQUESTED", "layers": {}, "constraints": None},
                "visible_event_ids": [],
            },
            "wyckoff": snapshot,
            "delta": {
                "changed": visible_index == 0, "fields": {}, "new_wyckoff_event_ids": [],
                "interpretation": "OBSERVATIONAL_DELTA_NOT_SIGNAL",
            },
            "policy": "CLOSED_PREFIX_DIAGNOSTIC_ONLY",
        })
    return timeline, []


def run_visual_replay(
    raw_frames: dict[str, pd.DataFrame],
    config: ReplayConfig | None = None,
) -> VisualBacktest:
    """Run canonical engines and return a deterministic v1.1 replay artifact."""

    config = config or ReplayConfig()
    main_tf = config.timeframe.upper()
    authority_tf = config.authority_tf.upper()
    if main_tf not in raw_frames:
        raise KeyError(f"main timeframe {main_tf!r} not supplied")
    frames: dict[str, pd.DataFrame] = {}
    for tf, frame in raw_frames.items():
        tf_upper = tf.upper()
        frames[tf_upper] = _canonical_frame(
            frame,
            name=tf_upper,
            timeframe=tf_upper,
            timestamp_semantics=config.timestamp_semantics,
        )
    if authority_tf not in frames:
        raise KeyError(f"authority timeframe {authority_tf!r} not supplied")

    main_raw = frames[main_tf]
    visible_start = int(main_raw.attrs.get("visible_start_index", 0))
    visible_end = int(main_raw.attrs.get("visible_end_index", len(main_raw) - 1))
    if visible_start < 0 or visible_end >= len(main_raw) or visible_start > visible_end:
        raise ValueError("invalid visible main-frame bounds")
    featured = {tf: build_features(frame) for tf, frame in frames.items()}
    for tf, frame in featured.items():
        frame.attrs = frames[tf].attrs
    main = featured[main_tf]

    closed_index: dict[str, int] = {}
    context_tfs = tuple(featured)

    def context_at(index: int) -> dict[str, Any]:
        timestamp = main.iloc[index]["time"]
        for tf, frame in featured.items():
            closed_index[tf] = _last_closed_index(frame, timestamp)
        return build_multitf_context(featured, timestamp, tfs=context_tfs, closed_index=closed_index)

    htf = (config.htf_timeframe or authority_tf).upper()
    if htf not in featured:
        htf = main_tf
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
        "ltf_tf": main_tf,
        "htf": htf,
        "exec_frames": {tf: featured[tf] for tf in ("M5", "M1") if tf in featured},
    }
    if config.use_multitf_context:
        replay_kwargs["est_htf_ctx_fn"] = context_at
    else:
        # run_sequence_traced routes through SequenceRunner, which only accepts
        # est_htf_ctx_fn. Wrap the legacy single-HTF reader into a minimal
        # context so extract_htf_layer yields the identical HTF dict (trend,
        # sweep_up, sweep_down, pd_zones) and behaviour is unchanged.
        def legacy_context_at(index: int) -> dict[str, Any]:
            layer = htf_at(index)
            return {
                htf: {
                    "tf": htf,
                    "available": True,
                    "trend": layer["trend"],
                    "sweep_up": layer["sweep_up"],
                    "sweep_down": layer["sweep_down"],
                    "pd_zones": layer["pd_zones"],
                }
            }

        replay_kwargs["est_htf_ctx_fn"] = legacy_context_at
    signals, phase_seen, expedientes, sequence_state = run_sequence_traced(
        main, None, config.sequence, **replay_kwargs
    )

    structure_events = _visible_structure_events(
        extract_structure_events(main_raw, structure=config.structure), visible_start, visible_end
    )
    trades = _trade_records(signals, featured, config, visible_start, visible_end)
    timeline_layers = tuple(tf for tf in config.wyckoff_layers if tf.upper() in frames)
    if config.wyckoff_enabled:
        timeline, wyckoff_events = build_wyckoff_timeline(
            frames,
            main_tf=main_tf,
            authority_tf=authority_tf,
            visible_start_index=visible_start,
            visible_end_index=visible_end,
            layers=timeline_layers,
        )
    else:
        timeline, wyckoff_events = _disabled_wyckoff_timeline(
            frames, main_tf, visible_start, visible_end
        )
    for point in timeline:
        cursor = int(point["index"])
        decision = _utc(point["decision_time"], name="timeline.decision_time")
        point["ict"]["visible_event_ids"] = [
            event["id"]
            for event in structure_events
            if int(event["confirmed_index"]) <= cursor
            and _utc(event["confirmed_time"], name="structure.confirmed_time") <= decision
        ]
    candles = _candle_records(main_raw, visible_start, visible_end)
    manifest = _manifest(frames, config)
    config_payload = _config_dict(config)
    config_hash = stable_sha256(config_payload)
    commit = config.git_commit if config.git_commit != "UNKNOWN" else _git_commit(Path(__file__).resolve().parents[1])
    slice_hashes = {tf: item["slice_sha256"] for tf, item in manifest["timeframes"].items()}
    run_id = stable_sha256({"git_commit": commit, "config_sha256": config_hash, "slice_sha256": slice_hashes})[:24]
    visible_window = {
        "start": candles[0]["bar_close_time"],
        "end": candles[-1]["bar_close_time"],
        "rows": len(candles),
        "warmup_bars": config.warmup_bars,
        "index_semantics": "VISIBLE_ZERO_BASED",
    }
    run_metadata = {
        "run_id": run_id,
        "git_commit": commit,
        "git_branch": config.git_branch,
        "generator_worktree_clean_before_run": bool(config.generator_worktree_clean_before_run),
        "python_version": config.python_version,
        "node_version": config.node_version,
        "config": config_payload,
        "config_sha256": config_hash,
        "slice_sha256": slice_hashes,
        "engine_lineage": {
            "structure": "engine.bos.structure.detect_market_structure",
            "features": "engine.market_features.build_features",
            "navigation": "engine.mtf_navigation.MTFNavigator",
            "replay": "engine.sequence.run_sequence_traced",
            "outcome": "engine.sequential_outcome.resolve_outcome",
            "wyckoff": "engine.Wyckoff.build_wyckoff_snapshot",
        },
        "phase_seen": json_safe(phase_seen),
        "expedientes": sum(1 for signal in signals if signal.get("expediente") is not None),
        "legacy_backtest": False,
        "command": "DIRECT_API",
    }
    scientific_status = {
        "classification": "DIAGNOSTIC_CAUSAL_REPLAY",
        "scientific_gate": "NOT_EVALUATED_BY_THIS_VIEWER",
        "edge_claimed": False,
        "wyckoff_contract": "RUNTIME_BASIC_NOT_WYCKOFF_7",
        "pit_temporal_consistency": {
            "status": "PASS",
            "points_checked": 80,
            "divergences": 0,
            "meaning": "TEMPORAL_CONSISTENCY_IN_AUDITED_SAMPLE_ONLY",
            "source": "reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json",
        },
        "h1_feasibility": {
            "observations": 515,
            "required": 778,
            "verdict": "CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N",
            "source": (
                "reports/audits/experiments/wyckoff_ict_01/certification/"
                "CERTIFICATION_VERDICT.md"
            ),
        },
        "edge": "NOT_PROVEN_BY_THIS_VIEWER",
    }
    market_state = build_market_state(
        frames, signals, config, visible_start, visible_end
    )

    # FASE 4.1: instanciar el funnel AHF canónico (engine/ahf.py) UNA vez por run
    # y serializar cada AHFSnapshot en timeline[i]["ict"]["context"]. setup_builder
    # luego SOLO TRADUCE ese snapshot; no re-deriva la FSM.
    # Nota de memoria: serializamos un dict PLANO (sin el history completo del
    # funnel, que crece O(n^2) por vela) para no inflar el artifact.
    decision_times = [point["decision_time"] for point in timeline]
    try:
        ahf = AdaptiveHierarchicalFunnel(frames, AHFConfig())
        ahf_snapshots = ahf.run_timeline(decision_times, exec_tf=main_tf)
        for point, snap in zip(timeline, ahf_snapshots):
            last_inv = None
            if snap.history:
                last_inv = snap.history[-1].invalidation_reason
            point.setdefault("ict", {})["context"] = {
                "status": "AHF_LOCKED",
                "ahf_snapshot": {
                    "state": snap.state.value,
                    "active_tf": snap.active_tf,
                    "confirmed_context": snap.confirmed_context,
                    "last_event": snap.last_event.value,
                    "invalidation_reason": last_inv,
                },
                "layers": snap.confirmed_context,
                "constraints": snap.constraints.to_dict() if snap.constraints else None,
            }
    except Exception as exc:  # pragma: no cover - fail closed on canonical failure
        raise RuntimeError(
            "canonical AHF projection failed; refusing to emit an incomplete causal replay"
        ) from exc

    setups = build_setup_state(timeline, config, ahf_snapshots=ahf_snapshots)
    return VisualBacktest(
        symbol=config.symbol,
        timeframe=main_tf,
        authority_tf=authority_tf,
        visible_window=visible_window,
        policy=dict(REQUIRED_POLICY),
        candles=candles,
        structure_events=structure_events,
        trades=trades,
        timeline=timeline,
        wyckoff_events=wyckoff_events,
        data_manifest=manifest,
        run_metadata=run_metadata,
        scientific_status=scientific_status,
        market_state=market_state,
        setups=setups,
    )


__all__ = [
    "DEFAULT_TFS", "ReplayConfig", "extract_structure_events", "load_raw_frames",
    "run_visual_replay", "timeframe_duration",
]
