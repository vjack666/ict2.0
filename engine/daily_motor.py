"""Composición segura del motor diario con observación LTF/EXEC.

Esta capa une el contexto top-down existente (`engine.plan`) con el LTF del
perfil diario. Es observacional: no emite órdenes ni inventa entry/SL/TP.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from engine.plan import (
    build_context_stack,
    ltf_structure_at,
    top_down_allows_trade,
)


@dataclass(frozen=True)
class DailyMotorConfig:
    """Perfil temporal explícito para la lectura diaria intradía."""

    htf: str = "D1"
    itf: str = "H4"
    context_tf: str = "H1"
    exec_tf: str = "M15"
    require_d1: bool = True
    require_itf: bool = True
    require_context: bool = True
    require_pd: bool = True

    @property
    def tfs(self) -> tuple[str, ...]:
        return (self.htf, self.itf, self.context_tf, self.exec_tf)


def _asof_time(frames: dict[str, pd.DataFrame], tf: str) -> Any:
    df = frames.get(tf)
    if df is None or df.empty or "time" not in df.columns:
        return None
    return pd.to_datetime(df["time"], utc=True, errors="coerce").max()


def _direction_from_stack(stack: dict[str, Any], config: DailyMotorConfig) -> int:
    for tf in (config.htf, config.itf, config.context_tf):
        trend = str((stack.get(tf) or {}).get("trend", "RANGING")).upper()
        if trend == "BULLISH":
            return 1
        if trend == "BEARISH":
            return -1
    return 0


def _closed_zone_state(frame: pd.DataFrame | None, decision_time: Any) -> dict[str, Any]:
    """Read explicit zone/retest markers from the last closed EXEC row."""
    if frame is None or frame.empty or "time" not in frame.columns:
        return {"zone_present": False, "retest_observed": False}
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(decision_time, utc=True, errors="coerce")
    if pd.isna(tt):
        return {"zone_present": False, "retest_observed": False}
    past = frame.loc[times <= tt]
    if past.empty:
        return {"zone_present": False, "retest_observed": False}
    row = past.iloc[-1]
    fvg_state = str(row.get("fvg_state", "NONE") or "NONE").upper()
    ob_dir = str(row.get("ob_direction", row.get("ob_dir", "-")) or "-").upper()
    zone_present = fvg_state not in {"", "NONE", "NAN", "NULL"} or ob_dir not in {"", "-", "NONE", "NAN", "NULL"}
    marker_values = [
        row.get("retest_observed", False),
        row.get("retest", False),
        row.get("zone_touched", False),
    ]
    marker_text = " ".join(str(v).upper() for v in marker_values)
    retest_observed = any(bool(v) for v in marker_values if not isinstance(v, str))
    retest_observed = retest_observed or any(
        token in marker_text for token in ("TOUCHED", "RETEST", "MITIGATED", "FILLED")
    )
    return {
        "zone_present": bool(zone_present),
        "retest_observed": bool(retest_observed),
        "fvg_state": fvg_state,
        "ob_direction": ob_dir,
    }


def build_daily_motor_snapshot(
    frames: dict[str, pd.DataFrame],
    decision_time: Any = None,
    config: DailyMotorConfig | None = None,
) -> dict[str, Any]:
    """Build a closed-only daily context + LTF observation snapshot.

    The output is deliberately not an order API. It reports what the daily
    motor may observe at ``decision_time`` and why it is waiting.
    """
    config = config or DailyMotorConfig()
    frames = frames or {}
    if decision_time is None:
        decision_time = _asof_time(frames, config.exec_tf)
    tt = pd.to_datetime(decision_time, utc=True, errors="coerce")
    if pd.isna(tt):
        return {
            "policy": "OBSERVE_ONLY_NO_ORDER",
            "entry_authorized": False,
            "status": "NO_LTF_DATA",
            "decision_time": None,
            "direction": 0,
            "context": {"allowed": False, "reason": "invalid_decision_time", "stack": {}},
            "ltf": {"tf": config.exec_tf, "available": False},
        }

    stack = build_context_stack(frames, tt, tfs=config.tfs)
    direction = _direction_from_stack(stack, config)
    gate_allowed, gate_reason = top_down_allows_trade(
        stack,
        direction,
        require_d1=config.require_d1,
        require_h4=config.require_itf,
        require_h1=config.require_context,
        require_pd=config.require_pd,
        require_ltf=False,
    ) if direction else (False, "no_htf_direction")

    structure = ltf_structure_at(frames, config.exec_tf, tt)
    zone = _closed_zone_state(frames.get(config.exec_tf), tt)
    want = "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "RANGING"
    structure_confirmed = bool(
        direction
        and (
            structure.get("trend") == want
            or int(structure.get("bos_dir", 0) or 0) == direction
            or int(structure.get("momentum", 0) or 0) == direction
        )
    )
    ltf_available = bool(structure.get("available"))
    if not ltf_available:
        status = "NO_LTF_DATA"
    elif not gate_allowed:
        status = "WAIT_CONTEXT"
    elif not structure_confirmed:
        status = "WAIT_LTF_CONFIRMATION"
    elif not zone.get("zone_present"):
        status = "WAIT_LTF_ZONE"
    elif not zone.get("retest_observed"):
        status = "WAIT_RETEST"
    else:
        status = "OBSERVABLE_SETUP"

    ltf = {
        "tf": config.exec_tf,
        "available": ltf_available,
        "asof_time": structure.get("time"),
        "trend": structure.get("trend", "RANGING"),
        "bos_dir": int(structure.get("bos_dir", 0) or 0),
        "momentum": int(structure.get("momentum", 0) or 0),
        "structure_confirmed": structure_confirmed,
        **zone,
    }
    return {
        "policy": "OBSERVE_ONLY_NO_ORDER",
        "entry_authorized": False,
        "status": status,
        "decision_time": str(tt),
        "direction": direction,
        "direction_label": want,
        "context": {
            "allowed": bool(gate_allowed),
            "reason": gate_reason,
            "stack": stack,
        },
        "ltf": ltf,
    }


__all__ = ["DailyMotorConfig", "build_daily_motor_snapshot"]
