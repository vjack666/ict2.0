"""AHF — Adaptive Hierarchical MTF Funnel (máquina de estados ejecutable).

Implementa docs/CONTRATO_AHF.md y SDD §4.3.
No emite entradas. Todo as-of(t).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Mapping

import pandas as pd

from engine.mtf_navigation import (
    ContextConstraints,
    LayerSnapshot,
    MTFNavigator,
    NavigatorConfig,
    StructureBias,
    TimeframeLayer,
)


class AHFState(str, Enum):
    WAIT_D1 = "WAIT_D1"
    D1_LOCKED = "D1_LOCKED"
    WAIT_H4 = "WAIT_H4"
    H4_LOCKED = "H4_LOCKED"
    WAIT_H1 = "WAIT_H1"
    WAIT_LTF = "WAIT_LTF"
    SETUP_READY = "SETUP_READY"
    OUTCOME = "OUTCOME"


class AHFEvent(str, Enum):
    D1_PASS = "D1_PASS"
    H4_PASS = "H4_PASS"
    H1_PASS = "H1_PASS"
    LTF_CONFIRMATION = "LTF_CONFIRMATION"
    OUTCOME_MARK = "OUTCOME_MARK"
    D1_INVALIDATED = "D1_INVALIDATED"
    H4_INVALIDATED = "H4_INVALIDATED"
    H1_INVALIDATED = "H1_INVALIDATED"
    NOOP = "NOOP"


# active TF while in state
_STATE_TF: dict[AHFState, str] = {
    AHFState.WAIT_D1: "D1",
    AHFState.D1_LOCKED: "D1",
    AHFState.WAIT_H4: "H4",
    AHFState.H4_LOCKED: "H4",
    AHFState.WAIT_H1: "H1",
    AHFState.WAIT_LTF: "H1",  # LTF may be H1 if no M15
    AHFState.SETUP_READY: "H1",
    AHFState.OUTCOME: "H1",
}


@dataclass
class AHFTransition:
    state: str
    active_tf: str
    transition_event: str
    transition_time: Any
    parent_state: str | None
    invalidation_reason: str | None = None
    confirmed_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "active_tf": self.active_tf,
            "transition_event": self.transition_event,
            "transition_time": str(self.transition_time),
            "parent_state": self.parent_state,
            "invalidation_reason": self.invalidation_reason,
            "confirmed_context": self.confirmed_context,
        }


@dataclass
class AHFSnapshot:
    """Estado de la máquina en un decision_time."""

    decision_time: Any
    state: AHFState
    active_tf: str
    confirmed_context: dict[str, Any]
    constraints: ContextConstraints | None
    history: list[AHFTransition]
    last_event: AHFEvent
    status: str = "OK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_time": str(self.decision_time),
            "state": self.state.value,
            "active_tf": self.active_tf,
            "confirmed_context": self.confirmed_context,
            "constraints": self.constraints.to_dict() if self.constraints else None,
            "last_event": self.last_event.value,
            "status": self.status,
            "history": [h.to_dict() for h in self.history],
            "policy": "AHF_STATE_NOT_ENTRY",
        }


def _ctx_blob(snap: LayerSnapshot | None) -> dict[str, Any]:
    if snap is None:
        return {}
    return {
        "layer": snap.layer.value,
        "asof_bar": snap.asof_bar,
        "asof_time": str(snap.asof_time),
        "structure_bias": snap.structure_bias.value,
        "regime": snap.regime.value,
        "last_close": snap.last_close,
        "last_bos_direction": snap.last_bos_direction,
        "answers": snap.answers,
    }


@dataclass
class AHFConfig:
    min_seq_depth_h1: int = 1
    min_seq_depth_setup: int = 4  # if no separate LTF
    enable_invalidation: bool = True
    navigator: NavigatorConfig = field(default_factory=NavigatorConfig)


class AdaptiveHierarchicalFunnel:
    """Máquina AHF sobre un MTFNavigator."""

    def __init__(
        self,
        frames: Mapping[str, pd.DataFrame],
        config: AHFConfig | None = None,
    ) -> None:
        self.config = config or AHFConfig()
        self.nav = MTFNavigator(frames, self.config.navigator)
        self._state = AHFState.WAIT_D1
        self._history: list[AHFTransition] = []
        self._confirmed: dict[str, Any] = {}
        self._lock_bias: dict[str, str] = {}  # layer -> structure bias at lock

    @property
    def state(self) -> AHFState:
        return self._state

    def reset(self) -> None:
        self._state = AHFState.WAIT_D1
        self._history.clear()
        self._confirmed.clear()
        self._lock_bias.clear()

    def _emit(
        self,
        new_state: AHFState,
        event: AHFEvent,
        t: Any,
        parent: AHFState,
        reason: str | None = None,
    ) -> None:
        tr = AHFTransition(
            state=new_state.value,
            active_tf=_STATE_TF[new_state],
            transition_event=event.value,
            transition_time=t,
            parent_state=parent.value,
            invalidation_reason=reason,
            confirmed_context=dict(self._confirmed),
        )
        self._history.append(tr)
        self._state = new_state

    def _d1_pass(self, layers: dict[str, LayerSnapshot]) -> bool:
        d1 = layers.get("D1")
        if not d1:
            return False
        ans = d1.answers.get("HAS_RELEVANT_CONTEXT")
        if ans is None:
            # compute if navigate didn't set — structure or liq
            has_liq = any(z.kind in ("BSL", "SSL") for z in d1.zones)
            return d1.structure_bias is not StructureBias.UNKNOWN or has_liq
        return bool(ans)

    def _h4_pass(self, layers: dict[str, LayerSnapshot]) -> bool:
        return "H4" in layers

    def _h1_pass(self, layers: dict[str, LayerSnapshot]) -> bool:
        h1 = layers.get("H1")
        if not h1:
            return False
        depth_ans = h1.answers.get("HAS_SEQUENCE_DEPTH")
        depth = 0
        if isinstance(depth_ans, dict):
            depth = int(depth_ans.get("depth") or 0)
        elif depth_ans is not None:
            depth = int(depth_ans)
        has_struct = h1.structure_bias is not StructureBias.UNKNOWN or h1.last_bos_direction is not None
        return has_struct or depth >= self.config.min_seq_depth_h1

    def _ltf_confirm(self, layers: dict[str, LayerSnapshot]) -> bool:
        # Prefer M15 if present, else H1 depth/trigger
        ltf = layers.get("M15") or layers.get("M5") or layers.get("H1")
        if not ltf:
            return False
        depth_ans = (layers.get("H1") or ltf).answers.get("HAS_SEQUENCE_DEPTH")
        depth = int(depth_ans.get("depth") or 0) if isinstance(depth_ans, dict) else int(depth_ans or 0)
        if depth >= self.config.min_seq_depth_setup:
            return True
        trig = ltf.answers.get("HAS_TRIGGER")
        if trig is True:
            return True
        return bool(ltf.displacement_recent)

    def _check_invalidation(
        self, layers: dict[str, LayerSnapshot], t: Any
    ) -> tuple[AHFEvent, str, AHFState] | None:
        if not self.config.enable_invalidation:
            return None
        # D1 bias flip vs lock
        d1 = layers.get("D1")
        if d1 and "D1" in self._lock_bias and self._state not in (AHFState.WAIT_D1,):
            locked = self._lock_bias["D1"]
            now = d1.structure_bias.value
            if locked in ("BULLISH", "BEARISH") and now in ("BULLISH", "BEARISH") and now != locked:
                return AHFEvent.D1_INVALIDATED, f"D1 bias {locked}->{now}", AHFState.WAIT_D1
        # H4 opposite to locked D1
        h4 = layers.get("H4")
        if (
            h4
            and "D1" in self._lock_bias
            and self._state in (AHFState.WAIT_H1, AHFState.WAIT_LTF, AHFState.SETUP_READY, AHFState.H4_LOCKED)
        ):
            d1b = self._lock_bias["D1"]
            if d1b == "BULLISH" and h4.structure_bias is StructureBias.BEARISH:
                return AHFEvent.H4_INVALIDATED, "H4 BEARISH vs D1 BULLISH lock", AHFState.WAIT_H4
            if d1b == "BEARISH" and h4.structure_bias is StructureBias.BULLISH:
                return AHFEvent.H4_INVALIDATED, "H4 BULLISH vs D1 BEARISH lock", AHFState.WAIT_H4
        # H1: structure against lock direction after H1_PASS
        h1 = layers.get("H1")
        if h1 and self._state in (AHFState.WAIT_LTF, AHFState.SETUP_READY) and "D1" in self._lock_bias:
            d1b = self._lock_bias["D1"]
            if d1b == "BULLISH" and h1.last_bos_direction == -1:
                return AHFEvent.H1_INVALIDATED, "H1 BOS down vs D1 bull lock", AHFState.WAIT_H1
            if d1b == "BEARISH" and h1.last_bos_direction == 1:
                return AHFEvent.H1_INVALIDATED, "H1 BOS up vs D1 bear lock", AHFState.WAIT_H1
        return None

    def step(self, decision_time: Any, exec_tf: str = "H1") -> AHFSnapshot:
        """Un paso de la máquina en decision_time (vela de ejecución)."""
        market = self.nav.navigate(decision_time=decision_time, exec_tf=exec_tf)
        layers = market.layers
        parent = self._state
        event = AHFEvent.NOOP

        # Invalidation first
        inv = self._check_invalidation(layers, decision_time)
        if inv is not None:
            ev, reason, target = inv
            # clear locks at and below target
            if target == AHFState.WAIT_D1:
                self._confirmed.clear()
                self._lock_bias.clear()
            elif target == AHFState.WAIT_H4:
                self._confirmed.pop("H4", None)
                self._confirmed.pop("H1", None)
                self._lock_bias.pop("H4", None)
                self._lock_bias.pop("H1", None)
            elif target == AHFState.WAIT_H1:
                self._confirmed.pop("H1", None)
                self._lock_bias.pop("H1", None)
            self._emit(target, ev, decision_time, parent, reason)
            event = ev
        else:
            # Forward transitions
            st = self._state
            if st is AHFState.WAIT_D1 and self._d1_pass(layers):
                self._confirmed["D1"] = _ctx_blob(layers.get("D1"))
                if layers.get("D1"):
                    self._lock_bias["D1"] = layers["D1"].structure_bias.value
                self._emit(AHFState.D1_LOCKED, AHFEvent.D1_PASS, decision_time, parent)
                self._emit(AHFState.WAIT_H4, AHFEvent.D1_PASS, decision_time, AHFState.D1_LOCKED)
                event = AHFEvent.D1_PASS
            elif st is AHFState.WAIT_H4 and self._h4_pass(layers):
                self._confirmed["H4"] = _ctx_blob(layers.get("H4"))
                if layers.get("H4"):
                    self._lock_bias["H4"] = layers["H4"].structure_bias.value
                self._emit(AHFState.H4_LOCKED, AHFEvent.H4_PASS, decision_time, parent)
                self._emit(AHFState.WAIT_H1, AHFEvent.H4_PASS, decision_time, AHFState.H4_LOCKED)
                event = AHFEvent.H4_PASS
            elif st is AHFState.WAIT_H1 and self._h1_pass(layers):
                self._confirmed["H1"] = _ctx_blob(layers.get("H1"))
                if layers.get("H1"):
                    self._lock_bias["H1"] = layers["H1"].structure_bias.value
                self._emit(AHFState.WAIT_LTF, AHFEvent.H1_PASS, decision_time, parent)
                event = AHFEvent.H1_PASS
            elif st is AHFState.WAIT_LTF and self._ltf_confirm(layers):
                self._emit(AHFState.SETUP_READY, AHFEvent.LTF_CONFIRMATION, decision_time, parent)
                event = AHFEvent.LTF_CONFIRMATION
            elif st is AHFState.SETUP_READY:
                # Optional mark outcome without trading
                pass

        return AHFSnapshot(
            decision_time=decision_time,
            state=self._state,
            active_tf=_STATE_TF[self._state],
            confirmed_context=dict(self._confirmed),
            constraints=market.constraints,
            history=list(self._history),
            last_event=event,
            status=market.status,
        )

    def run_timeline(
        self,
        decision_times: list[Any],
        exec_tf: str = "H1",
    ) -> list[AHFSnapshot]:
        self.reset()
        return [self.step(t, exec_tf=exec_tf) for t in decision_times]
