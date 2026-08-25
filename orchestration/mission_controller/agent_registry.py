"""Resolve functional routes to agents registered in ``opencode.json``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentDescriptor:
    """Provider-neutral description of a configured OpenCode agent."""

    key: str
    permissions: dict[str, Any]


class AgentRegistryResolver:
    """Read-only resolver for the local OpenCode agent registry."""

    def __init__(self, config_path: Path | str):
        self.config_path = Path(config_path)

    def list_agents(self) -> tuple[AgentDescriptor, ...]:
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        configured = config.get("agent", {})
        if not isinstance(configured, dict):
            raise ValueError("opencode.json agent registry must be an object")
        return tuple(
            AgentDescriptor(key=key, permissions=dict(value.get("permission", {})))
            for key, value in sorted(configured.items())
            if isinstance(value, dict)
        )

    def resolve(self, agent_key: str) -> AgentDescriptor:
        for agent in self.list_agents():
            if agent.key == agent_key:
                return agent
        available = ", ".join(agent.key for agent in self.list_agents())
        raise KeyError(f"agent not registered: {agent_key}; available: {available}")

    def validate(self, agent_keys: list[str] | tuple[str, ...]) -> None:
        available = {agent.key for agent in self.list_agents()}
        missing = sorted(set(agent_keys) - available)
        if missing:
            raise ValueError(f"unregistered agents: {missing}")
