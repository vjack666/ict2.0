"""Append-only local audit trail for the mechanical MT5 boundary.

The journal deliberately records *before* an order reaches ``order_send``.
If that durable write cannot be made, the caller must fail closed and no
broker request is sent.  It is local evidence, not a trading signal source.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping


class BlackBoxWriteError(RuntimeError):
    """Raised when the required pre-send audit evidence cannot be persisted."""


def canonical_hash(value: Any) -> str:
    """Hash the complete canonical input; record retention is handled separately."""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BlackBoxJournal:
    """Synchronous JSONL journal with bounded records and size rotation.

    ``record`` fsyncs every entry.  This is intentionally conservative: the
    mechanical bot has a 15-second tick and audit durability matters more than
    throughput.  Each file has a hash chain so an operator can detect missing
    or altered entries within that file.
    """

    def __init__(self, path: Path, *, max_bytes: int = 5_000_000, backups: int = 3, max_record_bytes: int = 32_000):
        if max_bytes < 100_000 or backups < 1 or max_record_bytes < 1_000:
            raise ValueError("invalid black-box retention limits")
        self.path = Path(path)
        self.max_bytes = int(max_bytes)
        self.backups = int(backups)
        self.max_record_bytes = int(max_record_bytes)
        self._lock = RLock()
        self._previous_hash = self._load_last_hash()

    def record(self, event: str, /, **fields: Any) -> dict[str, Any]:
        if not isinstance(event, str) or not event:
            raise ValueError("black-box event is required")
        with self._lock:
            try:
                body = {
                    "schema_version": 1,
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": event,
                    "previous_hash": self._previous_hash,
                    **_bounded(fields),
                }
                body["record_hash"] = canonical_hash(body)
                line = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str) + "\n"
                if len(line.encode("utf-8")) > self.max_record_bytes:
                    raise BlackBoxWriteError("black-box record exceeds bounded size")
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate_if_needed(len(line.encode("utf-8")))
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
                self._previous_hash = body["record_hash"]
                return body
            except BlackBoxWriteError:
                raise
            except (OSError, TypeError, ValueError) as exc:
                raise BlackBoxWriteError(f"black-box persistence failed: {exc}") from exc

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return a bounded, malformed-line-tolerant summary for the local UI."""
        limit = max(0, min(int(limit), 100))
        if limit == 0 or not self.path.exists():
            return []
        try:
            # The UI polls every second.  Reading only the end avoids loading a
            # rotated-at-5MB journal on each status request.
            with self.path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - 131_072))
                text = handle.read().decode("utf-8", errors="replace")
            lines = text.splitlines()[-limit:]
        except OSError:
            return []
        entries: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                entries.append({key: item.get(key) for key in ("time", "event", "correlation_id", "reason", "outcome", "error", "request_hash", "record_hash") if key in item})
        return entries

    def summary(self) -> dict[str, Any]:
        return {"path": str(self.path), "tail": self.tail(12), "max_bytes": self.max_bytes, "backups": self.backups}

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        try:
            current_size = self.path.stat().st_size
        except FileNotFoundError:
            return
        if current_size + incoming_bytes <= self.max_bytes:
            return
        for index in range(self.backups, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            target = self.path.with_name(f"{self.path.name}.{index + 1}")
            if source.exists():
                if index == self.backups:
                    source.unlink()
                else:
                    source.replace(target)
        self.path.replace(self.path.with_name(f"{self.path.name}.1"))
        self._previous_hash = None

    def _load_last_hash(self) -> str | None:
        try:
            last_line = self.path.read_text(encoding="utf-8").splitlines()[-1]
            value = json.loads(last_line).get("record_hash")
            return value if isinstance(value, str) else None
        except (OSError, ValueError, IndexError, AttributeError):
            return None


def _bounded(value: Any, *, depth: int = 0) -> Any:
    """Keep audit records JSON-safe and bounded without hiding request facts."""
    if depth >= 5:
        return "<depth-limited>"
    if isinstance(value, Mapping):
        return {str(key)[:128]: _bounded(item, depth=depth + 1) for key, item in list(value.items())[:100]}
    if isinstance(value, (list, tuple, set)):
        return [_bounded(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, str):
        return value[:4_000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if hasattr(value, "_asdict"):
        return _bounded(value._asdict(), depth=depth + 1)
    if hasattr(value, "__dict__"):
        return _bounded(vars(value), depth=depth + 1)
    return str(value)[:4_000]


__all__ = ["BlackBoxJournal", "BlackBoxWriteError", "canonical_hash"]
