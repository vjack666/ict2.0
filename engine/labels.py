"""engine/labels.py — ETIQUETADO DE RESULTADO (MIRA EL FUTURO).

============================================================================
ESTE MÓDULO MIRA EL FUTURO.
============================================================================
`engine/labels.py` es el ÚNICO lugar autorizado del motor (engine/) para
indexar barras POR DELANTE (slicing `i+1:`). Las etiquetas que produce son
puramente DESCRIPTIVAS del desenlace de un evento ya decidido por
`detect_market_structure` (que vive en el pasado/presente, sin look-ahead).

Contrato anti-look-ahead (Ley 12 / Ley 1):
  - `detect_market_structure` (engine/bos/structure.py) toma TODAS las
    decisiones de mercado con `_consecutive_break` (solo presente/pasado) y
    NUNCA mira `i+1:`.
  - Al final, UNA vez decidido el evento, llama a este módulo SOLO para
    anotar columnas con prefijo reservado `label_*` (desenlace informativo:
    si el nivel fue roto en `k` velas, score de confirmación, motivo de
    descarte). Esas columnas son OBSERVABILIDAD, no entrada a ninguna
    decisión causal.
  - Ningún otro archivo de `engine/` puede contener slicing `[i + 1 :]`
    (ver tests/test_labels_isolation.py).

Regresión cero: las columnas de DECISIÓN (`bos_dir`, `bos_status`,
`bos_discard_reason`, `bos_quality_score`, `bos_real`, `choch_*`, etc.)
mantienen EXACTAMENTE el mismo nombre y valor que antes de extraer este
módulo. Aquí solo se AÑADEN alias `label_*` (columnas duplicadas) que la
fase de transición deja convivir; el consumidor aguas arriba no las usa
para decidir, por lo que no hay cambio de comportamiento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Marca de este módulo: el único que mira el futuro en engine/.
USES_FUTURE = True

BOS_DISCARD_REASONS = ("NO_HIT_IN_K", "INVALIDATED", "UNRESOLVED")
CHOCH_DISCARD_REASONS = ("NO_CONFIRMATION", "INVALIDATED", "UNRESOLVED")


def label_bos_outcome(
    d: pd.DataFrame,
    config,
    bos_discard: pd.Series,
) -> pd.Series:
    """Etiqueta el desenlace (hit / motivo de descarte) de cada BOS emitido.

    Mira `i+1:` para decidir si el nivel fue roto en `k` velas CERRADAS
    tras el evento. SOLO anota; no cambia ninguna decisión de estructura.

    Devuelve una Serie con los motivos de descarte idénticos a los que
    producía `_label_bos_discard` en structure.py (para regresión cero) y,
    además, deja el alias `label_bos_reason` en la columna `name` del
    resultado (se asigna por el llamador).
    """
    n = len(d)
    reasons = pd.Series([pd.NA] * n, index=d.index, dtype=object)
    highs = d["high"].to_numpy()
    lows = d["low"].to_numpy()
    bos_levels = d["bos_level"].to_numpy()
    bos_status = d["bos_status"].to_numpy()

    invalidated_mask = bos_status == "invalidated"
    reasons[bos_discard == "INVALIDATED"] = "INVALIDATED"

    active_mask = bos_status == "active"
    for i in np.where(active_mask)[0]:
        if pd.notna(reasons.iloc[i]):
            continue
        end = min(i + config.k, n)
        future_highs = highs[i + 1 : end] if i + 1 < n else np.array([], dtype=float)
        future_lows = lows[i + 1 : end] if i + 1 < n else np.array([], dtype=float)
        level = float(bos_levels[i])
        direction = int(d["bos_dir"].iat[i])
        hit = False
        if direction == 1 and len(future_highs) > 0:
            hit = bool(np.nanmax(future_highs) > level)
        elif direction == -1 and len(future_lows) > 0:
            hit = bool(np.nanmin(future_lows) < level)
        if not hit:
            reasons.iloc[i] = "NO_HIT_IN_K" if end < n else "UNRESOLVED"
    reasons.name = "label_bos_reason"
    return reasons


def label_choch_outcome(
    d: pd.DataFrame,
    config,
    choch_discard: pd.Series,
) -> pd.Series:
    """Etiqueta el desenlace de cada CHOCH emitido (solo anota)."""
    n = len(d)
    reasons = pd.Series([pd.NA] * n, index=d.index, dtype=object)
    choch_status = d["choch_status"].to_numpy()

    reasons[choch_discard == "INVALIDATED"] = "INVALIDATED"
    active_mask = choch_status == "active"
    for i in np.where(active_mask)[0]:
        end = min(i + config.confirm_bars + 1, n)
        if end < n:
            reasons.iloc[i] = "NO_CONFIRMATION"
        else:
            reasons.iloc[i] = "UNRESOLVED"
    reasons.name = "label_choch_reason"
    return reasons


def confirm_score(d: pd.DataFrame, i: int, k: int) -> float:
    """Score de confirmación posterior (0/1) para el BOS en el índice `i`.

    Mira `i+1:` (hasta `i+1+k`) para ver si el precio NO retornó al nivel
    roto de inmediato. Es puramente descriptivo (componente del
    `bos_quality_score`). Índices fuera de rango devuelven 0.0.
    """
    n = len(d)
    if i < 0 or i >= n:
        return 0.0
    direction = int(d["bos_dir"].iat[i])
    level = float(d["bos_level"].iat[i]) if "bos_level" in d.columns else float("nan")
    highs = d["high"].to_numpy()
    lows = d["low"].to_numpy()
    if k <= 0:
        return 0.0
    end = min(i + k + 1, n)
    if end <= i + 1:
        return 0.0
    fut = slice(i + 1, end)
    if direction == 1:
        return 1.0 if float(np.nanmin(lows[fut])) > level else 0.0
    if direction == -1:
        return 1.0 if float(np.nanmax(highs[fut])) < level else 0.0
    return 0.0
