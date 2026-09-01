"""engine/_volume.py — Helper CENTRALIZADO de confirmación por volumen (MDS_VOLUMEN).

Única fuente de verdad (DRY) del patrón ya verificado en `engine/silver_bullet.py`
y `engine/turtle_soup.py`.

Reglas duras (AGENTS.md / MDS_VOLUMEN.md):
  - CERO indicadores. El volumen es el ÚNICO dato extra permitido y es dato
    crudo de mercado, no un indicador suavizado.
  - SOLO confirmación: se REPORTA un ratio (float). NUNCA se usa como gate,
    filtro booleano ni señal direccional.
  - Regresión cero: si no hay columna 'volume' devuelve None y la geometría
    existente no cambia.
  - `engine/` NUNCA importa `ict_backtest/`.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

__all__ = ["volume_confirm"]


def volume_confirm(df: pd.DataFrame, idx: int, window: int = 20) -> Optional[float]:
    """Confirmacion OPCIONAL por volumen (unico dato extra permitido, no indicador).

    Devuelve el ratio volumen[vela] / media(volumen ventana previa). None si no
    hay columna 'volume'. Ratio > 1 = participacion por encima de la media.
    NO es senal direccional ni indicador suavizado; es dato crudo de mercado.
    """
    if df is None or "volume" not in getattr(df, "columns", ()):
        return None
    if idx is None or idx < 0 or idx >= len(df):
        return None
    v = float(df["volume"].iloc[idx])
    lo = max(0, idx - window)
    prev = df["volume"].iloc[lo:idx]
    mean = float(prev.mean()) if len(prev) else 0.0
    if mean <= 0:
        return None
    return v / mean
