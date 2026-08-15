"""ict_backtest/object_adapter.py — Puente R9: frames <-> MarketObject[].

R9 (Migración del motor a MarketObject) — PASO 1 (puro, sin tocar strategy):

El objetivo de R9 es hacer que el motor consuma la ontología (MarketObject +
MarketNarrative) como representación interna canónica, manteniendo la interfaz
legacy de DataFrame a través de translation.py. Esta refactorización NO cambia
ninguna regla ICT: ni POI, ni sweep, ni BOS, ni entry, ni risk. Solo cambia el
TIPO DE DATO interno.

`objects_view(frames)` es el adaptador mínimo del Paso 1:
  frames (dict tf->df con features)
      -> build_objects (data_feed)        [df_to_objects: sella capa + rol]
      -> objects_to_legacy_df (translation)[reconstruye columnas derivadas]
      -> reensambla por bar_index sobre el df original (preserva time/OHLC/atr)
      -> frames equivalentes

Cada MarketObject lleva bar_index/bar_time (su vela de origen), así el df
resultante tiene EXACTAMENTE las mismas filas y columnas que lee hoy
sequence.py / market_structure.py / engine.py. sequence NO se toca.

Invariante que el test garantiza (Paso 2):
  run_sequence(frames)          ==  run_sequence(objects_view(frames))
  simulate_trade(...) sobre ambos -> mismo PF / WR / expectancy / DD.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ict_backtest.data_feed import build_objects
from ict_backtest.translation import objects_to_legacy_df


def objects_view(frames: dict[str, pd.DataFrame],
                 symbol: str = "") -> dict[str, pd.DataFrame]:
    """Reconstruye `frames` pasándolos por la capa de objetos (canónica).

    No altera ninguna regla ICT. Solo envuelve cada fila de cada TF en un
    MarketObject (sellando origin_tf + role + bar_index/bar_time) y vuelve a
    expandir las columnas derivadas (bos_dir, choch_dir, fvg_*, ob_*,
    macro_direction, zone_*) REENSAMBLADAS por bar_index sobre el df original,
    preservando time/OHLC/atr.

    El resultado es un dict tf->df con las MISMAS filas y columnas que el df de
    entrada. sequence.py lo consume sin saber que pasó por objetos.
    """
    objects = build_objects(frames, symbol=symbol)

    by_tf: dict[str, list[Any]] = {}
    for o in objects:
        by_tf.setdefault(o.origin_tf, []).append(o)

    out: dict[str, pd.DataFrame] = {}
    for tf, df in frames.items():
        objs_tf = by_tf.get(tf, [])
        merged = df.reset_index(drop=True).copy()
        if objs_tf:
            legacy = objects_to_legacy_df(objs_tf)
            # Reensamblar por bar_index: el df original ya trae esas columnas
            # desde los detectores, pero las reconstruimos DESDE el objeto para
            # probar la fidelidad del puente. Usamos bar_index como clave.
            legacy_idx = legacy.copy()
            legacy_idx["__bi"] = [int(o.bar_index) for o in objs_tf]
            # Asegurar que el df tenga una columna de índice de barra.
            if "bar_index" not in merged.columns:
                merged["bar_index"] = range(len(merged))
            for col in ("bos_direction", "choch_dir", "fvg_bullish", "fvg_bearish",
                        "ob_direction", "ob_bullish", "ob_bearish", "macro_direction",
                        "bos_status", "choch_status", "fvg_state", "ob_status",
                        "zone_high", "zone_low", "quality_score", "role", "type"):
                if col in legacy_idx.columns:
                    lut = dict(zip(legacy_idx["__bi"].tolist(),
                                   legacy_idx[col].tolist()))
                    merged[col] = merged["bar_index"].map(lut)
        out[tf] = merged
    return out


# Re-export para consumidores que quieran el paso único.
__all__ = ["objects_view"]
