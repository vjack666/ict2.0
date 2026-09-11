"""Read-only health of the canonical analysis; never an execution signal."""
from datetime import datetime, timezone

TF_SECONDS = {"D1": 86400, "H4": 14400, "H1": 3600, "M15": 900, "M5": 300, "M1": 60}


def _time(value):
    if not isinstance(value, str):
        raise ValueError("timestamp required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timezone required")
    return stamp.astimezone(timezone.utc)


def canonical_health(engine, connection, symbol, now=None):
    now = now or datetime.now(timezone.utc)
    snapshot = engine.get("snapshot")
    result = {"valid": False, "code": "CANONICAL_MISSING", "detail": "Esperando el análisis canónico del motor.",
              "decision_time": None, "age_seconds": None, "max_age_seconds": 180,
              "can_trade": False, "entry_authorized": False}

    def fail(code, detail):
        return {**result, "code": code, "detail": detail}

    if not isinstance(snapshot, dict):
        if engine.get("status") == "ERROR":
            return fail("ENGINE_ERROR", "Falló el cálculo: " + str(engine.get("error", "sin detalle")))
        return result
    if snapshot.get("schema_version") != "MT5_OPERATIONAL_SNAPSHOT_V1":
        return fail("CANONICAL_SCHEMA_INVALID", "Esquema canónico incompatible.")
    if snapshot.get("symbol") != symbol:
        return fail("CANONICAL_SYMBOL_MISMATCH", "El símbolo del análisis no coincide.")
    if (snapshot.get("policy") != "OBSERVE_ONLY_NO_ORDER" or snapshot.get("can_trade") is not False
            or snapshot.get("entry_authorized") is not False):
        return fail("CANONICAL_POLICY_INVALID", "Contrato de lectura canónica incompatible.")
    if snapshot.get("status") != "READY" or snapshot.get("missing_timeframes") != []:
        return fail("CANONICAL_BLOCKED", "El motor no publicó un análisis completo.")
    try:
        decision = _time(snapshot.get("decision_time"))
        age = (now - decision).total_seconds()
        result.update(decision_time=decision.isoformat(), age_seconds=round(age, 1))
        if age < 0:
            return fail("CANONICAL_FUTURE", "El análisis está fechado en el futuro.")
        if age > result["max_age_seconds"]:
            return fail("CANONICAL_STALE", "El análisis ha vencido; esperando actualización del motor.")
        asofs = snapshot.get("asof_times_by_tf")
        if not isinstance(asofs, dict):
            raise ValueError("missing timeframe clocks")
        for tf, seconds in TF_SECONDS.items():
            close = _time(asofs.get(tf)).timestamp() + seconds
            if close > decision.timestamp():
                return fail("CANONICAL_UNCLOSED_BAR", f"{tf}: la vela no estaba cerrada al decidir.")
            max_age = 4 * 86400 if tf == "D1" else max(180, seconds * 2)
            if now.timestamp() - close > max_age:
                return fail("CANONICAL_TF_STALE", f"{tf}: velas cerradas desactualizadas.")
    except (ValueError, TypeError, OverflowError):
        return fail("CANONICAL_TIME_INVALID", "Falta un reloj válido con zona horaria en el análisis.")
    if connection.get("status") != "READY":
        return fail("CANONICAL_FEED_UNAVAILABLE", "Feed MT5 no vigente; el análisis anterior es histórico.")
    if engine.get("status") not in {"READY", "RUNNING"}:
        return fail("CANONICAL_ENGINE_UNAVAILABLE", "Motor no disponible: " + str(engine.get("error") or engine.get("status")))
    return {**result, "valid": True, "code": "PASS",
            "detail": f"Análisis canónico válido y vigente ({age:.0f} s). Solo lectura; no autoriza entradas."}
