"""Provider adapter for OpenCode's non-interactive CLI.

The adapter is deliberately opt-in for process execution. Mission planning can
construct a valid delegation without launching a provider. A real process is
started only when ``allow_process=True`` is passed by an authorized controller.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .agent_registry import AgentDescriptor, AgentRegistryResolver


class AdapterCapabilityError(RuntimeError):
    """The selected provider mode cannot support the requested operation."""


@dataclass(frozen=True)
class SessionRef:
    session_id: str
    agent_key: str
    title: str
    mission_id: str
    task_id: str


@dataclass(frozen=True)
class DelegationRef:
    delegation_id: str
    session_id: str
    status: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class ProviderEvent:
    """Normalized event extracted from OpenCode JSON output."""

    event_type: str
    status: str | None
    provider_session_id: str | None
    payload: dict


@dataclass
class _ProcessRecord:
    process: subprocess.Popen[str]
    command: tuple[str, ...]
    started_at: float
    stdout_path: Path
    stderr_path: Path
    delegation_id: str


class OpenCodeCliAdapter:
    """A small, testable adapter around ``opencode run``."""

    def __init__(
        self,
        *,
        workspace: Path | str,
        registry: AgentRegistryResolver,
        executable: str = "opencode",
        state_dir: Path | str | None = None,
        allow_process: bool = False,
    ):
        self.workspace = Path(workspace)
        self.registry = registry
        self.executable = executable
        self.state_dir = Path(state_dir or self.workspace / ".hermes-state" / "delegations")
        self.allow_process = allow_process
        self._sessions: dict[str, SessionRef] = {}
        self._processes: dict[str, _ProcessRecord] = {}
        self._provider_session_ids: dict[str, str] = {}

    def list_agents(self) -> tuple[AgentDescriptor, ...]:
        return self.registry.list_agents()

    def create_session(self, agent: str, title: str, mission_id: str, task_id: str) -> SessionRef:
        self.registry.resolve(agent)
        if not title.strip() or not mission_id.strip() or not task_id.strip():
            raise ValueError("title, mission_id and task_id must not be empty")
        session = SessionRef(
            session_id=f"local-{uuid4().hex}",
            agent_key=agent,
            title=title,
            mission_id=mission_id,
            task_id=task_id,
        )
        self._sessions[session.session_id] = session
        return session

    def delegate(self, session: SessionRef, prompt: str, mode: str = "run") -> DelegationRef:
        self._require_contract_fields(session, prompt)
        if mode != "run":
            raise AdapterCapabilityError(f"unsupported OpenCode CLI mode: {mode}")
        command = (
            self.executable,
            "run",
            "--agent", session.agent_key,
            "--title", session.title,
            "--format", "json",
            "--dir", str(self.workspace),
            prompt,
        )
        delegation_id = f"delegation-{uuid4().hex}"
        if not self.allow_process:
            return DelegationRef(delegation_id, session.session_id, "PLANNED", command)

        self._launch(session, delegation_id, command)
        return DelegationRef(delegation_id, session.session_id, "RUNNING", command)

    def get_session_status(self, session: SessionRef) -> dict:
        record = self._processes.get(session.session_id)
        if record is None:
            return {
                "session_id": session.session_id,
                "provider_session_id": self._provider_session_ids.get(session.session_id),
                "status": "PLANNED",
            }
        events = self.read_events(session)
        returncode = record.process.poll()
        status = "RUNNING" if returncode is None else ("COMPLETED" if returncode == 0 else "FAILED")
        if any(event.status in {"error", "failed"} for event in events):
            status = "FAILED"
        return {
            "session_id": session.session_id,
            "provider_session_id": self._provider_session_ids.get(session.session_id),
            "delegation_id": record.delegation_id,
            "status": status,
            "returncode": returncode,
            "stdout_path": str(record.stdout_path),
            "stderr_path": str(record.stderr_path),
        }

    def get_session_children(self, session: SessionRef) -> tuple[SessionRef, ...]:
        return tuple(child for child in self._sessions.values() if child.session_id != session.session_id and child.mission_id == session.mission_id)

    def resume(self, session: SessionRef, prompt: str) -> DelegationRef:
        self._require_contract_fields(session, prompt)
        provider_session_id = self._provider_session_ids.get(session.session_id)
        if not provider_session_id:
            self.read_events(session)
            provider_session_id = self._provider_session_ids.get(session.session_id)
        if not provider_session_id:
            raise AdapterCapabilityError(
                "resume requires a provider session id from OpenCode events; local CLI refs cannot be resumed safely"
            )
        command = (
            self.executable, "run", "--session", provider_session_id,
            "--format", "json", "--dir", str(self.workspace), prompt,
        )
        delegation_id = f"delegation-{uuid4().hex}"
        if not self.allow_process:
            return DelegationRef(delegation_id, session.session_id, "PLANNED", command)
        self._launch(session, delegation_id, command)
        return DelegationRef(delegation_id, session.session_id, "RUNNING", command)

    def subscribe_events(self) -> tuple[ProviderEvent, ...]:
        events: list[ProviderEvent] = []
        for session in self._sessions.values():
            events.extend(self.read_events(session))
        return tuple(events)

    def read_events(self, session: SessionRef) -> tuple[ProviderEvent, ...]:
        """Read and normalize all complete JSON events currently persisted."""
        record = self._processes.get(session.session_id)
        if record is None or not record.stdout_path.is_file():
            return ()
        events: list[ProviderEvent] = []
        for line in record.stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event = self._normalize_event(payload)
            events.append(event)
            if event.provider_session_id:
                self._provider_session_ids[session.session_id] = event.provider_session_id
        return tuple(events)

    def _launch(self, session: SessionRef, delegation_id: str, command: tuple[str, ...]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = self.state_dir / f"{delegation_id}.stdout.jsonl"
        stderr_path = self.state_dir / f"{delegation_id}.stderr.log"
        stdout = stdout_path.open("w", encoding="utf-8")
        stderr = stderr_path.open("w", encoding="utf-8")
        try:
            process = subprocess.Popen(
                list(command), cwd=self.workspace, stdout=stdout, stderr=stderr,
                text=True, shell=False,
            )
        finally:
            stdout.close()
            stderr.close()
        self._processes[session.session_id] = _ProcessRecord(
            process=process, command=command, started_at=monotonic(),
            stdout_path=stdout_path, stderr_path=stderr_path,
            delegation_id=delegation_id,
        )

    @staticmethod
    def _normalize_event(payload: dict) -> ProviderEvent:
        event_type = str(payload.get("type") or payload.get("event") or payload.get("kind") or "unknown")
        status_value = payload.get("status")
        if isinstance(status_value, dict):
            status_value = status_value.get("type") or status_value.get("status")
        status = str(status_value).casefold() if status_value is not None else None
        provider_session_id = OpenCodeCliAdapter._find_value(
            payload, ("sessionID", "sessionId", "session_id", "provider_session_id")
        )
        return ProviderEvent(event_type, status, provider_session_id, payload)

    @staticmethod
    def _find_value(value: object, keys: tuple[str, ...]) -> str | None:
        if isinstance(value, dict):
            for key in keys:
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate:
                    return candidate
            for nested in value.values():
                found = OpenCodeCliAdapter._find_value(nested, keys)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = OpenCodeCliAdapter._find_value(nested, keys)
                if found:
                    return found
        return None

    @staticmethod
    def _require_contract_fields(session: SessionRef, prompt: str) -> None:
        required = (session.mission_id, session.task_id)
        if not prompt.strip() or any(value not in prompt for value in required):
            raise ValueError("delegated prompt must be non-empty and include mission_id and task_id")


class OpenCodeHttpAdapter:
    """HTTP adapter for an OpenCode headless server.

    The adapter uses the provider's session API (`/session` and
    `/prompt_async`) and never shells out. ``poll_events`` converts the
    provider's status map into normalized events; a future SSE consumer can be
    added without changing the mission-controller interface.
    """

    def __init__(
        self,
        *,
        base_url: str,
        registry: AgentRegistryResolver,
        timeout: float = 10.0,
        request: Callable | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.registry = registry
        self.timeout = timeout
        self._request_impl = request or self._request

    def list_agents(self) -> tuple[AgentDescriptor, ...]:
        payload = self._request_impl("GET", "/agent", None)
        if not isinstance(payload, list):
            raise ValueError("OpenCode /agent response must be a list")
        return tuple(
            AgentDescriptor(key=str(item["name"]), permissions={})
            for item in payload
            if isinstance(item, dict) and item.get("name")
        )

    def create_session(self, agent: str, title: str, mission_id: str, task_id: str) -> SessionRef:
        self.registry.resolve(agent)
        if not title.strip() or not mission_id.strip() or not task_id.strip():
            raise ValueError("title, mission_id and task_id must not be empty")
        payload = self._request_impl("POST", "/session", {"title": title, "agent": agent})
        session_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("OpenCode /session response did not include an id")
        return SessionRef(session_id, agent, title, mission_id, task_id)

    def delegate(self, session: SessionRef, prompt: str, mode: str = "run") -> DelegationRef:
        OpenCodeCliAdapter._require_contract_fields(session, prompt)
        if mode != "run":
            raise AdapterCapabilityError(f"unsupported OpenCode HTTP mode: {mode}")
        self._request_impl(
            "POST",
            f"/session/{session.session_id}/prompt_async",
            {"agent": session.agent_key, "parts": [{"type": "text", "text": prompt}]},
        )
        return DelegationRef(
            delegation_id=f"delegation-{uuid4().hex}",
            session_id=session.session_id,
            status="RUNNING",
            command=("HTTP", "POST", f"/session/{session.session_id}/prompt_async"),
        )

    def get_session_status(self, session: SessionRef) -> dict:
        payload = self._request_impl("GET", "/session/status", None)
        status = payload.get(session.session_id) if isinstance(payload, dict) else None
        if isinstance(status, dict):
            status_value = status.get("type", "UNKNOWN")
        else:
            status_value = "UNKNOWN"
        return {"session_id": session.session_id, "status": str(status_value).upper(), "provider": "opencode"}

    def get_session_children(self, session: SessionRef) -> tuple[SessionRef, ...]:
        payload = self._request_impl("GET", f"/session/{session.session_id}/children", None)
        if not isinstance(payload, list):
            return ()
        return tuple(
            SessionRef(
                session_id=str(item["id"]), agent_key=str(item.get("agent", "")),
                title=str(item.get("title", "")), mission_id=session.mission_id,
                task_id=f"{session.task_id}:child",
            )
            for item in payload if isinstance(item, dict) and item.get("id")
        )

    def resume(self, session: SessionRef, prompt: str) -> DelegationRef:
        return self.delegate(session, prompt)

    def poll_events(self) -> tuple[ProviderEvent, ...]:
        payload = self._request_impl("GET", "/session/status", None)
        if not isinstance(payload, dict):
            return ()
        return tuple(
            ProviderEvent(
                event_type="session.status",
                status=str(value.get("type", "unknown")).casefold() if isinstance(value, dict) else None,
                provider_session_id=str(session_id),
                payload={"session_id": session_id, "status": value},
            )
            for session_id, value in payload.items()
        )

    def subscribe_events(self) -> tuple[ProviderEvent, ...]:
        return self.poll_events()

    def delete_session(self, session: SessionRef) -> None:
        self._request_impl("DELETE", f"/session/{session.session_id}", None)

    def _request(self, method: str, path: str, body: dict | None) -> dict | list:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            f"{self.base_url}{path}", data=data, method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError) as error:
            raise AdapterCapabilityError(f"OpenCode HTTP request failed: {method} {path}: {error}") from error
        if not raw.strip():
            return {}
        payload = json.loads(raw)
        if not isinstance(payload, (dict, list)):
            raise ValueError(f"unexpected OpenCode response for {path}")
        return payload
