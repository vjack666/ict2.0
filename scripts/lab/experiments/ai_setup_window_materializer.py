"""Materializa setups causales por ventanas desde Funnel + backtest.

Este adaptador es deliberadamente independiente de los productores canónicos:
no ejecuta replay, no abre ``data/raw`` y no importa MT5. Lee los artefactos
JSON ya congelados con un parser de streaming, conserva solo la ventana
solicitada y escribe filas JSONL en lotes pequeños. La salida es material
técnico para revisión; no crea snapshots, no promociona modelos y siempre
lleva ``can_trade=false``.

Ejemplo::

    python -m scripts.lab.experiments.ai_setup_window_materializer \
      --funnel reports/audits/experiments/ai/month.funnel.json \
      --backtest reports/audits/experiments/ai/month.backtest.json \
      --window 2025-01-01T00:00:00Z,2025-01-31T23:59:59Z \
      --output reports/audits/experiments/ai/month.setup_rows.jsonl \
      --batch-size 64

``--window`` may be repeated. Each window is processed independently, so
memory is bounded by one window even when the source artifact is multi-year.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_VERSION = "AI_SETUP_WINDOW_DATASET_V1"
FUNNEL_CONTRACT_VERSION = "EPISODES_FUNNEL_V1"
BACKTEST_SCHEMA_VERSION = "1.0"
DEFAULT_BATCH_SIZE = 256
_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
_DIRECTION_ALIASES = {
    "BULLISH": 1,
    "BULL": 1,
    "LONG": 1,
    "BEARISH": -1,
    "BEAR": -1,
    "SHORT": -1,
}
_FORBIDDEN_FEATURE_PARTS = (
    "label", "outcome", "exit", "future", "pnl", "profit", "return",
    "entry", "stop", "target", "sl", "tp", "bars_held", "result",
)
_TIME_PARTS = ("time", "timestamp", "asof", "available", "observed", "created")
_REGISTERED_SPLITS = (
    ("DESIGN", datetime(2006, 1, 1, tzinfo=timezone.utc), datetime(2015, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
    ("VALIDATION", datetime(2016, 1, 1, tzinfo=timezone.utc), datetime(2020, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
    ("HOLDOUT", datetime(2021, 1, 1, tzinfo=timezone.utc), datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
)


class SetupWindowError(ValueError):
    """La entrada no cumple el límite causal o el contrato de la utilidad."""


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def contains(self, value: datetime) -> bool:
        return self.start <= value <= self.end

    def to_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


@dataclass(frozen=True)
class WindowResult:
    """Resultado de una ventana, sin autoridad científica o de trading."""

    rows: tuple[dict[str, Any], ...]
    diagnostics: tuple[str, ...]
    rejected_count: int
    window: Window


class _JsonCursor:
    """Cursor JSON mínimo: conserva en memoria solo un valor solicitado."""

    def __init__(self, path: Path, *, chunk_size: int = 64 * 1024) -> None:
        self.path = Path(path)
        self.file = self.path.open("rb")
        self.chunk_size = chunk_size
        self.buffer = b""
        self.position = 0
        self.eof = False

    def __enter__(self) -> "_JsonCursor":
        return self

    def __exit__(self, *_: object) -> None:
        self.file.close()

    def _fill(self) -> bool:
        if self.position < len(self.buffer):
            return True
        chunk = self.file.read(self.chunk_size)
        if not chunk:
            self.buffer = b""
            self.position = 0
            self.eof = True
            return False
        self.buffer = chunk
        self.position = 0
        return True

    def peek(self) -> int | None:
        return self.buffer[self.position] if self._fill() else None

    def take(self) -> int:
        value = self.peek()
        if value is None:
            raise SetupWindowError(f"JSON_TRUNCATED: {self.path}")
        self.position += 1
        return value

    def skip_ws(self) -> None:
        while True:
            value = self.peek()
            if value is None or value not in b" \t\r\n":
                return
            self.position += 1

    def expect(self, expected: int) -> None:
        actual = self.take()
        if actual != expected:
            raise SetupWindowError(
                f"JSON_INVALID: {self.path} expected={chr(expected)!r} got={chr(actual)!r}"
            )

    def read_string(self) -> str:
        self.skip_ws()
        raw = bytearray()
        raw.append(self.take())
        if raw[0] != ord('"'):
            raise SetupWindowError(f"JSON_INVALID_STRING: {self.path}")
        escaped = False
        while True:
            value = self.take()
            raw.append(value)
            if escaped:
                escaped = False
            elif value == ord("\\"):
                escaped = True
            elif value == ord('"'):
                try:
                    return json.loads(bytes(raw).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise SetupWindowError(f"JSON_INVALID_STRING: {self.path}") from exc

    def read_value_bytes(self) -> bytes:
        """Consume one JSON value, retaining only that value as bytes."""

        self.skip_ws()
        first = self.peek()
        if first is None:
            raise SetupWindowError(f"JSON_TRUNCATED: {self.path}")
        if first not in (ord("{"), ord("[")):
            raw = bytearray()
            while True:
                value = self.peek()
                if value is None or value in b",}] \t\r\n":
                    return bytes(raw)
                raw.append(self.take())

        raw = bytearray()
        depth = 0
        in_string = False
        escaped = False
        while True:
            value = self.take()
            raw.append(value)
            if in_string:
                if escaped:
                    escaped = False
                elif value == ord("\\"):
                    escaped = True
                elif value == ord('"'):
                    in_string = False
                continue
            if value == ord('"'):
                in_string = True
            elif value in (ord("{"), ord("[")):
                depth += 1
            elif value in (ord("}"), ord("]")):
                depth -= 1
                if depth == 0:
                    return bytes(raw)

    def skip_value(self) -> None:
        """Consume one value without materializing it."""

        self.skip_ws()
        first = self.peek()
        if first is None:
            raise SetupWindowError(f"JSON_TRUNCATED: {self.path}")
        if first not in (ord("{"), ord("[")):
            while True:
                value = self.peek()
                if value is None or value in b",}] \t\r\n":
                    return
                self.position += 1
        else:
            self.read_value_bytes_discard()

    def read_value_bytes_discard(self) -> None:
        self.skip_ws()
        first = self.peek()
        if first not in (ord("{"), ord("[")):
            self.skip_value()
            return
        depth = 0
        in_string = False
        escaped = False
        while True:
            value = self.take()
            if in_string:
                if escaped:
                    escaped = False
                elif value == ord("\\"):
                    escaped = True
                elif value == ord('"'):
                    in_string = False
                continue
            if value == ord('"'):
                in_string = True
            elif value in (ord("{"), ord("[")):
                depth += 1
            elif value in (ord("}"), ord("]")):
                depth -= 1
                if depth == 0:
                    return

    def iter_array(self) -> Iterator[Any]:
        self.skip_ws()
        self.expect(ord("["))
        self.skip_ws()
        if self.peek() == ord("]"):
            self.take()
            return
        while True:
            raw = self.read_value_bytes()
            try:
                yield json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SetupWindowError(f"JSON_ARRAY_ITEM_INVALID: {self.path}") from exc
            self.skip_ws()
            delimiter = self.take()
            if delimiter == ord("]"):
                return
            if delimiter != ord(","):
                raise SetupWindowError(f"JSON_ARRAY_INVALID: {self.path}")


def _decode(raw: bytes, path: Path) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SetupWindowError(f"JSON_VALUE_INVALID: {path}") from exc


def _read_fields(path: str | Path, names: set[str]) -> dict[str, Any]:
    source = Path(path)
    result: dict[str, Any] = {}
    with _JsonCursor(source) as cursor:
        cursor.skip_ws()
        cursor.expect(ord("{"))
        while True:
            cursor.skip_ws()
            if cursor.peek() == ord("}"):
                cursor.take()
                return result
            key = cursor.read_string()
            cursor.skip_ws()
            cursor.expect(ord(":"))
            if key in names:
                result[key] = _decode(cursor.read_value_bytes(), source)
            else:
                cursor.skip_value()
            cursor.skip_ws()
            delimiter = cursor.take()
            if delimiter == ord("}"):
                return result
            if delimiter != ord(","):
                raise SetupWindowError(f"JSON_OBJECT_INVALID: {source}")


def _iter_array(path: str | Path, name: str) -> Iterator[Any]:
    source = Path(path)
    with _JsonCursor(source) as cursor:
        cursor.skip_ws()
        cursor.expect(ord("{"))
        while True:
            cursor.skip_ws()
            if cursor.peek() == ord("}"):
                cursor.take()
                return
            key = cursor.read_string()
            cursor.skip_ws()
            cursor.expect(ord(":"))
            if key == name:
                yield from cursor.iter_array()
            else:
                cursor.skip_value()
            cursor.skip_ws()
            delimiter = cursor.take()
            if delimiter == ord("}"):
                return
            if delimiter != ord(","):
                raise SetupWindowError(f"JSON_OBJECT_INVALID: {source}")


def _sha256_file(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {"path": str(path.resolve()), "bytes": size, "sha256": digest.hexdigest()}


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SetupWindowError(f"{field}_INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise SetupWindowError(f"{field}_INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _direction(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise SetupWindowError(f"{field}_INVALID_DIRECTION")
    if isinstance(value, (int, float)) and int(value) in (-1, 1) and float(value) == int(value):
        return int(value)
    if isinstance(value, str):
        raw = value.strip().upper()
        if raw in _DIRECTION_ALIASES:
            return _DIRECTION_ALIASES[raw]
        try:
            result = int(raw)
        except ValueError:
            result = 0
        if result in (-1, 1):
            return result
    raise SetupWindowError(f"{field}_INVALID_DIRECTION")


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SetupWindowError(f"{field}_INVALID_POSITIVE_INTEGER")
    return value


def parse_window(start: Any, end: Any) -> Window:
    start_dt = _utc(start, "window_start")
    end_dt = _utc(end, "window_end")
    if start_dt > end_dt:
        raise SetupWindowError("WINDOW_START_AFTER_END")
    return Window(start_dt, end_dt)


def parse_window_spec(value: str) -> Window:
    parts = value.split(",")
    if len(parts) != 2:
        raise SetupWindowError("WINDOW_FORMAT_EXPECTED_START_COMMA_END")
    return parse_window(parts[0], parts[1])


def _split_for(value: datetime) -> str:
    for name, start, end in _REGISTERED_SPLITS:
        if start <= value <= end:
            return name
    raise SetupWindowError("EVENT_OUTSIDE_PREREGISTERED_SPLIT")


def _validate_features(value: Any, decision_time: datetime, path: str = "features_at_t") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _FORBIDDEN_FEATURE_PARTS):
                raise SetupWindowError(f"FUTURE_FEATURE_FIELD:{path}.{key}")
            if key_text in {"time", "timestamp", "event_time", "observed_time", "available_time", "created_at", "as_of", "asof"}:
                if _utc(child, f"{path}.{key}") > decision_time:
                    raise SetupWindowError(f"FUTURE_FEATURE_TIME:{path}.{key}")
            elif any(part in key_text for part in _TIME_PARTS) and isinstance(child, str):
                try:
                    if _utc(child, f"{path}.{key}") > decision_time:
                        raise SetupWindowError(f"FUTURE_FEATURE_TIME:{path}.{key}")
                except SetupWindowError as exc:
                    if "INVALID_TIMESTAMP" not in str(exc):
                        raise
            _validate_features(child, decision_time, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_features(child, decision_time, f"{path}[{index}]")


def _funnel_context(path: Path) -> tuple[dict[str, Any], list[str]]:
    fields = _read_fields(path, {"contract_version", "aggregated_status", "gates", "full_prefix", "generator_commit", "provenance"})
    diagnostics: list[str] = []
    if fields.get("contract_version") != FUNNEL_CONTRACT_VERSION:
        diagnostics.append("FUNNEL_CONTRACT_MISMATCH")
    if fields.get("aggregated_status") != "PASS":
        diagnostics.append(f"FUNNEL_STATUS_{fields.get('aggregated_status', 'MISSING')}")
    gates = fields.get("gates")
    if not isinstance(gates, Mapping) or not gates or any(value != "PASS" for value in gates.values()):
        diagnostics.append("FUNNEL_GATES_NOT_PASS")
    prefix = fields.get("full_prefix")
    if not isinstance(prefix, Mapping) or prefix.get("prefix_matches_full") is not True:
        diagnostics.append("FUNNEL_FULL_PREFIX_NOT_PROVEN")
    commit = fields.get("generator_commit")
    if not isinstance(commit, str) or not _HEX_COMMIT.fullmatch(commit):
        diagnostics.append("FUNNEL_GENERATOR_COMMIT_INVALID")
    provenance = fields.get("provenance")
    if not isinstance(provenance, Mapping):
        diagnostics.append("FUNNEL_PROVENANCE_MISSING")
    elif provenance.get("status") != "PASS":
        diagnostics.append(f"FUNNEL_PROVENANCE_{provenance.get('status', 'MISSING')}")
    return fields, diagnostics


def _backtest_context(path: Path) -> tuple[dict[str, Any], list[str], int]:
    fields = _read_fields(path, {"schema_version", "symbol", "timeframe", "metadata", "provenance"})
    diagnostics: list[str] = []
    if fields.get("schema_version") != BACKTEST_SCHEMA_VERSION:
        diagnostics.append("BACKTEST_SCHEMA_MISMATCH")
    metadata = fields.get("metadata")
    outcome = metadata.get("outcome") if isinstance(metadata, Mapping) else None
    candidate = outcome.get("horizon_bars") if isinstance(outcome, Mapping) else None
    horizon = _positive_int(candidate, "horizon_bars")
    if not isinstance(metadata, Mapping) or metadata.get("causal") is not True:
        diagnostics.append("BACKTEST_CAUSAL_METADATA_NOT_PASS")
    backtest_provenance = fields.get("provenance")
    if not isinstance(backtest_provenance, Mapping) or backtest_provenance.get("status") != "PASS":
        diagnostics.append("BACKTEST_PROVENANCE_NOT_PASS")
    return fields, diagnostics, horizon


def _select_episodes(path: Path, window: Window) -> tuple[list[dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    for item in _iter_array(path, "episodes"):
        if not isinstance(item, Mapping):
            diagnostics.append("EPISODE_NOT_OBJECT")
            continue
        try:
            decision = _utc(item.get("decision_time"), "episode_decision_time")
        except SetupWindowError:
            diagnostics.append("EPISODE_DECISION_TIME_INVALID")
            continue
        if not window.contains(decision):
            continue
        if item.get("status") != "ACCEPTED":
            diagnostics.append(f"EPISODE_NOT_ACCEPTED:{item.get('episode_id', '')}")
            continue
        meta = item.get("meta")
        signal_index = meta.get("backtest_signal_index") if isinstance(meta, Mapping) else None
        if isinstance(signal_index, bool) or not isinstance(signal_index, int) or signal_index < 0:
            diagnostics.append(f"EPISODE_SIGNAL_INDEX_INVALID:{item.get('episode_id', '')}")
            continue
        features = item.get("features_at_t")
        if not isinstance(features, Mapping):
            diagnostics.append(f"MISSING_FEATURES_AT_T:{item.get('episode_id', '')}")
            continue
        try:
            direction = _direction(item.get("direction"), "episode_direction")
            _validate_features(features, decision)
            sequence = features.get("sequence")
            context = features.get("context_inputs")
            depth = _positive_int(features.get("sequence_depth"), "sequence_depth")
            if not isinstance(sequence, list) or not sequence or not isinstance(context, Mapping):
                raise SetupWindowError("FEATURES_AT_T_CONTRACT_INCOMPLETE")
            if _direction(context.get("sequence_direction"), "sequence_direction") != direction:
                raise SetupWindowError("FEATURE_DIRECTION_MISMATCH")
        except SetupWindowError as exc:
            diagnostics.append(f"EPISODE_INVALID:{item.get('episode_id', '')}:{exc}")
            continue
        selected.append({
            "episode_id": str(item.get("episode_id") or f"EP_SIGNAL_{signal_index + 1:06d}"),
            "decision_time": decision,
            "direction": direction,
            "features_at_t": deepcopy(dict(features)),
            "signal_index": signal_index,
            "symbol": str(item.get("symbol") or ""),
        })
    return selected, diagnostics


def _selected_trades(path: Path, signal_indexes: set[int]) -> tuple[dict[int, dict[str, Any]], list[str]]:
    matches: dict[int, list[dict[str, Any]]] = {index: [] for index in signal_indexes}
    diagnostics: list[str] = []
    for item in _iter_array(path, "trades"):
        if not isinstance(item, Mapping):
            diagnostics.append("TRADE_NOT_OBJECT")
            continue
        index = item.get("signal_index")
        if isinstance(index, bool) or not isinstance(index, int) or index not in signal_indexes:
            continue
        matches[index].append(dict(item))
    result: dict[int, dict[str, Any]] = {}
    for index, candidates in matches.items():
        if len(candidates) != 1:
            diagnostics.append(f"TRADE_MISSING_OR_AMBIGUOUS:{index}")
        else:
            result[index] = candidates[0]
    return result, diagnostics


def _candle_targets(trades: Iterable[Mapping[str, Any]], horizon: int) -> set[int]:
    targets: set[int] = set()
    for trade in trades:
        entry = trade.get("entry_index")
        if isinstance(entry, int) and not isinstance(entry, bool):
            targets.add(entry)
            targets.add(entry + horizon)
        exit_index = trade.get("exit_index")
        if isinstance(exit_index, int) and not isinstance(exit_index, bool):
            targets.add(exit_index)
    return targets


def _load_target_candles(path: Path, targets: set[int]) -> tuple[dict[int, dict[str, Any]], int]:
    result: dict[int, dict[str, Any]] = {}
    max_index = -1
    for item in _iter_array(path, "candles"):
        if not isinstance(item, Mapping):
            continue
        index = item.get("index")
        if isinstance(index, int) and not isinstance(index, bool):
            max_index = max(max_index, index)
            if index in targets:
                result[index] = dict(item)
    return result, max_index


def _row_for(
    episode: Mapping[str, Any],
    trade: Mapping[str, Any],
    candles: Mapping[int, Mapping[str, Any]],
    horizon: int,
    backtest: Mapping[str, Any],
) -> dict[str, Any]:
    entry_index = trade.get("entry_index")
    if isinstance(entry_index, bool) or not isinstance(entry_index, int) or entry_index < 0:
        raise SetupWindowError("TRADE_ENTRY_INDEX_INVALID")
    entry_candle = candles.get(entry_index)
    if entry_candle is None:
        raise SetupWindowError("TRADE_ENTRY_CANDLE_MISSING")
    decision = episode["decision_time"]
    if _utc(entry_candle.get("time"), "entry_candle_time") != decision:
        raise SetupWindowError("TRADE_ENTRY_TIME_MISMATCH")
    if _direction(trade.get("direction"), "trade_direction") != episode["direction"]:
        raise SetupWindowError("TRADE_DIRECTION_MISMATCH")
    outcome = str(trade.get("outcome") or "").upper()
    labels = {"TP": "continuation", "SL": "reversal", "OPEN": "failure"}
    if outcome not in labels:
        raise SetupWindowError("TRADE_OUTCOME_INVALID")
    exit_index = trade.get("exit_index")
    if outcome == "OPEN":
        if exit_index is not None:
            raise SetupWindowError("OPEN_HAS_EXIT")
        available_candle = candles.get(entry_index + horizon)
        if available_candle is None:
            raise SetupWindowError("INSUFFICIENT_FUTURE_HORIZON")
        available_time = _utc(available_candle.get("time"), "horizon_candle_time")
        available_index: int | None = None
    else:
        if isinstance(exit_index, bool) or not isinstance(exit_index, int) or not entry_index < exit_index <= entry_index + horizon:
            raise SetupWindowError("EXIT_OUTSIDE_ALLOWED_HORIZON")
        exit_candle = candles.get(exit_index)
        if exit_candle is None:
            raise SetupWindowError("TRADE_EXIT_CANDLE_MISSING")
        available_time = _utc(exit_candle.get("time"), "exit_candle_time")
        if trade.get("exit_time") is not None and _utc(trade["exit_time"], "trade_exit_time") != available_time:
            raise SetupWindowError("TRADE_EXIT_TIME_MISMATCH")
        available_index = exit_index
    return {
        "dataset_id": CONTRACT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "symbol": str(backtest.get("symbol") or episode.get("symbol") or ""),
        "timeframe": str(backtest.get("timeframe") or ""),
        "episode_id": episode["episode_id"],
        "event_time": decision.isoformat(),
        "split": _split_for(decision),
        "label_available_time": available_time.isoformat(),
        "direction": int(episode["direction"]),
        "sequence_depth": int(episode["features_at_t"]["sequence_depth"]),
        "features_at_t": deepcopy(dict(episode["features_at_t"])),
        "label": labels[outcome],
        f"label_end_{horizon}": labels[outcome],
        "horizon_bars": horizon,
        "backtest_signal_index": episode["signal_index"],
        "backtest_trade_id": str(trade.get("id") or ""),
        "backtest_entry_index": entry_index,
        "backtest_exit_index": available_index,
        "label_source": "canonical_backtest_trade_outcome",
        "can_trade": False,
    }


def materialize_window(
    funnel_path: str | Path,
    backtest_path: str | Path,
    window: Window,
    *,
    horizon_bars: int | None = None,
) -> WindowResult:
    """Materializa una sola ventana sin cargar arrays completos."""

    funnel = Path(funnel_path)
    backtest = Path(backtest_path)
    funnel_fields, funnel_diagnostics = _funnel_context(funnel)
    backtest_fields, backtest_diagnostics, discovered_horizon = _backtest_context(backtest)
    horizon = discovered_horizon if horizon_bars is None else _positive_int(horizon_bars, "horizon_bars")
    diagnostics = list(funnel_diagnostics) + list(backtest_diagnostics)
    episodes, episode_diagnostics = _select_episodes(funnel, window)
    diagnostics.extend(episode_diagnostics)
    trades, trade_diagnostics = _selected_trades(backtest, {int(item["signal_index"]) for item in episodes})
    diagnostics.extend(trade_diagnostics)
    candles, _ = _load_target_candles(backtest, _candle_targets(trades.values(), horizon))
    rows: list[dict[str, Any]] = []
    row_rejections = 0
    for episode in episodes:
        trade = trades.get(int(episode["signal_index"]))
        if trade is None:
            continue
        try:
            rows.append(_row_for(episode, trade, candles, horizon, backtest_fields))
        except SetupWindowError as exc:
            diagnostics.append(f"ROW_REJECTED:{episode['episode_id']}:{exc}")
            row_rejections += 1
    return WindowResult(
        tuple(rows),
        tuple(diagnostics),
        len(episode_diagnostics) + len(trade_diagnostics) + row_rejections,
        window,
    )


def _provenance_context(funnel_path: Path, backtest_path: Path) -> tuple[dict[str, Any], list[str]]:
    funnel = _read_fields(funnel_path, {"provenance"}).get("provenance")
    backtest = _read_fields(backtest_path, {"provenance"}).get("provenance")
    diagnostics: list[str] = []
    for name, value in (("FUNNEL", funnel), ("BACKTEST", backtest)):
        if not isinstance(value, Mapping):
            diagnostics.append(f"{name}_PROVENANCE_MISSING")
        elif value.get("status") != "PASS":
            diagnostics.append(f"{name}_PROVENANCE_{value.get('status', 'MISSING')}")
    return {"funnel": deepcopy(dict(funnel or {})), "backtest": deepcopy(dict(backtest or {}))}, diagnostics


def _git_value(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    return result.stdout.strip() or "UNKNOWN"


def _generator_evidence() -> dict[str, str]:
    status = _git_value("status", "--porcelain", "--untracked-files=all")
    return {
        "script": "scripts/lab/experiments/ai_setup_window_materializer.py",
        "commit": _git_value("rev-parse", "HEAD"),
        "branch": _git_value("branch", "--show-current"),
        "worktree_state": "CLEAN" if status == "" else "DIRTY",
    }


def materialize_windows(
    funnel_path: str | Path,
    backtest_path: str | Path,
    windows: Sequence[Window],
    output_path: str | Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    horizon_bars: int | None = None,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """Procesa ventanas secuencialmente y escribe JSONL + resumen auditable."""

    if not windows:
        raise SetupWindowError("WINDOWS_REQUIRED")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise SetupWindowError("BATCH_SIZE_INVALID")
    funnel = Path(funnel_path).resolve()
    backtest = Path(backtest_path).resolve()
    output = Path(output_path).resolve()
    summary = Path(summary_path).resolve() if summary_path else output.with_suffix(".summary.json")
    if output.exists() or summary.exists():
        raise SetupWindowError("OUTPUT_EXISTS_NO_OVERWRITE")
    if funnel == output or backtest == output or funnel == summary or backtest == summary:
        raise SetupWindowError("OUTPUT_MUST_BE_SEPARATE_FROM_INPUT")

    funnel_fields, funnel_diagnostics = _funnel_context(funnel)
    backtest_fields, backtest_diagnostics, discovered_horizon = _backtest_context(backtest)
    horizon = discovered_horizon if horizon_bars is None else _positive_int(horizon_bars, "horizon_bars")
    provenance, provenance_diagnostics = _provenance_context(funnel, backtest)
    diagnostics = list(funnel_diagnostics) + list(backtest_diagnostics) + list(provenance_diagnostics)
    counts = {"rows": 0, "rejected": 0, "windows": len(windows), "split": {}, "labels": {}}
    window_reports: list[dict[str, Any]] = []
    seen_episode_ids: set[str] = set()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for window in windows:
                result = materialize_window(funnel, backtest, window, horizon_bars=horizon)
                diagnostics.extend(result.diagnostics)
                counts["rejected"] += result.rejected_count
                pending: list[dict[str, Any]] = []
                for row in result.rows:
                    episode_id = str(row["episode_id"])
                    if episode_id in seen_episode_ids:
                        diagnostics.append(f"DUPLICATE_EPISODE_ACROSS_WINDOWS:{episode_id}")
                        counts["rejected"] += 1
                        continue
                    seen_episode_ids.add(episode_id)
                    pending.append(row)
                    if len(pending) >= batch_size:
                        for batched_row in pending:
                            stream.write(json.dumps(batched_row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                            counts["rows"] += 1
                            counts["split"][batched_row["split"]] = counts["split"].get(batched_row["split"], 0) + 1
                            counts["labels"][batched_row["label"]] = counts["labels"].get(batched_row["label"], 0) + 1
                        pending.clear()
                for batched_row in pending:
                    stream.write(json.dumps(batched_row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                    counts["rows"] += 1
                    counts["split"][batched_row["split"]] = counts["split"].get(batched_row["split"], 0) + 1
                    counts["labels"][batched_row["label"]] = counts["labels"].get(batched_row["label"], 0) + 1
                window_reports.append({
                    **window.to_dict(),
                    "rows": len(result.rows),
                    "rejected": result.rejected_count,
                    "diagnostics": list(result.diagnostics),
                })
            stream.flush()
        temporary.replace(output)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise

    if counts["rows"] == 0:
        diagnostics.append("NO_ROWS_MATERIALIZED")
    status = "PASS" if counts["rows"] > 0 and not diagnostics else "BLOCKED"
    result = {
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "materialization_status": "PASS" if counts["rows"] > 0 else "BLOCKED",
        "training_eligible": False,
        "can_trade": False,
        "promotion_authorized": False,
        "horizon_bars": horizon,
        "batch_size": batch_size,
        "windows": window_reports,
        "counts": counts,
        "diagnostics": sorted(set(diagnostics)),
        "split_policy": "registered temporal DESIGN/VALIDATION/HOLDOUT; no random split",
        "causality": {
            "decision_time_policy": "Funnel episode decision_time is the only feature timestamp",
            "outcome_policy": "canonical backtest trade outcome; future not copied into features_at_t",
            "future_features_exported": False,
            "mt5_used": False,
        },
        "provenance": {
            "status": "PASS" if not provenance_diagnostics else "BLOCKED",
            "sources": provenance,
            "blocking_reasons": sorted(set(provenance_diagnostics)),
        },
        "inputs": {
            "funnel": _sha256_file(funnel),
            "backtest": _sha256_file(backtest),
        },
        "output": _sha256_file(output),
        "generator": {**_generator_evidence(), "contract_version": CONTRACT_VERSION},
    }
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funnel", required=True, type=Path)
    parser.add_argument("--backtest", required=True, type=Path)
    parser.add_argument("--window", action="append", help="inclusive UTC START,END; may repeat")
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--horizon-bars", type=int)
    args = parser.parse_args(argv)
    try:
        specs = [parse_window_spec(value) for value in (args.window or [])]
        if args.window_start is not None or args.window_end is not None:
            if args.window_start is None or args.window_end is None:
                raise SetupWindowError("WINDOW_START_AND_END_REQUIRED_TOGETHER")
            specs.append(parse_window(args.window_start, args.window_end))
        result = materialize_windows(
            args.funnel, args.backtest, specs, args.output,
            batch_size=args.batch_size, horizon_bars=args.horizon_bars, summary_path=args.summary,
        )
    except (SetupWindowError, OSError) as exc:
        print(f"[AI_SETUP_WINDOW][BLOCKED] {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": result["status"],
        "output": str(args.output),
        "summary": str(args.summary or args.output.with_suffix(".summary.json")),
        "rows": result["counts"]["rows"],
        "horizon_bars": result["horizon_bars"],
        "can_trade": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


__all__ = [
    "CONTRACT_VERSION", "DEFAULT_BATCH_SIZE", "SetupWindowError", "Window",
    "WindowResult", "materialize_window", "materialize_windows", "parse_window",
    "parse_window_spec",
]


if __name__ == "__main__":
    raise SystemExit(main())
