"""Durable, atomic mission snapshots and append-only events."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"COMPLETE", "FAILED"}
VALID_STATUSES = {
    "PLAN", "DELEGATE", "EXECUTE", "OBSERVE", "VERIFY", "RECOVER",
    "WAITING_FOR_AGENT", "WAITING_FOR_TEST", "WAITING_FOR_REVIEW",
    "WAITING_FOR_EXTERNAL_REASONING", "ESCALATED", "COMPLETE", "FAILED",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionStore:
    """Persist mission state under a caller-provided directory.

    Tests and previews should pass a temporary directory. The production default
    is `.hermes-state/missions`, which is operational state rather than source code.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, mission_id: str) -> Path:
        if "/" in mission_id or "\\" in mission_id or mission_id in {".", ".."}:
            raise ValueError("invalid mission_id")
        return self.root / f"{mission_id}.json"

    def save(self, mission: dict[str, Any]) -> None:
        required = {"schema_version", "mission_id", "objective", "status", "phase", "tasks", "completion_state"}
        missing = required - mission.keys()
        if missing:
            raise ValueError(f"mission missing fields: {sorted(missing)}")
        if mission["status"] not in VALID_STATUSES:
            raise ValueError(f"invalid mission status: {mission['status']}")
        mission = dict(mission)
        mission["updated_at"] = _now()
        target = self.path_for(str(mission["mission_id"]))
        fd, temporary = tempfile.mkstemp(prefix=f".{target.stem}.", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(mission, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load(self, mission_id: str) -> dict[str, Any]:
        return json.loads(self.path_for(mission_id).read_text(encoding="utf-8"))

    def list_missions(self) -> tuple[str, ...]:
        """Return durable mission IDs in deterministic order."""
        return tuple(sorted(path.stem for path in self.root.glob("MC-*.json")))

    def append_event(self, mission_id: str, event: dict[str, Any]) -> None:
        event = dict(event)
        event.setdefault("timestamp", _now())
        event.setdefault("mission_id", mission_id)
        path = self.root / f"{mission_id}.events.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def transition(self, mission_id: str, status: str, *, event: dict[str, Any] | None = None) -> dict[str, Any]:
        mission = self.load(mission_id)
        if mission["status"] in TERMINAL_STATUSES:
            raise ValueError("terminal mission cannot transition")
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid mission status: {status}")
        mission["status"] = status
        self.save(mission)
        self.append_event(mission_id, {"type": "MISSION_STATUS", "status": status, **(event or {})})
        return mission
