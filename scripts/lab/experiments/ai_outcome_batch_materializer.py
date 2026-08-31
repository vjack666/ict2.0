"""LOCAL_ONLY materializador por particiones del Funnel de outcomes IA.

La utilidad consume dos artefactos ya serializados: un Episodes/Funnel y el
backtest canónico que lo respalda. No ejecuta el motor, no lee MT5 y no carga
los arrays JSON completos en memoria. Los arrays grandes se recorren elemento a
elemento; las velas se reducen a un índice de timestamps y los trades se
indexan en un SQLite temporal en disco. Cada lote se entrega al materializador
contractual existente para conservar sus validaciones causales y temporales.

La salida es deliberadamente técnica. Un resultado ``PASS`` de un lote no
autoriza entrenamiento ni trading: provenance, A7 y la autorización científica
siguen siendo gates independientes. Todas las filas conservan
``can_trade=false``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lab.experiments.ai_outcome_dataset import (  # noqa: E402
    materialize_outcome_rows,
)


CONTRACT_VERSION = "AI_OUTCOME_BATCH_MATERIALIZER_V1"
FUNNEL_CONTRACT_VERSION = "EPISODES_FUNNEL_V1"
VISUAL_BACKTEST_SCHEMA_VERSION = "1.0"
DEFAULT_BATCH_SIZE = 256
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
_DIRECTION_ALIASES = {
    "BULLISH": 1,
    "BULL": 1,
    "LONG": 1,
    "BEARISH": -1,
    "BEAR": -1,
    "SHORT": -1,
}


class BatchMaterializationError(ValueError):
    """Entrada inválida o evidencia insuficiente para particionar."""


class _CharStream:
    """Lector de texto con buffer acotado y posición lógica."""

    def __init__(self, handle, *, chunk_size: int = 1024 * 1024) -> None:
        self.handle = handle
        self.chunk_size = chunk_size
        self.buffer = ""
        self.position = 0

    def read(self, size: int | None = None) -> str:
        target = self.chunk_size if size is None else max(1, size)
        pieces: list[str] = []
        remaining = target
        while remaining > 0:
            if self.position < len(self.buffer):
                take = min(remaining, len(self.buffer) - self.position)
                pieces.append(self.buffer[self.position : self.position + take])
                self.position += take
                remaining -= take
                continue
            chunk = self.handle.read(max(self.chunk_size, remaining))
            if not chunk:
                break
            self.buffer = chunk
            self.position = 0
        return "".join(pieces)

    def read_char(self) -> str:
        value = self.read(1)
        return value


def _decode_string(chars: Sequence[str]) -> str:
    try:
        return json.loads('"' + "".join(chars) + '"')
    except json.JSONDecodeError as exc:
        raise BatchMaterializationError("JSON_PROPERTY_NAME_INVALID") from exc


def _locate_top_level_value(path: Path, field: str) -> tuple[_CharStream, str]:
    """Locate a top-level JSON value without parsing unrelated arrays."""

    if not field or '"' in field:
        raise BatchMaterializationError("JSON_FIELD_INVALID")
    handle = path.open("r", encoding="utf-8", newline="")
    stream = _CharStream(handle)
    depth = 0
    in_string = False
    escaped = False
    string_chars: list[str] = []
    string_is_key = False
    pending_key: str | None = None
    expecting_value = False

    try:
        while True:
            char = stream.read_char()
            if not char:
                break
            if in_string:
                if escaped:
                    string_chars.append(char)
                    escaped = False
                elif char == "\\":
                    string_chars.append(char)
                    escaped = True
                elif char == '"':
                    in_string = False
                    if string_is_key:
                        pending_key = _decode_string(string_chars)
                else:
                    string_chars.append(char)
                continue

            if char == '"':
                if expecting_value:
                    if pending_key == field:
                        expecting_value = False
                        return stream, char
                    expecting_value = False
                    pending_key = None
                in_string = True
                escaped = False
                string_chars = []
                string_is_key = depth == 1 and not expecting_value
                continue
            if char == "{":
                if expecting_value and pending_key == field:
                    expecting_value = False
                    return stream, char
                depth += 1
                if expecting_value:
                    expecting_value = False
                    pending_key = None
                continue
            if char == "}":
                depth -= 1
                continue
            if char == ":" and depth == 1 and pending_key is not None:
                expecting_value = True
                continue
            if expecting_value:
                if char.isspace():
                    continue
                expecting_value = False
                if pending_key == field:
                    return stream, char
                pending_key = None
            if char == "," and depth == 1:
                pending_key = None
    except BaseException:
        handle.close()
        raise

    handle.close()
    raise BatchMaterializationError(f"JSON_FIELD_MISSING:{field}:{path}")


def _iter_json_array(path: Path, field: str) -> Iterator[Mapping[str, Any]]:
    """Yield array objects incrementally using only the standard library."""

    stream, opening = _locate_top_level_value(path, field)
    if opening != "[":
        stream.handle.close()
        raise BatchMaterializationError(f"JSON_FIELD_NOT_ARRAY:{field}")

    decoder = json.JSONDecoder()
    buffer = ""
    first = True
    try:
        while True:
            while True:
                buffer = buffer.lstrip()
                if buffer:
                    break
                buffer = stream.read()
                if not buffer:
                    raise BatchMaterializationError(f"JSON_ARRAY_UNTERMINATED:{field}")
            if not first:
                if buffer[0] == ",":
                    buffer = buffer[1:]
                    continue
            if buffer[0] == "]":
                return

            while True:
                buffer = buffer.lstrip()
                try:
                    value, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    more = stream.read()
                    if not more:
                        raise BatchMaterializationError(f"JSON_ARRAY_ITEM_INVALID:{field}")
                    buffer += more
                    continue
                buffer = buffer[end:]
                first = False
                if not isinstance(value, Mapping):
                    raise BatchMaterializationError(f"JSON_ARRAY_ITEM_NOT_OBJECT:{field}")
                yield value
                break
    finally:
        stream.handle.close()


def _read_top_level_value(path: Path, field: str) -> Any:
    stream, first = _locate_top_level_value(path, field)
    decoder = json.JSONDecoder()
    buffer = first + stream.read()
    try:
        while True:
            try:
                value, _ = decoder.raw_decode(buffer.lstrip())
                return value
            except json.JSONDecodeError:
                more = stream.read()
                if not more:
                    raise BatchMaterializationError(f"JSON_VALUE_INVALID:{field}")
                buffer += more
    finally:
        stream.handle.close()


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise BatchMaterializationError(f"{field}_INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise BatchMaterializationError(f"{field}_INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any, field: str) -> str:
    return _utc(value, field).isoformat()


def _direction(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise BatchMaterializationError(f"{field}_INVALID_DIRECTION")
    if isinstance(value, (int, float)) and int(value) in (-1, 1) and float(value) == int(value):
        return int(value)
    if isinstance(value, str):
        raw = value.strip().upper()
        if raw in _DIRECTION_ALIASES:
            return _DIRECTION_ALIASES[raw]
        try:
            parsed = int(raw)
        except ValueError:
            parsed = 0
        if parsed in (-1, 1):
            return parsed
    raise BatchMaterializationError(f"{field}_INVALID_DIRECTION")


def _file_evidence(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def _git_value(*args: str) -> str:
    try:
        value = subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    return value or "UNKNOWN"


def _generator_evidence() -> dict[str, str]:
    status = _git_value("status", "--porcelain", "--untracked-files=all")
    return {
        "script": "scripts/lab/experiments/ai_outcome_batch_materializer.py",
        "commit": _git_value("rev-parse", "HEAD"),
        "branch": _git_value("branch", "--show-current"),
        "worktree_state": "CLEAN" if not status else "DIRTY",
    }


def _header(path: Path, fields: Iterable[str]) -> dict[str, Any]:
    return {field: _read_top_level_value(path, field) for field in fields}


def _validate_funnel_header(funnel: Mapping[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    if funnel.get("contract_version") != FUNNEL_CONTRACT_VERSION:
        diagnostics.append("FUNNEL_CONTRACT_MISMATCH")
    if funnel.get("aggregated_status") != "PASS":
        diagnostics.append(f"FUNNEL_STATUS_{funnel.get('aggregated_status', 'MISSING')}")
    gates = funnel.get("gates")
    if not isinstance(gates, Mapping) or not gates:
        diagnostics.append("FUNNEL_GATES_MISSING")
    elif any(value != "PASS" for value in gates.values()):
        diagnostics.append("FUNNEL_CAUSAL_GATES_NOT_PASS")
    prefix = funnel.get("full_prefix")
    if not isinstance(prefix, Mapping) or prefix.get("prefix_matches_full") is not True:
        diagnostics.append("FUNNEL_FULL_PREFIX_NOT_PROVEN")
    commit = funnel.get("generator_commit")
    if not isinstance(commit, str) or not _HEX_COMMIT.fullmatch(commit):
        diagnostics.append("FUNNEL_GENERATOR_COMMIT_MISSING_OR_INVALID")
    provenance = funnel.get("provenance")
    if not isinstance(provenance, Mapping) or not provenance:
        diagnostics.append("FUNNEL_PROVENANCE_MISSING")
    elif provenance.get("status") != "PASS":
        diagnostics.append("FUNNEL_PROVENANCE_NOT_PASS")
    return diagnostics


def _validate_backtest_header(backtest: Mapping[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    if backtest.get("schema_version") != VISUAL_BACKTEST_SCHEMA_VERSION:
        diagnostics.append("BACKTEST_SCHEMA_MISMATCH")
    metadata = backtest.get("metadata")
    if not isinstance(metadata, Mapping):
        diagnostics.append("BACKTEST_METADATA_MISSING")
        return diagnostics
    if metadata.get("causal") is not True:
        diagnostics.append("BACKTEST_CAUSAL_METADATA_MISSING")
    if metadata.get("legacy_backtest") is not False:
        diagnostics.append("BACKTEST_LEGACY_BOUNDARY_UNPROVEN")
    if metadata.get("promotion_authorized") is not False:
        diagnostics.append("BACKTEST_PROMOTION_BOUNDARY_UNPROVEN")
    provenance = metadata.get("provenance")
    if provenance is not None and isinstance(provenance, Mapping) and provenance.get("status") != "PASS":
        diagnostics.append("BACKTEST_PROVENANCE_NOT_PASS")
    return diagnostics


def _load_horizon(metadata: Mapping[str, Any]) -> int:
    outcome = metadata.get("outcome")
    value = outcome.get("horizon_bars") if isinstance(outcome, Mapping) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise BatchMaterializationError("BACKTEST_HORIZON_MISSING_OR_INVALID")
    return value


def _read_candle_times(path: Path) -> tuple[list[str], list[str]]:
    times: list[str] = []
    diagnostics: list[str] = []
    previous: datetime | None = None
    for expected_index, candle in enumerate(_iter_json_array(path, "candles")):
        if candle.get("index") != expected_index:
            raise BatchMaterializationError("BACKTEST_CANDLE_INDEX_NOT_CONTIGUOUS")
        current = _utc(candle.get("time"), f"candles[{expected_index}].time")
        if previous is not None and current <= previous:
            raise BatchMaterializationError("BACKTEST_CANDLE_TIMES_NOT_STRICTLY_INCREASING")
        times.append(current.isoformat())
        previous = current
    if not times:
        raise BatchMaterializationError("BACKTEST_CANDLES_EMPTY")
    return times, diagnostics


def _validate_events(path: Path, candle_count: int) -> int:
    event_ids: set[str] = set()
    for index, event in enumerate(_iter_json_array(path, "events")):
        event_id = str(event.get("id", ""))
        if not event_id or event_id in event_ids:
            raise BatchMaterializationError(f"BACKTEST_EVENT_ID_INVALID_OR_DUPLICATE:{index}")
        event_ids.add(event_id)
        try:
            event_index = int(event["index"])
            confirmed = int(event["confirmed_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BatchMaterializationError(f"BACKTEST_EVENT_INDEX_INVALID:{event_id}") from exc
        if not 0 <= event_index < candle_count or not 0 <= confirmed < candle_count:
            raise BatchMaterializationError(f"BACKTEST_EVENT_OUTSIDE_CANDLE_RANGE:{event_id}")
        if confirmed < event_index:
            raise BatchMaterializationError(f"BACKTEST_EVENT_CONFIRMATION_PRECEDES_EVENT:{event_id}")
        parent_id = event.get("parent_id")
        if parent_id is not None and parent_id not in event_ids:
            raise BatchMaterializationError(f"BACKTEST_EVENT_PARENT_NOT_PRECEDING:{event_id}")
    return len(event_ids)


def _build_trade_index(path: Path, times: Sequence[str], database: Path) -> tuple[int, list[str]]:
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute(
            "CREATE TABLE trades (entry_time TEXT NOT NULL, direction INTEGER NOT NULL, payload TEXT NOT NULL)"
        )
        connection.execute("CREATE INDEX trades_key ON trades(entry_time, direction)")
        malformed: list[str] = []
        count = 0
        for index, trade in enumerate(_iter_json_array(path, "trades")):
            try:
                entry_time = _iso(trade.get("entry_time"), f"trades[{index}].entry_time")
                direction = _direction(trade.get("direction"), f"trades[{index}].direction")
                entry_index = trade.get("entry_index")
                if isinstance(entry_index, bool) or not isinstance(entry_index, int):
                    raise BatchMaterializationError("ENTRY_INDEX_INVALID")
                if not 0 <= entry_index < len(times) or times[entry_index] != entry_time:
                    raise BatchMaterializationError("ENTRY_INDEX_TIME_MISMATCH")
                payload = json.dumps(dict(trade), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                connection.execute(
                    "INSERT INTO trades(entry_time, direction, payload) VALUES (?, ?, ?)",
                    (entry_time, direction, payload),
                )
                count += 1
            except BatchMaterializationError as exc:
                malformed.append(f"BACKTEST_TRADE_INVALID:{index}:{exc}")
        connection.commit()
        return count, malformed
    finally:
        connection.close()


def _partition_key(value: datetime, mode: str) -> str:
    if mode == "year":
        return f"{value.year:04d}"
    if mode == "quarter":
        return f"{value.year:04d}-Q{((value.month - 1) // 3) + 1}"
    if mode == "month":
        return f"{value.year:04d}-{value.month:02d}"
    raise BatchMaterializationError(f"PARTITION_MODE_INVALID:{mode}")


def _query_trades(connection: sqlite3.Connection, episode: Mapping[str, Any]) -> list[dict[str, Any]]:
    event_time = _iso(episode.get("decision_time"), "episode.decision_time")
    direction = _direction(episode.get("direction"), "episode.direction")
    rows = connection.execute(
        "SELECT payload FROM trades WHERE entry_time = ? AND direction = ? ORDER BY rowid",
        (event_time, direction),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]


def _batch_backtest(
    template: Mapping[str, Any],
    batch: Sequence[Mapping[str, Any]],
    *,
    connection: sqlite3.Connection,
    times: Sequence[str],
    horizon: int,
) -> dict[str, Any]:
    selected: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    indexes: list[int] = []
    for episode in batch:
        matches = _query_trades(connection, episode)
        for match in matches:
            if isinstance(match.get("entry_index"), int):
                indexes.append(int(match["entry_index"]))
                selected.append((episode, match))

    if indexes:
        base = min(indexes)
        last = min(len(times) - 1, max(index + horizon for index in indexes))
        if base < 0 or base > last:
            raise BatchMaterializationError("BATCH_CANDLE_SLICE_INVALID")
        candles = [
            {"index": index - base, "time": times[index]}
            for index in range(base, last + 1)
        ]
    else:
        base = 0
        candles = []

    trades: list[dict[str, Any]] = []
    for _, trade in selected:
        current = deepcopy(trade)
        current["entry_index"] = int(current["entry_index"]) - base
        if isinstance(current.get("exit_index"), int):
            current["exit_index"] = int(current["exit_index"]) - base
        trades.append(current)

    return {
        "schema_version": VISUAL_BACKTEST_SCHEMA_VERSION,
        "symbol": template.get("symbol", ""),
        "timeframe": template.get("timeframe", ""),
        "candles": candles,
        "events": [],
        "trades": trades,
        "metadata": deepcopy(dict(template["metadata"])),
    }


def _batch_funnel(template: Mapping[str, Any], batch: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    payload = deepcopy(dict(template))
    payload["episodes"] = [deepcopy(dict(item)) for item in batch]
    return payload


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    lines = [
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        for row in rows
    ]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def _write_new(path: Path, data: bytes) -> str:
    if path.exists():
        raise BatchMaterializationError(f"OUTPUT_EXISTS:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        body = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return digest.hexdigest()


def _load_optional_json(path: Path | None, field: str) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchMaterializationError(f"{field}_JSON_INVALID:{path}") from exc
    if not isinstance(payload, Mapping):
        raise BatchMaterializationError(f"{field}_JSON_NOT_OBJECT:{path}")
    return dict(payload)


def materialize_in_batches(
    *,
    funnel_path: str | Path,
    backtest_path: str | Path,
    output_dir: str | Path,
    a7_report_path: str | Path | None = None,
    research_gate_path: str | Path | None = None,
    partition: str = "month",
    max_episodes_per_batch: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Materializa lotes temporales sin cargar los artefactos completos."""

    if partition not in {"month", "quarter", "year"}:
        raise BatchMaterializationError(f"PARTITION_MODE_INVALID:{partition}")
    if isinstance(max_episodes_per_batch, bool) or not isinstance(max_episodes_per_batch, int) or max_episodes_per_batch < 1:
        raise BatchMaterializationError("BATCH_SIZE_INVALID")

    funnel = Path(funnel_path).resolve()
    backtest = Path(backtest_path).resolve()
    output = Path(output_dir).resolve()
    if not funnel.is_file() or not backtest.is_file():
        raise BatchMaterializationError("INPUT_ARTIFACT_MISSING")
    if output.exists():
        raise BatchMaterializationError(f"OUTPUT_EXISTS:{output}")

    funnel_header = _header(
        funnel,
        ("contract_version", "aggregated_status", "gates", "full_prefix", "generator_commit", "provenance"),
    )
    backtest_header = _header(backtest, ("schema_version", "symbol", "timeframe", "metadata"))
    diagnostics = _validate_funnel_header(funnel_header)
    diagnostics.extend(_validate_backtest_header(backtest_header))
    metadata = backtest_header.get("metadata")
    if not isinstance(metadata, Mapping):
        raise BatchMaterializationError("BACKTEST_METADATA_MISSING")
    horizon = _load_horizon(metadata)

    a7_report = _load_optional_json(Path(a7_report_path).resolve() if a7_report_path else None, "A7_REPORT")
    research_gate = _load_optional_json(
        Path(research_gate_path).resolve() if research_gate_path else None,
        "RESEARCH_GATE",
    )
    input_evidence = {
        "funnel": _file_evidence(funnel),
        "backtest": _file_evidence(backtest),
    }
    if a7_report_path:
        input_evidence["a7_report"] = _file_evidence(Path(a7_report_path).resolve())
    if research_gate_path:
        input_evidence["research_gate"] = _file_evidence(Path(research_gate_path).resolve())

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    try:
        partitions_root = staging / "partitions"
        diagnostics_path = staging / "diagnostics.jsonl"
        times, _ = _read_candle_times(backtest)
        event_count = _validate_events(backtest, len(times))
        database = staging / "trade_index.sqlite3"
        trade_count, trade_diagnostics = _build_trade_index(backtest, times, database)
        diagnostics.extend(trade_diagnostics)

        funnel_template = dict(funnel_header)
        batches_by_partition: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        batch_numbers: Counter[str] = Counter()
        manifest_batches: list[dict[str, Any]] = []
        split_counts: Counter[str] = Counter()
        total_episodes = 0
        total_rows = 0

        with diagnostics_path.open("w", encoding="utf-8", newline="\n") as diagnostic_handle:
            def record_diagnostics(partition_name: str, batch_number: int, values: Iterable[str]) -> None:
                for value in values:
                    diagnostic_handle.write(
                        json.dumps(
                            {"partition": partition_name, "batch": batch_number, "diagnostic": value},
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )

            with closing(sqlite3.connect(database)) as connection:
                for episode in _iter_json_array(funnel, "episodes"):
                    if episode.get("status") != "ACCEPTED":
                        diagnostics.append(f"EPISODE_NOT_ACCEPTED:{episode.get('episode_id', '')}")
                        continue
                    episode_id = str(episode.get("episode_id", ""))
                    if not episode_id:
                        diagnostics.append("EPISODE_ID_MISSING")
                        continue
                    decision = _utc(episode.get("decision_time"), f"episode[{episode_id}].decision_time")
                    key = _partition_key(decision, partition)
                    batches_by_partition[key].append(dict(episode))
                    total_episodes += 1
                    if len(batches_by_partition[key]) < max_episodes_per_batch:
                        continue

                    batch = batches_by_partition[key]
                    batches_by_partition[key] = []
                    batch_numbers[key] += 1
                    result = materialize_outcome_rows(
                        _batch_funnel(funnel_template, batch),
                        _batch_backtest(
                            backtest_header,
                            batch,
                            connection=connection,
                            times=times,
                            horizon=horizon,
                        ),
                        a7_report=a7_report,
                        research_gate=research_gate,
                    )
                    relative = Path("partitions") / key / f"batch_{batch_numbers[key]:05d}.jsonl"
                    body = _jsonl_bytes(result.rows)
                    digest = _write_new(staging / relative, body)
                    record_diagnostics(key, batch_numbers[key], result.diagnostics)
                    total_rows += len(result.rows)
                    for row in result.rows:
                        split_counts[str(row["split"])] += 1
                    manifest_batches.append({
                        "partition": key,
                        "batch": batch_numbers[key],
                        "episodes": len(batch),
                        "rows": len(result.rows),
                        "status": result.status,
                        "training_eligible": result.training_eligible,
                        "diagnostic_count": len(result.diagnostics),
                        "rows_sha256": digest,
                        "path": relative.as_posix(),
                    })

                for key in sorted(batches_by_partition):
                    batch = batches_by_partition[key]
                    if not batch:
                        continue
                    batch_numbers[key] += 1
                    result = materialize_outcome_rows(
                        _batch_funnel(funnel_template, batch),
                        _batch_backtest(
                            backtest_header,
                            batch,
                            connection=connection,
                            times=times,
                            horizon=horizon,
                        ),
                        a7_report=a7_report,
                        research_gate=research_gate,
                    )
                    relative = Path("partitions") / key / f"batch_{batch_numbers[key]:05d}.jsonl"
                    body = _jsonl_bytes(result.rows)
                    digest = _write_new(staging / relative, body)
                    record_diagnostics(key, batch_numbers[key], result.diagnostics)
                    total_rows += len(result.rows)
                    for row in result.rows:
                        split_counts[str(row["split"])] += 1
                    manifest_batches.append({
                        "partition": key,
                        "batch": batch_numbers[key],
                        "episodes": len(batch),
                        "rows": len(result.rows),
                        "status": result.status,
                        "training_eligible": result.training_eligible,
                        "diagnostic_count": len(result.diagnostics),
                        "rows_sha256": digest,
                        "path": relative.as_posix(),
                    })

        if not manifest_batches:
            diagnostics.append("NO_EPISODE_BATCHES")

        manifest_batches.sort(key=lambda item: (item["partition"], item["batch"]))
        if diagnostics_path.exists():
            with diagnostics_path.open("r", encoding="utf-8") as diagnostic_reader:
                diagnostics_count = sum(1 for _ in diagnostic_reader)
        else:
            diagnostics_count = 0
        if diagnostics:
            record = diagnostics_path.open("a", encoding="utf-8", newline="\n")
            try:
                for value in diagnostics:
                    record.write(json.dumps({"partition": "_global", "batch": 0, "diagnostic": value}, ensure_ascii=False, sort_keys=True) + "\n")
            finally:
                record.close()
            diagnostics_count += len(diagnostics)

        all_batches_clean = bool(manifest_batches) and all(
            item["status"] == "PASS" and item["training_eligible"] for item in manifest_batches
        )
        status = "PASS" if all_batches_clean and not diagnostics else "BLOCKED"
        manifest = {
            "contract_version": CONTRACT_VERSION,
            "status": status,
            "training_eligible": status == "PASS",
            "can_trade": False,
            "local_only": True,
            "source_artifacts": input_evidence,
            "source_contracts": {
                "funnel": FUNNEL_CONTRACT_VERSION,
                "backtest": VISUAL_BACKTEST_SCHEMA_VERSION,
                "materializer": "scripts/lab/experiments/ai_outcome_dataset.py",
            },
            "partitioning": {
                "mode": partition,
                "max_episodes_per_batch": max_episodes_per_batch,
                "source_arrays_streamed": ["candles", "events", "trades", "episodes"],
                "memory_model": "compact candle timestamp index + temporary on-disk SQLite trade index + bounded episode batch",
                "full_backtest_arrays_loaded": False,
            },
            "causality": {
                "features_source": "Funnel episode.features_at_t",
                "labels_source": "canonical backtest trade outcome",
                "future_features_exported": False,
                "outcome_horizon_bars": horizon,
                "no_replay_or_relabel": True,
            },
            "temporal_splits": {
                "policy": "ai_outcome_dataset.REGISTERED_SPLIT_BLOCKS",
                "counts": dict(sorted(split_counts.items())),
                "no_random_shuffle": True,
            },
            "counts": {
                "candles_indexed": len(times),
                "events_validated": event_count,
                "trades_indexed": trade_count,
                "episodes_seen_accepted": total_episodes,
                "batches": len(manifest_batches),
                "rows": total_rows,
                "diagnostics": diagnostics_count,
            },
            "batches": manifest_batches,
            "diagnostics_path": "diagnostics.jsonl",
            "dataset_hash": _hash_tree(staging / "partitions"),
            "generator": _generator_evidence(),
            "next_action": "Resolver provenance/A7/research_gate y ampliar volumen antes de ejecutar ai_outcome_train.py." if status != "PASS" else "Auditar el manifest y pasar por el runner de entrenamiento en Shadow Mode.",
        }
        _write_new(staging / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        if database.exists():
            database.unlink()
        staging.replace(output)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _parser():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funnel", required=True, type=Path)
    parser.add_argument("--backtest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--a7-report", type=Path)
    parser.add_argument("--research-gate", type=Path)
    parser.add_argument("--partition", choices=("month", "quarter", "year"), default="month")
    parser.add_argument("--max-episodes-per-batch", type=int, default=DEFAULT_BATCH_SIZE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = materialize_in_batches(
            funnel_path=args.funnel,
            backtest_path=args.backtest,
            output_dir=args.output,
            a7_report_path=args.a7_report,
            research_gate_path=args.research_gate,
            partition=args.partition,
            max_episodes_per_batch=args.max_episodes_per_batch,
        )
    except (BatchMaterializationError, OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "status": manifest["status"],
        "training_eligible": manifest["training_eligible"],
        "output": str(args.output),
        "counts": manifest["counts"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 2


__all__ = ["BatchMaterializationError", "materialize_in_batches"]


if __name__ == "__main__":
    raise SystemExit(main())
