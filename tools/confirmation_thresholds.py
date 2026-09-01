"""Umbrales de confirmación calibrados — single source of truth.

Calibración 2026-08-17 (evidencia: eventos EURUSD M15/H1/H4/D1 + hallazgos Hermes
M5 ~92.8% reclaim). Documentación: docs/UMBRALES_CONFIRMACION.md y
.hermes-worklog/2026-08-17_1300_CALIBRACION_UMBRALES_CONFIRMACION.md

Tres modos:
  SCAN     — detección / log de aprendizaje (no tirar eventos)
  CONFIRM  — nature label y score de calidad
  PREMIUM  — único nivel que puede modular bias del motor

Clases de score (choch_class / teacher klass):
  premium >= SCORE_PREMIUM (90)
  useful  SCORE_USEFUL..SCORE_PREMIUM-1 (70-89)
  noise   < SCORE_USEFUL
"""
from __future__ import annotations

from typing import Dict

# --- Clases de score híbrido / rúbrica teacher ---
SCORE_PREMIUM: float = 90.0
SCORE_USEFUL: float = 70.0

# --- Excursión mínima en múltiplos del rango medio (R) ---
EXCURSION_K_SCAN: Dict[str, float] = {
    "M5": 2.0,
    "M15": 2.0,
    "H1": 1.8,
    "H4": 1.5,
    "D1": 1.0,
}

EXCURSION_K_CONFIRM: Dict[str, float] = {
    "M5": 4.5,
    "M15": 4.0,
    "H1": 5.0,
    "H4": 3.0,
    "D1": 2.0,
}

EXCURSION_K_PREMIUM: Dict[str, float] = {
    "M5": 6.0,
    "M15": 6.0,
    "H1": 8.0,
    "H4": 4.0,
    "D1": 3.0,
}

# Alias: label_ep / nature confirm usan modo CONFIRM por defecto
EXCURSION_K: Dict[str, float] = dict(EXCURSION_K_CONFIRM)

# Horizontes nature / label (velas posteriores)
NATURE_HORIZON: Dict[str, int] = {
    "M5": 50,
    "M15": 40,
    "H1": 30,
    "H4": 20,
    "D1": 10,
}

# Edad máxima del swing padre (barras) para gates opcionales
PARENT_AGE_MAX: Dict[str, int] = {
    "M15": 20,
    "H1": 30,
    "H4": 40,
    "D1": 30,
}

# Política bias (engine/bias_from_tools)
# CHOCH solo mueve bias si clase == premium (nunca noise/useful solos)
BIAS_CHOCH_MIN_CLASS: str = "premium"


def choch_class_from_score(score: float) -> str:
    """Clase canónica a partir de score 0-100."""
    if score >= SCORE_PREMIUM:
        return "premium"
    if score >= SCORE_USEFUL:
        return "useful"
    return "noise"


def excursion_k(tf: str, mode: str = "confirm") -> float:
    """k de excursión por TF y modo (scan|confirm|premium)."""
    tf_u = str(tf).upper()
    mode_l = (mode or "confirm").lower()
    table = {
        "scan": EXCURSION_K_SCAN,
        "confirm": EXCURSION_K_CONFIRM,
        "premium": EXCURSION_K_PREMIUM,
    }.get(mode_l, EXCURSION_K_CONFIRM)
    return float(table.get(tf_u, EXCURSION_K_CONFIRM.get("M15", 4.0)))
