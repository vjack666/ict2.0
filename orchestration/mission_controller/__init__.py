"""Mission planning and department routing for ICT 2.0."""

from .controller import MissionController
from .agent_registry import AgentDescriptor, AgentRegistryResolver
from .opencode_adapter import (
    AdapterCapabilityError,
    DelegationRef,
    OpenCodeCliAdapter,
    OpenCodeHttpAdapter,
    ProviderEvent,
    SessionRef,
)
from .memory import EngramCliMemorySink, MemorySaveResult
from .models import RouteDecision
from .router import route_request
from .store import MissionStore

__all__ = [
    "AgentDescriptor",
    "AgentRegistryResolver",
    "AdapterCapabilityError",
    "DelegationRef",
    "EngramCliMemorySink",
    "MissionController",
    "MissionStore",
    "MemorySaveResult",
    "OpenCodeCliAdapter",
    "OpenCodeHttpAdapter",
    "ProviderEvent",
    "RouteDecision",
    "SessionRef",
    "route_request",
]
