"""Herramienta SWING (individual, Fase 1).

Envuelve la lógica PURA de swings high/low (algoritmo autónomo, sin
dependencias de engine/ ni de detect_bos). Es la base de la futura
"plantilla de gráfico vela-a-vela": cada alto/bajo recibe una etiqueta
HH / LH / HL / LL según la tesis ICT.

CRITERIO DE AISLAMIENTO (ver veredicto Task 2): las funciones _swing_points
y _label_swings se REENVUELVEN aquí como puras (solo pandas/numpy), NO se
importa detectors.bos completo, para no arrastrar ATR/sweeps/BOS ni el
legado de engine/. Esto mantiene tools/ desacoplado.

Salida: ToolEvent por cada barra donde se marca un nuevo swing, con la
etiqueta y el nivel. Se escribe a data/learning/swing/<sym>_M5_<mes>.jsonl
(human_score=None hasta que el trader humano califique).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tools.base import SingleTool
from tools.event import ToolEvent


def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    """Pivots clásicos por ventana central. Solo la vela pivot lleva valor
    (NaN en el resto), SIN ffill, para que el consumidor sepa qué barra es
    realmente el alto/bajo."""
    window = lookback * 2 + 1
    rolling_high = frame["high"].rolling(window=window, center=True)
    rolling_low = frame["low"].rolling(window=window, center=True)
    swing_high = frame["high"].where(frame["high"] == rolling_high.max())
    swing_low = frame["low"].where(frame["low"] == rolling_low.min())
    return swing_high, swing_low


def _label_swings(swing_high: pd.Series, swing_low: pd.Series) -> pd.Series:
    """Etiqueta HH/LH/HL/LL SOLO en las velas pivot (donde swing_high/low
    no son NaN). El resto queda NaN."""
    labels = pd.Series([pd.NA] * len(swing_high), index=swing_high.index, dtype=object)
    new_high = swing_high.notna() & (swing_high != swing_high.shift(1))
    new_low = swing_low.notna() & (swing_low != swing_low.shift(1))
    prev_high = swing_high.where(new_high).ffill().shift(1)
    prev_low = swing_low.where(new_low).ffill().shift(1)
    labels[new_high & prev_high.isna()] = "HH"
    labels[new_high & (swing_high > prev_high)] = "HH"
    labels[new_high & (swing_high < prev_high)] = "LH"
    labels[new_low & prev_low.isna()] = "HL"
    labels[new_low & (swing_low > prev_low)] = "HL"
    labels[new_low & (swing_low < prev_low)] = "LL"
    return labels


class SwingTool(SingleTool):
    tool_name = "swing"
    tf = "M5"

    def __init__(self, lookback: int = 5):
        self.lookback = lookback

    def _detect(self, df: pd.DataFrame, context: dict | None = None) -> pd.DataFrame:
        data = df.copy()
        sh, sl = _swing_points(data, self.lookback)
        data["swing_high"] = sh
        data["swing_low"] = sl
        data["swing_label"] = _label_swings(sh, sl)
        return data

    def _to_events(self, df: pd.DataFrame, symbol: str, context: dict | None) -> list[ToolEvent]:
        events: list[ToolEvent] = []
        labels = df["swing_label"]
        sh = df["swing_high"]
        sl = df["swing_low"]
        for i in range(len(df)):
            # solo emitir en la vela que ES pivot (swing_high o swing_low no NA)
            is_pivot = (not pd.isna(sh.iloc[i])) or (not pd.isna(sl.iloc[i]))
            if not is_pivot:
                continue
            lab = labels.iloc[i]
            if pd.isna(lab) or str(lab) == "NONE":
                continue
            level = float(sh.iloc[i]) if not pd.isna(sh.iloc[i]) else float(sl.iloc[i])
            events.append(ToolEvent(
                bar_index=int(i),
                time=str(df["time"].iloc[i]) if "time" in df.columns else None,
                symbol=symbol,
                tf=self.tf,
                tool_name=self.tool_name,
                signal=f"SWING_{lab}",
                detail=f"level={level:.5f}",
                confidence_raw=1.0,
            ))
        return events
