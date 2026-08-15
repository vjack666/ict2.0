"""Herramienta SWING (individual, Fase 1) — objeto geométrico PERSISTENTE.

Envuelve la lógica PURA de swings high/low (algoritmo autónomo, sin
dependencias de engine/ ni de detect_bos). Es la base de la futura
"plantilla de gráfico vela-a-vela cartesiana": cada alto/bajo es un objeto
persistente con su punto cartesiano (origin_bar, price) y su confirmación.

CRITERIO DE AISLAMIENTO (ver veredicto Task 2): las funciones _swing_points
y _label_swings se REENVUELVEN aquí como puras (solo pandas/numpy), NO se
importa detectors.bos completo, para no arrastrar ATR/sweeps/BOS ni el
legado de engine/.

DISEÑO CARTESIANO (ver veredicto Director 2026-08-15):
- SWING = objeto persistente: origin_bar (pivot), confirmation_bar (donde
  queda confirmado SIN look-ahead: origin_bar + lookback), price, id, status.
- El swing permanece "active" hasta que un BOS lo rompa (Task 3 marca break_bar).

Salida: ToolEvent por cada pivot real, con event_kind="object". Se escribe a
data/learning/swing/<sym>_M5_<mes>.jsonl (human_score=None hasta calificación).
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
        self._counter = 0

    def _detect(self, df: pd.DataFrame, context: dict | None = None) -> pd.DataFrame:
        data = df.copy()
        sh, sl = _swing_points(data, self.lookback)
        data["swing_high"] = sh
        data["swing_low"] = sl
        data["swing_label"] = _label_swings(sh, sl)
        return data

    def _next_id(self, lab: str) -> str:
        self._counter += 1
        kind = "SH" if "H" in str(lab) else "SL"
        return f"SW_{kind}_{self._counter:04d}"

    def _to_events(self, df: pd.DataFrame, symbol: str, context: dict | None) -> list[ToolEvent]:
        events: list[ToolEvent] = []
        labels = df["swing_label"]
        sh = df["swing_high"]
        sl = df["swing_low"]
        n = len(df)
        for i in range(n):
            is_pivot = (not pd.isna(sh.iloc[i])) or (not pd.isna(sl.iloc[i]))
            if not is_pivot:
                continue
            lab = labels.iloc[i]
            if pd.isna(lab) or str(lab) == "NONE":
                continue
            is_high = not pd.isna(sh.iloc[i])
            price = float(sh.iloc[i]) if is_high else float(sl.iloc[i])
            # confirmation_bar SIN look-ahead: el pivot queda confirmado
            # lookback velas después (ventana central ya no lo reetiqueta).
            conf = min(i + self.lookback, n - 1)
            events.append(ToolEvent(
                bar_index=int(i),
                time=str(df["time"].iloc[i]) if "time" in df.columns else None,
                symbol=symbol,
                tf=self.tf,
                tool_name=self.tool_name,
                signal=f"SWING_{lab}",
                event_kind="object",
                id=self._next_id(lab),
                origin_bar=int(i),
                confirmation_bar=int(conf),
                break_bar=None,
                price=price,
                detail=f"level={price:.5f} type={'HIGH' if is_high else 'LOW'}",
                confidence_raw=1.0,
                status="active",
            ))
        return events
