"""Closed-candle diagnostic assessment for the mechanical signal producer.

This is intentionally an evaluator, not an entry model: it consumes the
already assembled canonical snapshot and preserves the engine's observe-only
authority.  A candidate is useful diagnostic evidence only; it is never a
BUY/SELL contract, a probability, or permission to trade.
"""
from __future__ import annotations

from typing import Any, Mapping


_DIRECTION = {1: "BULLISH", -1: "BEARISH"}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _direction(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.upper() in {"BULLISH", "BUY", "LONG", "UP"} else -1 if value.upper() in {"BEARISH", "SELL", "SHORT", "DOWN"} else 0
    try:
        return 1 if int(value) > 0 else -1 if int(value) < 0 else 0
    except (TypeError, ValueError):
        return 0


def _result(status: str, code: str, detail: str, snapshot: Mapping[str, Any], *, direction: int = 0,
            evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "MECHANICAL_SIGNAL_ASSESSMENT_V2A",
        "status": status,
        "code": code,
        "detail": detail,
        "symbol": snapshot.get("symbol"),
        "decision_time": snapshot.get("decision_time"),
        "context_direction": _DIRECTION.get(direction),
        "evidence": dict(evidence or {}),
        "entry_authorized": False,
        "can_trade": False,
        "publication": "DIAGNOSTIC_ONLY_NO_MECHANICAL_SNAPSHOT",
    }


def assess_mechanical_signal(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Evaluate the frozen H4/H1 -> M15 chain using only snapshot evidence.

    ``m15_evidence.sweep`` deliberately has no candle-derived fallback.  The
    current canonical assembler does not emit a causal sweep artifact, so an
    absent artifact abstains instead of turning a liquidity-zone heuristic
    into a claimed sweep.
    """
    snap = _mapping(snapshot)
    if not snap:
        return _result("BLOCKED", "CANONICAL_SNAPSHOT_UNAVAILABLE", "No existe snapshot canónico para evaluar.", snap)
    if (snap.get("schema_version") != "MT5_OPERATIONAL_SNAPSHOT_V1" or snap.get("status") != "READY"
            or snap.get("policy") != "OBSERVE_ONLY_NO_ORDER" or snap.get("can_trade") is not False
            or snap.get("entry_authorized") is not False):
        return _result("BLOCKED", "CANONICAL_SNAPSHOT_INVALID", "El snapshot canónico no está listo o rompe la frontera observacional.", snap)
    missing = [tf for tf in ("H4", "H1", "M15") if tf in set(snap.get("missing_timeframes") or [])]
    if missing:
        code = "M15_DATA_UNAVAILABLE" if "M15" in missing else "HTF_DATA_UNAVAILABLE"
        return _result("BLOCKED", code, "Faltan velas cerradas requeridas: " + ", ".join(missing) + ".", snap)

    daily = _mapping(snap.get("daily_motor"))
    context = _mapping(daily.get("context"))
    constraints = _mapping(context.get("constraints"))
    direction = _direction(daily.get("direction", context.get("direction_hint")))
    layers = _mapping(_mapping(snap.get("context_state")).get("layers"))
    h4, h1, m15 = (_mapping(layers.get(tf)) for tf in ("H4", "H1", "M15"))
    if not direction or not h4 or not h1 or not m15:
        return _result("BLOCKED", "HTF_EVIDENCE_UNAVAILABLE", "No hay contexto H4/H1/M15 cerrado suficiente para fijar la evaluación.", snap)
    expected = _DIRECTION[direction]
    side_allowed = constraints.get("allow_long") if direction > 0 else constraints.get("allow_short")
    if h4.get("structure_bias") != expected or h1.get("structure_bias") != expected or side_allowed is not True:
        return _result("NO_SIGNAL", "HTF_CONFLICT", "H4/H1 o las restricciones canónicas no están alineadas con la dirección contextual.", snap, direction=direction,
                       evidence={"h4_bias": h4.get("structure_bias"), "h1_bias": h1.get("structure_bias"), "side_allowed": side_allowed})

    evidence = _mapping(snap.get("m15_evidence"))
    sweep = evidence.get("sweep")
    if sweep is not True:
        code = "NO_SWEEP" if sweep is False else "SWEEP_EVIDENCE_UNAVAILABLE"
        return _result("NO_SIGNAL" if sweep is False else "BLOCKED", code, "No existe evidencia causal explícita de sweep M15 en velas cerradas.", snap, direction=direction,
                       evidence={"sweep": sweep, "source": evidence.get("source")})
    displacement = evidence.get("displacement", m15.get("displacement_recent"))
    if displacement is not True:
        return _result("NO_SIGNAL", "NO_DISPLACEMENT", "Tras el sweep no hay displacement M15 confirmado por vela cerrada.", snap, direction=direction)
    bos_or_choch = evidence.get("bos_or_choch")
    if bos_or_choch is not True:
        return _result("NO_SIGNAL", "NO_BOS", "Tras el displacement no hay BOS/CHOCH M15 compatible confirmado.", snap, direction=direction)
    ltf = _mapping(daily.get("ltf"))
    zone_present = evidence.get("fvg_or_ob", ltf.get("zone_present"))
    if zone_present is not True:
        return _result("NO_SIGNAL", "NO_FVG_OR_OB", "No hay FVG u Order Block M15 canónico compatible.", snap, direction=direction)
    retest = evidence.get("retest", ltf.get("retest_observed"))
    if retest is not True:
        return _result("NO_SIGNAL", "WAIT_RETEST", "La zona M15 existe, pero aún no registra retest cerrado.", snap, direction=direction)
    return _result("CANDIDATE_SETUP", "CHAIN_COMPLETE_DIAGNOSTIC", "Cadena H4/H1→M15 completa como diagnóstico; no crea señal operable.", snap, direction=direction,
                   evidence={"sweep": True, "displacement": True, "bos_or_choch": True, "fvg_or_ob": True, "retest": True,
                             "m5_m1": snap.get("micro_confirmation")})


__all__ = ["assess_mechanical_signal"]
