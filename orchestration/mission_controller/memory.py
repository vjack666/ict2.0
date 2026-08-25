"""Optional Engram memory sink for durable mission closeouts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemorySaveResult:
    provider: str
    status: str
    project: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "project": self.project,
            "detail": self.detail,
        }


class EngramCliMemorySink:
    """Save a concise mission summary without making Engram the source of state."""

    def __init__(self, *, project: str = "ict2.0", executable: str = "engram", timeout: float = 15.0):
        self.project = project
        self.executable = executable
        self.timeout = timeout

    def save(self, mission: dict[str, Any]) -> MemorySaveResult:
        mission_id = str(mission.get("mission_id", "unknown"))
        title = f"ICT 2.0 mission closeout {mission_id}"
        content = json.dumps(
            {
                "mission_id": mission_id,
                "objective": mission.get("objective"),
                "status": mission.get("status"),
                "route": mission.get("route"),
                "decisions": mission.get("decisions", []),
                "evidence": mission.get("evidence", []),
                "completion_state": mission.get("completion_state", {}),
                "worklog_path": mission.get("worklog_path"),
            },
            ensure_ascii=False,
        )
        command = [
            self.executable, "save", title, content,
            "--type", "decision", "--project", self.project, "--scope", "project",
        ]
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True,
                timeout=self.timeout, shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return MemorySaveResult("engram", "UNAVAILABLE", self.project, "process_unavailable")
        if completed.returncode != 0:
            return MemorySaveResult("engram", "ERROR", self.project, f"exit_{completed.returncode}")
        return MemorySaveResult("engram", "RECORDED", self.project)
