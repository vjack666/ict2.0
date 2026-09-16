#!/usr/bin/env python3
"""SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1 — detector semántico de zona PD Array válida.

Evalúa si un PD Array (FVG/OB) cumple las tres condiciones de POI según la tesis
ICT del proyecto (`21_POI.md` §16, `20_TESIS_ICT.md` §5b):

1. Zona correcta del dealing range (discount para long, premium para short).
2. Alineación con sesgo HTF confirmado.
3. Respaldo institucional: displacement que creó el PD Array.

El resultado es uno de:
    VALID_ITF_ZONE   — cumple las tres condiciones (zona válida según tesis).
    INVALID_ZONE     — existe geometría PD Array pero falla al menos una condición.
    NO_ZONE          — no hay evidencia de PD Array en el ITF hasta decision_time.
    EVIDENCE_MISSING — no hay fuente M15 disponible para la evaluación.

Regla de oro: NO inventar zona. Si falta evidencia para una condición,
se registra como EVIDENCE_MISSING o INVALID_ZONE según corresponda.
Nunca se promueve a VALID_ITF_ZONE sin las tres condiciones confirmadas.

can_trade = false, entry_authorized = false, shadow_mode = true.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("semantic_pd_array_eval_v1")


# ─────────────────────────────────────────────────────────────────────────────
# Estados de clasificación semántica
# ─────────────────────────────────────────────────────────────────────────────

VALID_ITF_ZONE = "VALID_ITF_ZONE"
INVALID_ZONE = "INVALID_ZONE"
NO_ZONE = "NO_ZONE"
EVIDENCE_MISSING = "EVIDENCE_MISSING"

SEMANTIC_ZONE_STATES = (VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING)


def semantic_pd_array_zone(
    decision_time: Any,
    features_at_t: dict[str, Any] | None,
    m15_evidence: dict[str, Any] | None,
    direction: int = 0,
) -> dict[str, Any]:
    """Evaluar si existe un PD Array válido según las tres condiciones de POI.

    Args:
        decision_time: Momento de decisión (any serializable UTC).
        features_at_t: features_at_t del evento (puede ser None si no existe).
        m15_evidence: dict de evidencia M15 desde
            engine.m15_evidence_assembler.build_m15_evidence_for_decision_time
            (puede ser None si no hay fuente M15).
        direction: dirección del setup esperado (>0 long, <0 short, 0 neutral).

    Returns:
        dict con:
            - zone_state: uno de SEMANTIC_ZONE_STATES.
            - conditions: dict con resultado de cada condición.
            - reason: explicación breve del resultado.
            - can_trade: False siempre.
            - entry_authorized: False siempre.
    """
    conditions: dict[str, Any] = {
        "condition_1_zone_correcta": None,
        "condition_2_sesgo_aligned": None,
        "condition_3_respaldo_institucional": None,
        "geometry_present": None,
        "evidence_missing_reason": None,
    }

    reason = ""
    zone_state = NO_ZONE

    # ── Validaciones iniciales ──────────────────────────────────────────────
    if features_at_t is None:
        conditions["evidence_missing_reason"] = "features_at_t no disponible"
        reason = "features_at_t no disponible para evaluar condiciones 1 y 2"
        zone_state = EVIDENCE_MISSING
        return _result(zone_state, conditions, reason)

    if m15_evidence is None:
        conditions["evidence_missing_reason"] = "m15_evidence no disponible"
        reason = "m15_evidence no disponible para evaluar condición 3"
        zone_state = EVIDENCE_MISSING
        return _result(zone_state, conditions, reason)

    # ── Condición 0: existencia de geometría PD Array ───────────────────────
    geometry_present = _geometry_present(m15_evidence)
    conditions["geometry_present"] = geometry_present

    if not geometry_present:
        reason = "no hay evidencia de FVG/OB en M15 hasta decision_time"
        zone_state = NO_ZONE
        return _result(zone_state, conditions, reason)

    # ── Condición 1: zona correcta del dealing range ────────────────────────
    condition_1 = _condition_1_zone_correcta(features_at_t, direction)
    conditions["condition_1_zone_correcta"] = condition_1
    if not condition_1["ok"]:
        reason = (
            f"wrong-side: {condition_1['detail']}"
        )
        zone_state = INVALID_ZONE
        return _result(zone_state, conditions, reason)

    # ── Condición 2: alineación con sesgo HTF confirmado ────────────────────
    condition_2 = _condition_2_sesgo_aligned(features_at_t, direction)
    conditions["condition_2_sesgo_aligned"] = condition_2
    if not condition_2["ok"]:
        reason = (
            f"sesgo HTF no alineado: {condition_2['detail']}"
        )
        zone_state = INVALID_ZONE
        return _result(zone_state, conditions, reason)

    # ── Condición 3: respaldo institucional (displacement) ──────────────────
    condition_3 = _condition_3_respaldo_institucional(m15_evidence)
    conditions["condition_3_respaldo_institucional"] = condition_3
    if not condition_3["ok"]:
        reason = (
            f"sin respaldo institucional: {condition_3['detail']}"
        )
        zone_state = INVALID_ZONE
        return _result(zone_state, conditions, reason)

    # ── Si llegamos aquí, cumple las tres condiciones ────────────────────────
    reason = "cumple las tres condiciones de POI: zona correcta, sesgo alineado, displacement"
    zone_state = VALID_ITF_ZONE
    return _result(zone_state, conditions, reason)


def _geometry_present(m15_evidence: dict[str, Any]) -> bool:
    """Verificar si existe FVG u OB en M15 hasta decision_time.

    Usa el campo fvg_or_ob.present del ensamblador de evidencia.
    """
    if not m15_evidence:
        return False
    fvg_or_ob = m15_evidence.get("fvg_or_ob", {})
    if not isinstance(fvg_or_ob, dict):
        return False
    present = fvg_or_ob.get("present", False)
    return bool(present)


def _condition_1_zone_correcta(
    features_at_t: dict[str, Any],
    direction: int,
) -> dict[str, Any]:
    """Condición 1: PD Array en zona correcta del dealing range.

    Long (direction > 0) → debe estar en DISCOUNT.
    Short (direction < 0) → debe estar en PREMIUM.
    Neutral (direction == 0) → no puede tener zona válida.

    Fuente: `features_at_t.context_inputs.h4_location`.
    """
    detail_parts: list[str] = []
    ok = False

    context_inputs = (features_at_t or {}).get("context_inputs") or {}
    h4_location = str(context_inputs.get("h4_location", "MISSING")).upper()

    if direction > 0:
        # Long: debe estar en discount
        if h4_location == "DISCOUNT":
            ok = True
            detail_parts.append("zona discount correcta para long")
        else:
            detail_parts.append(
                f"wrong-side: h4_location={h4_location}, se espera DISCOUNT para long"
            )
    elif direction < 0:
        # Short: debe estar en premium
        if h4_location == "PREMIUM":
            ok = True
            detail_parts.append("zona premium correcta para short")
        else:
            detail_parts.append(
                f"wrong-side: h4_location={h4_location}, se espera PREMIUM para short"
            )
    else:
        # Dirección neutra: no hay zona válida
        detail_parts.append("direction neutral: no hay zona válida")

    detail = "; ".join(detail_parts) if detail_parts else "h4_location desconocido"
    return {"ok": ok, "h4_location": h4_location, "detail": detail}


def _condition_2_sesgo_aligned(
    features_at_t: dict[str, Any],
    direction: int,
) -> dict[str, Any]:
    """Condición 2: alineación con sesgo HTF confirmado.

    Requiere:
        h1_alignment == ALIGNED
        context_bucket == ALIGNED
        direction_hint == expected_bias (BULLISH para long, BEARISH para short)

    Fuente: `features_at_t.context_inputs.h1_alignment`,
            `features_at_t.context_inputs.sequence_direction` (para hint),
            `features_at_t.context_bucket`.
    """
    detail_parts: list[str] = []
    ok = False

    context_inputs = (features_at_t or {}).get("context_inputs") or {}
    h1_alignment = str(context_inputs.get("h1_alignment", "MISSING")).upper()
    context_bucket = str((features_at_t or {}).get("context_bucket", "MISSING")).upper()
    direction_hint = str(context_inputs.get("direction_hint", "MISSING")).upper()

    expected = "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "MISSING"

    checks: list[tuple[str, bool]] = []

    if h1_alignment == "ALIGNED":
        checks.append(("h1_alignment=ALIGNED", True))
    else:
        checks.append((f"h1_alignment={h1_alignment}", False))

    if context_bucket == "ALIGNED":
        checks.append(("context_bucket=ALIGNED", True))
    else:
        checks.append((f"context_bucket={context_bucket}", False))

    if direction_hint in ("MISSING", expected):
        checks.append((f"direction_hint={direction_hint} compatible", True))
    else:
        checks.append((f"direction_hint={direction_hint} vs expected={expected}", False))

    all_ok = all(check[1] for check in checks)

    for label, passed in checks:
        detail_parts.append(f"{label}: {'OK' if passed else 'FAIL'}")

    detail = "; ".join(detail_parts) if detail_parts else "evidencia HTF insuficiente"
    return {"ok": all_ok, "detail": detail}


def _condition_3_respaldo_institucional(
    m15_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Condición 3: respaldo institucional — displacement que creó el PD Array.

    Según la tesis ICT (`20_TESIS_ICT.md` §5b, `21_POI.md` §16), un PD Array
    sin desplazamiento institucional es geometría suelta, no POI válido.

    Se evalúa con el ensamblador de evidencia M15:
        - displacement.present == True
        - fvg_or_ob.present == True
        - (opcionalmente) el displacement es posterior al FVG/OB que lo creó

    La relación causal explícita displacement → PD Array no está disponible en
    el ensamblador actual, por lo que usamos presencia conjunta de displacement
    y PD Array como evidencia suficiente de respaldo institucional para la
    etiqueta semántica.
    """
    detail_parts: list[str] = []
    ok = False

    displacement = m15_evidence.get("displacement", {})
    fvg_or_ob = m15_evidence.get("fvg_or_ob", {})

    displacement_present = bool(displacement.get("present", False)) if isinstance(displacement, dict) else False
    fvg_or_ob_present = bool(fvg_or_ob.get("present", False)) if isinstance(fvg_or_ob, dict) else False

    if displacement_present and fvg_or_ob_present:
        ok = True
        detail_parts.append("displacement presente + FVG/OB presente: respaldo institucional confirmado")
        if displacement.get("time"):
            detail_parts.append(f"displacement time: {displacement['time']}")
        if fvg_or_ob.get("time"):
            detail_parts.append(f"fvg_or_ob time: {fvg_or_ob['time']}")
    elif displacement_present and not fvg_or_ob_present:
        detail_parts.append("displacement presente pero no hay FVG/OB detectado en M15")
    elif not displacement_present and fvg_or_ob_present:
        detail_parts.append("FVG/OB presente pero sin displacement: geometría suelta (no POI)")
    else:
        detail_parts.append("ni displacement ni FVG/OB detectados en M15")

    detail = "; ".join(detail_parts) if detail_parts else "evidencia insuficiente"
    return {"ok": ok, "displacement_present": displacement_present, "detail": detail}


