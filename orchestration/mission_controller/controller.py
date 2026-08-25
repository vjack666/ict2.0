"""Provider-neutral mission creation and routing."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
import os
import tempfile
from json import dumps
from pathlib import Path
from uuid import uuid4

from .agent_registry import AgentRegistryResolver
from .memory import EngramCliMemorySink, MemorySaveResult
from .opencode_adapter import DelegationRef, SessionRef
from .router import route_request
from .store import MissionStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionController:
    """Create auditable missions without executing delegated work."""

    controller_version = "MC-0/MC-3-local-1.1"

    def __init__(self, store: MissionStore | None = None, workspace: Path | str | None = None, agent_registry: AgentRegistryResolver | None = None, memory_sink=None):
        self.workspace = Path(workspace or Path(__file__).resolve().parents[2])
        self.store = store or MissionStore(self.workspace / ".hermes-state" / "missions")
        config_path = self.workspace / "opencode.json"
        self.agent_registry = agent_registry or (
            AgentRegistryResolver(config_path) if config_path.is_file() else None
        )
        self.memory_sink = memory_sink or (EngramCliMemorySink() if config_path.is_file() else None)

    def create_mission(self, objective: str, *, allowed_roots: list[str] | None = None) -> dict:
        route = route_request(objective)
        if self.agent_registry is not None:
            self.agent_registry.resolve(route.agent_key)
        mission_id = f"MC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        task_id = f"{mission_id}-T01"
        mission = {
            "schema_version": "1.0",
            "mission_id": mission_id,
            "created_at": _now(),
            "updated_at": _now(),
            "controller_version": self.controller_version,
            "git_head": self._git_head(),
            "objective": objective,
            "scope": {
                "workspace": self.workspace.name,
                "allowed_roots": allowed_roots or [route.department_id],
                "excluded_roots": ["secrets/"],
            },
            "authority": {
                "owner": "user",
                "ceo": "codex",
                "autonomy_policy": "technical_subordinate_decisions",
                "escalation_boundaries": ["OBJECTIVE", "SCOPE", "AUTHORITY", "SECURITY", "BUDGET", "IRREVERSIBLE_DATA"],
            },
            "phase": "PLAN",
            "status": "PLAN",
            "plan": [{"step": "route", "status": "COMPLETED", "department": route.department_id}],
            "tasks": [{
                "task_id": task_id,
                "mission_id": mission_id,
                "kind": route.task_kind,
                "title": objective,
                "status": "PENDING",
                "depends_on": [],
                "assigned_agent": route.assigned_role,
                "agent_key": route.agent_key,
                "department_id": route.department_id,
                "opencode_session_id": None,
                "attempt": 0,
                "inputs": [],
                "outputs": [],
                "evidence_refs": [],
                "blocker_refs": [],
                "next_action": "discover_context",
                "started_at": None,
                "completed_at": None,
            }],
            "route": route.to_dict(),
            "delegation": {
                "provider": "opencode",
                "agent_key": route.agent_key,
                "session_id": None,
                "status": "PLANNED",
            },
            "decisions": [],
            "evidence": [],
            "blockers": [],
            "completion_state": {
                "objective_satisfied": False,
                "required_tests_pass": False,
                "evidence_recorded": False,
                "no_unresolved_blockers": False,
                "artifacts_consistent": False,
                "mission_complete": False,
            },
            "resume": {"last_checkpoint": None, "active_task_id": None, "opencode_session_ids": [], "attempts": 0},
        }
        self.store.save(mission)
        self.store.append_event(mission_id, {"type": "MISSION_CREATED", "department_id": route.department_id, "assigned_agent": route.assigned_role})
        return mission

    def delegate_task(self, mission_id: str, task_id: str, adapter, prompt: str) -> dict:
        """Delegate one persisted task and record the provider reference.

        The adapter owns provider I/O. This method owns mission state, so a
        provider response can never silently become a completed task.
        """
        mission = self.store.load(mission_id)
        task = self._task(mission, task_id)
        if task["status"] not in {"PENDING", "PLANNED", "RECOVER"}:
            raise ValueError(f"task is not delegable from status {task['status']}")
        if task.get("opencode_session_id"):
            raise ValueError("task already has a durable provider session")
        session = adapter.create_session(
            task["agent_key"], task["title"], mission_id, task_id,
        )
        delegation = adapter.delegate(session, prompt)
        task["opencode_session_id"] = session.session_id
        task["delegation_id"] = delegation.delegation_id
        task["delegation_status"] = delegation.status
        task["started_at"] = _now() if delegation.status == "RUNNING" else None
        task["status"] = "RUNNING" if delegation.status == "RUNNING" else "PLANNED"
        mission["delegation"] = {
            "provider": "opencode",
            "agent_key": task["agent_key"],
            "session_id": session.session_id,
            "delegation_id": delegation.delegation_id,
            "status": delegation.status,
        }
        mission["phase"] = "EXECUTE" if delegation.status == "RUNNING" else "DELEGATE"
        mission["status"] = mission["phase"]
        mission["resume"]["active_task_id"] = task_id
        mission["resume"]["opencode_session_ids"] = [session.session_id]
        self.store.save(mission)
        self.store.append_event(mission_id, {
            "type": "TASK_DELEGATED", "task_id": task_id,
            "agent_key": task["agent_key"], "session_id": session.session_id,
            "delegation_id": delegation.delegation_id, "status": delegation.status,
        })
        return mission

    def reconcile_task(self, mission_id: str, task_id: str, adapter) -> dict:
        """Reconcile provider status without inventing task evidence."""
        mission = self.store.load(mission_id)
        task = self._task(mission, task_id)
        session_id = task.get("opencode_session_id")
        if not session_id:
            raise ValueError("task has no provider session")
        session = SessionRef(
            session_id=session_id, agent_key=task["agent_key"],
            title=task["title"], mission_id=mission_id, task_id=task_id,
        )
        provider = adapter.get_session_status(session)
        provider_status = str(provider.get("status", "UNKNOWN")).upper()
        task["provider_status"] = provider_status
        task["provider_snapshot"] = provider
        if provider_status in {"RUNNING", "BUSY"}:
            task["status"] = "RUNNING"
            mission["phase"] = mission["status"] = "WAITING_FOR_AGENT"
        elif provider_status in {"COMPLETED", "IDLE", "SUCCESS"}:
            # Provider completion is only an observation. Outputs/evidence are
            # still required before the task can become COMPLETE.
            task["status"] = "OBSERVE"
            mission["phase"] = mission["status"] = "OBSERVE"
            task["next_action"] = "collect_outputs_and_evidence"
        elif provider_status in {"FAILED", "ERROR"}:
            task["status"] = "RECOVER"
            task["blocker_refs"] = [f"provider_status:{provider_status}"]
            mission["phase"] = mission["status"] = "RECOVER"
        else:
            mission["phase"] = mission["status"] = "WAITING_FOR_AGENT"
        self.store.save(mission)
        self.store.append_event(mission_id, {
            "type": "TASK_RECONCILED", "task_id": task_id,
            "provider_status": provider_status, "task_status": task["status"],
        })
        return mission

    def recover_mission(self, mission_id: str, adapter) -> dict:
        """Re-open a durable mission after controller/process restart."""
        mission = self.store.load(mission_id)
        if mission["status"] in {"COMPLETE", "FAILED"}:
            return mission
        active = mission.get("resume", {}).get("active_task_id")
        self.store.append_event(mission_id, {"type": "MISSION_RECOVERED", "active_task_id": active})
        if active:
            return self.reconcile_task(mission_id, active, adapter)
        mission["status"] = "PLAN"
        mission["phase"] = "PLAN"
        mission["resume"]["attempts"] = int(mission.get("resume", {}).get("attempts", 0)) + 1
        self.store.save(mission)
        return mission

    def set_gate(self, mission_id: str, gate: str, passed: bool, evidence_ref: str) -> dict:
        """Record one completion predicate with explicit evidence."""
        valid = {
            "objective_satisfied", "required_tests_pass", "evidence_recorded",
            "no_unresolved_blockers", "artifacts_consistent",
        }
        if gate not in valid:
            raise ValueError(f"unknown completion gate: {gate}")
        if not evidence_ref.strip():
            raise ValueError("gate evidence_ref must not be empty")
        mission = self.store.load(mission_id)
        mission["completion_state"][gate] = bool(passed)
        mission.setdefault("evidence", []).append({"gate": gate, "passed": bool(passed), "ref": evidence_ref})
        self.store.save(mission)
        self.store.append_event(mission_id, {"type": "GATE_RECORDED", "gate": gate, "passed": bool(passed), "evidence_ref": evidence_ref})
        return mission

    def verify_task(self, mission_id: str, task_id: str, *, outputs: list[str], evidence_refs: list[str]) -> dict:
        """Accept a task result only when it has outputs and evidence."""
        if not outputs or not evidence_refs:
            raise ValueError("task verification requires outputs and evidence_refs")
        mission = self.store.load(mission_id)
        task = self._task(mission, task_id)
        if task["status"] not in {"OBSERVE", "VERIFY"}:
            raise ValueError(f"task cannot be verified from status {task['status']}")
        task["outputs"] = list(outputs)
        task["evidence_refs"] = list(evidence_refs)
        task["status"] = "COMPLETE"
        task["completed_at"] = _now()
        mission["phase"] = mission["status"] = "VERIFY"
        mission["completion_state"]["evidence_recorded"] = True
        mission.setdefault("evidence", []).extend(evidence_refs)
        self.store.save(mission)
        self.store.append_event(mission_id, {"type": "TASK_VERIFIED", "task_id": task_id, "outputs": outputs, "evidence_refs": evidence_refs})
        return mission

    def complete_mission(self, mission_id: str, final_evidence_ref: str) -> dict:
        """Close only when every SDD completion predicate is true."""
        if not final_evidence_ref.strip():
            raise ValueError("final_evidence_ref must not be empty")
        mission = self.store.load(mission_id)
        if any(task.get("status") != "COMPLETE" for task in mission.get("tasks", [])):
            raise ValueError("cannot complete mission with incomplete tasks")
        predicates = (
            "objective_satisfied", "required_tests_pass", "evidence_recorded",
            "no_unresolved_blockers", "artifacts_consistent",
        )
        if not all(mission["completion_state"].get(predicate) is True for predicate in predicates):
            raise ValueError("completion predicates are not all true")
        mission["evidence"].append(final_evidence_ref)
        mission["completion_state"]["mission_complete"] = True
        mission["status"] = mission["phase"] = "COMPLETE"
        mission["resume"]["active_task_id"] = None
        for task in mission.get("tasks", []):
            task["next_action"] = "none"
        worklog_path = self._worklog_path(mission_id)
        mission["worklog_path"] = str(worklog_path.relative_to(self.workspace))
        self.store.save(mission)
        self.store.append_event(mission_id, {"type": "MISSION_COMPLETED", "final_evidence_ref": final_evidence_ref})
        if self.memory_sink is not None:
            try:
                memory_result = self.memory_sink.save(mission)
            except Exception:
                memory_result = MemorySaveResult("engram", "ERROR", "ict2.0", "sink_exception")
            mission["memory"] = memory_result.to_dict()
            self.store.save(mission)
            self.store.append_event(mission_id, {"type": "MEMORY_CLOSEOUT", "provider": memory_result.provider, "status": memory_result.status})
        self.write_worklog(mission_id)
        return mission

    def write_worklog(self, mission_id: str) -> Path:
        """Write a human-readable durable closeout/checkpoint worklog."""
        mission = self.store.load(mission_id)
        target = self._worklog_path(mission_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        tasks = mission.get("tasks", [])
        lines = [
            f"# Hermes Mission Worklog — {mission_id}",
            "",
            f"- **Estado:** `{mission['status']}`",
            f"- **Fase:** `{mission['phase']}`",
            f"- **Objetivo:** {mission['objective']}",
            f"- **Git HEAD:** `{mission.get('git_head')}`",
            "",
            "## Ruta y delegación",
            "",
            "```json",
            dumps(mission.get("route", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Tareas",
            "",
        ]
        for task in tasks:
            lines.append(f"- `{task.get('task_id')}` — `{task.get('status')}` — agente `{task.get('agent_key')}`")
            if task.get("evidence_refs"):
                lines.append(f"  - evidencia: {', '.join(task['evidence_refs'])}")
        lines.extend([
            "",
            "## Completion state",
            "",
            "```json",
            dumps(mission.get("completion_state", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Evidencia",
            "",
            *[f"- {item if isinstance(item, str) else dumps(item, ensure_ascii=False)}" for item in mission.get("evidence", [])],
            "",
            "## Siguiente acción",
            "",
            f"{tasks[0].get('next_action') if tasks else 'none'}",
            "",
        ])
        content = "\n".join(lines)
        fd, temporary = tempfile.mkstemp(prefix=f".{mission_id}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return target

    def audit_mission(self, mission_id: str) -> list[dict[str, str]]:
        """Return durable-snapshot findings; findings are fail-closed."""
        mission = self.store.load(mission_id)
        findings: list[dict[str, str]] = []
        excluded = set(mission.get("scope", {}).get("excluded_roots", []))
        allowed = set(mission.get("scope", {}).get("allowed_roots", []))
        if excluded & allowed:
            findings.append({"severity": "BLOCKING", "code": "SCOPE_OVERLAP", "detail": "allowed and excluded roots overlap"})
        for task in mission.get("tasks", []):
            if task.get("status") == "COMPLETE" and (not task.get("outputs") or not task.get("evidence_refs")):
                findings.append({"severity": "BLOCKING", "code": "COMPLETE_WITHOUT_EVIDENCE", "detail": task.get("task_id", "unknown")})
            if task.get("status") in {"RUNNING", "OBSERVE", "RECOVER"} and not task.get("opencode_session_id"):
                findings.append({"severity": "WARNING", "code": "TASK_WITHOUT_SESSION", "detail": task.get("task_id", "unknown")})
        if mission.get("status") == "COMPLETE" and not mission.get("completion_state", {}).get("mission_complete"):
            findings.append({"severity": "BLOCKING", "code": "STATUS_COMPLETION_MISMATCH", "detail": mission_id})
        return findings

    def _worklog_path(self, mission_id: str) -> Path:
        return self.workspace / ".hermes-worklog" / f"HERMES_MISSION_{mission_id}.md"

    @staticmethod
    def _task(mission: dict, task_id: str) -> dict:
        for task in mission.get("tasks", []):
            if task.get("task_id") == task_id:
                return task
        raise KeyError(f"unknown task: {task_id}")

    def _git_head(self) -> str | None:
        try:
            return subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.workspace, check=True,
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
