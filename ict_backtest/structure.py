"""ict_backtest/structure.py — Parte 1: clasificacion de estructura de mercado.

Detecta BULLISH / BEARISH / RANGING por temporalidad a partir de los
swing labels que ya calculan los detectores del proyecto (bos.py pone
`swing_label` = HH/HL/LH/LL). Esto es la base del esqueleto ICT:
toda regla (intradia PO3/Turtle Soup, scalping Silver Bullet) arranca
confirmando la estructura del HTF.

No es ML: es clasificacion deterministica por conteo de swing points.

Uso:
    from ict_backtest.structure import classify_structure
    regime = classify_structure(df["swing_label"].dropna().tolist())
    # -> "BULLISH" | "BEARISH" | "RANGING"
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence


def classify_structure(swing_labels: Sequence[str] | Iterable[str]) -> str:
    """Clasifica la estructura de una temporalidad.

    Regla (ver docs/ICT_RULEBOOK.md §1):
      - HH + HL -> BULLISH
      - LH + LL -> BEARISH
      - sino    -> RANGING (o transicional)

    Solo cuenta los labels que son HH/HL/LH/LL. Ignora 'NONE'/vacio.
    Requiere al menos 2 swings confirmados para no ruido.
    """
    counts = Counter(str(lbl).strip().upper() for lbl in swing_labels)
    hh = counts.get("HH", 0)
    hl = counts.get("HL", 0)
    lh = counts.get("LH", 0)
    ll = counts.get("LL", 0)

    has_bull = hh > 0 or hl > 0
    has_bear = lh > 0 or ll > 0

    if has_bull and not has_bear:
        return "BULLISH"
    if has_bear and not has_bull:
        return "BEARISH"
    if has_bull and has_bear:
        # Ambos presentes: decide por el mas reciente / predominante.
        bull_score = hh + hl
        bear_score = lh + ll
        if bull_score > bear_score:
            return "BULLISH"
        if bear_score > bull_score:
            return "BEARISH"
        return "RANGING"
    return "RANGING"


def classify_multi_tf(structures: dict[str, Sequence[str]]) -> dict[str, str]:
    """Clasifica varias temporalidades a la vez.

    structures: {"D1": [...labels...], "H4": [...], "M15": [...], ...}
    Devuelve {"D1": "BULLISH", "H4": "RANGING", ...}
    """
    return {
        tf: classify_structure(labels)
        for tf, labels in structures.items()
    }


def momentum_direction(swing_labels: Sequence[str] | Iterable[str]) -> str:
    """Direccion del ULTIMO swing confirmado (util para BOS/CHOCH).

    Mira los ultimos labels no-vacios y devuelve el sentido del ultimo
    movimiento de estructura: "UP" (HH/HL) o "DOWN" (LH/LL).
    """
    seq = [str(l).strip().upper() for l in swing_labels if str(l).strip().upper() not in ("", "NONE")]
    if not seq:
        return "NONE"
    last = seq[-1]
    if last in ("HH", "HL"):
        return "UP"
    if last in ("LH", "LL"):
        return "DOWN"
    return "NONE"


if __name__ == "__main__":
    # Smoke test rapido (sin pytest).
    ej = ["HH", "HL", "HH", "HL", "LL"]
    print("BULLISH?", classify_structure(["HH", "HL", "HH", "HL"]))
    print("BEARISH?", classify_structure(["LH", "LL", "LH", "LL"]))
    print("RANGING?", classify_structure(["HH", "LL"]))
    print("MIX last-down?", classify_structure(ej), momentum_direction(ej))