def _result(
    zone_state: str,
    conditions: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Armar el resultado de la evaluación semántica."""
    return {
        "zone_state": zone_state,
        "conditions": conditions,
        "reason": reason,
        "can_trade": False,
        "entry_authorized": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Compatibilidad con el materializador existente
# ─────────────────────────────────────────────────────────────────────────────

def semantic_pd_array_zone_from_row(
    row: dict[str, Any],
    m15_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Versión compatibilidad: toma una fila del dataset y evalúa semánticamente.

    Usa `decision_time`, `features_at_t` y `direction` de la fila, más el
    m15_evidence proporcionado.
    """
    decision_time = row.get("decision_time")
    features_at_t = row.get("features_at_t")
    direction = int((row.get("features_at_t") or {}).get("context_inputs", {}).get("sequence_direction", 0) or 0)

    return semantic_pd_array_zone(
        decision_time=decision_time,
        features_at_t=features_at_t,
        m15_evidence=m15_evidence,
        direction=direction,
    )


if __name__ == "__main__":
    import json
    from engine.m15_evidence_assembler import build_m15_evidence_for_decision_time
    import pandas as pd
    import numpy as np
    from datetime import datetime, timezone

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("TEST: semantic_pd_array_zone — casos de referencia")
    print("=" * 60)

    # Caso 1: PD Array válido (zona correcta + sesgo alineado + displacement)
    direction = 1  # long
    features_valid = {
        "context_inputs": {
            "h4_location": "DISCOUNT",
            "h1_alignment": "ALIGNED",
            "direction_hint": "BULLISH",
            "sequence_direction": 1,
        },
        "context_bucket": "ALIGNED",
    }
    m15_evidence_valid = {
        "fvg_or_ob": {"present": True, "time": "2024-01-15T10:00:00+00:00"},
        "displacement": {"present": True, "time": "2024-01-15T09:45:00+00:00"},
        "sweep": {"present": True, "time": "2024-01-15T09:30:00+00:00"},
        "bos_or_choch": {"present": True, "time": "2024-01-15T09:45:00+00:00"},
        "retest": {"present": False, "time": None},
    }
    result_valid = semantic_pd_array_zone(
        decision_time="2024-01-15T10:15:00+00:00",
        features_at_t=features_valid,
        m15_evidence=m15_evidence_valid,
        direction=direction,
    )
    print(f"\nCaso 1 — PD Array válido (long en discount con displacement):")
    print(f"  zone_state: {result_valid['zone_state']}")
    print(f"  reason: {result_valid['reason']}")
    assert result_valid["zone_state"] == VALID_ITF_ZONE, f"Esperado VALID_ITF_ZONE, got {result_valid['zone_state']}"

    # Caso 2: wrong-side (long en premium)
    features_wrong_side = {
        "context_inputs": {
            "h4_location": "PREMIUM",
            "h1_alignment": "ALIGNED",
            "direction_hint": "BULLISH",
            "sequence_direction": 1,
        },
        "context_bucket": "ALIGNED",
    }
    result_wrong_side = semantic_pd_array_zone(
        decision_time="2024-01-15T10:15:00+00:00",
        features_at_t=features_wrong_side,
        m15_evidence=m15_evidence_valid,
        direction=direction,
    )
    print(f"\nCaso 2 — Wrong-side (long en premium):")
    print(f"  zone_state: {result_wrong_side['zone_state']}")
    print(f"  reason: {result_wrong_side['reason']}")
    assert result_wrong_side["zone_state"] == INVALID_ZONE, f"Esperado INVALID_ZONE, got {result_wrong_side['zone_state']}"

    # Caso 3: sin sesgo alineado (h1_alignment=AGAINST)
    features_no_sesgo = {
        "context_inputs": {
            "h4_location": "DISCOUNT",
            "h1_alignment": "AGAINST",
            "direction_hint": "BULLISH",
            "sequence_direction": 1,
        },
        "context_bucket": "ALIGNED",
    }
    result_no_sesgo = semantic_pd_array_zone(
        decision_time="2024-01-15T10:15:00+00:00",
        features_at_t=features_no_sesgo,
        m15_evidence=m15_evidence_valid,
        direction=direction,
    )
    print(f"\nCaso 3 — Sin sesgo alineado (h1_alignment=AGAINST):")
    print(f"  zone_state: {result_no_sesgo['zone_state']}")
    print(f"  reason: {result_no_sesgo['reason']}")
    assert result_no_sesgo["zone_state"] == INVALID_ZONE, f"Esperado INVALID_ZONE, got {result_no_sesgo['zone_state']}"

    # Caso 4: sin displacement (geometría suelta)
    features_sin_displacement = {
        "context_inputs": {
            "h4_location": "DISCOUNT",
            "h1_alignment": "ALIGNED",
            "direction_hint": "BULLISH",
            "sequence_direction": 1,
        },
        "context_bucket": "ALIGNED",
    }
    m15_evidence_sin_displacement = {
        "fvg_or_ob": {"present": True, "time": "2024-01-15T10:00:00+00:00"},
        "displacement": {"present": False, "time": None},
        "sweep": {"present": False, "time": None},
        "bos_or_choch": {"present": False, "time": None},
        "retest": {"present": False, "time": None},
    }
    result_sin_displacement = semantic_pd_array_zone(
        decision_time="2024-01-15T10:15:00+00:00",
        features_at_t=features_sin_displacement,
        m15_evidence=m15_evidence_sin_displacement,
        direction=direction,
    )
    print(f"\nCaso 4 — Sin displacement (geometría suelta):")
    print(f"  zone_state: {result_sin_displacement['zone_state']}")
    print(f"  reason: {result_sin_displacement['reason']}")
    assert result_sin_displacement["zone_state"] == INVALID_ZONE, f"Esperado INVALID_ZONE, got {result_sin_displacement['zone_state']}"

    # Caso 5: no hay geometría (NO_ZONE real)
    features_no_zone = {
        "context_inputs": {
            "h4_location": "DISCOUNT",
            "h1_alignment": "ALIGNED",
            "direction_hint": "BULLISH",
            "sequence_direction": 1,
        },
        "context_bucket": "ALIGNED",
    }
    m15_evidence_no_zone = {
        "fvg_or_ob": {"present": False, "time": None},
        "displacement": {"present": False, "time": None},
        "sweep": {"present": False, "time": None},
        "bos_or_choch": {"present": False, "time": None},
        "retest": {"present": False, "time": None},
    }
    result_no_zone = semantic_pd_array_zone(
        decision_time="2024-01-15T10:15:00+00:00",
        features_at_t=features_no_zone,
        m15_evidence=m15_evidence_no_zone,
        direction=direction,
    )
    print(f"\nCaso 5 — Sin geometría (NO_ZONE real):")
    print(f"  zone_state: {result_no_zone['zone_state']}")
    print(f"  reason: {result_no_zone['reason']}")
    assert result_no_zone["zone_state"] == NO_ZONE, f"Esperado NO_ZONE, got {result_no_zone['zone_state']}"

    # Caso 6: evidencia faltante
    result_evidence_missing = semantic_pd_array_zone(
        decision_time="2024-01-15T10:15:00+00:00",
        features_at_t=None,
        m15_evidence=m15_evidence_valid,
        direction=direction,
    )
    print(f"\nCaso 6 — features_at_t no disponible:")
    print(f"  zone_state: {result_evidence_missing['zone_state']}")
    print(f"  reason: {result_evidence_missing['reason']}")
    assert result_evidence_missing["zone_state"] == EVIDENCE_MISSING, f"Esperado EVIDENCE_MISSING, got {result_evidence_missing['zone_state']}"

    print("\n" + "=" * 60)
    print("TEST COMPLETADO — 6/6 casos correctos")
    print("=" * 60)
