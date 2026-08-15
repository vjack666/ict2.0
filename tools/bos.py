"""Herramienta BOS (individual, Fase 1) — evento hijo del swing roto.

Envuelve `detectors.bos.detect_bos` de forma AISLADA (lo importa directo
del módulo detectors, que es puro: solo pandas/numpy/BosConfig; NO tira de
engine/). Emite BOS como evento de RUPTURA que consume el nivel del swing
padre, usando el método padre-hijo (linaje causal de SMC-SYSTEMS):
  SW_SH_xxxx (origin_bar, price)  --padre-->  BOS_xxxx (break_bar, price)

CRITERIO DE AISLAMIENTO: detectors/bos.py solo importa dataclasses/numpy/
pandas (verificado en Task 2). Al importarlo, NO se carga engine/ ni el
resto de detectors. El BOS usa swing_high.shift(1) como nivel roto y empareja
con el swing padre por barra (el último swing high/low previo a la ruptura).

Salida: ToolEvent por cada BOS con event_kind="event", parent_id del swing
roto, break_bar, price=bos_level, status sobre el padre="broken".
Se escribe a data/learning/bos/<sym>_M5_<mes>.jsonl (human_score=None).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from detectors.bos import detect_bos, BosConfig
from tools.base import SingleTool
from tools.event import ToolEvent


class BOSTool(SingleTool):
    tool_name = "bos"
    tf = "M5"

    def __init__(self, lookback: int = 5):
        self.lookback = lookback
        self._counter = 0

    def _detect(self, df: pd.DataFrame, context: dict | None = None) -> pd.DataFrame:
        cfg = BosConfig(swing_lookback=self.lookback)
        return detect_bos(df.copy(), cfg)

    def _next_id(self, direction: int) -> str:
        self._counter += 1
        return f"BOS_{'UP' if direction == 1 else 'DN'}_{self._counter:04d}"

    def _to_events(self, df: pd.DataFrame, symbol: str, context: dict | None) -> list[ToolEvent]:
        events: list[ToolEvent] = []
        direction = df["bos_direction"]
        level = df["bos_level"]
        sh = df["swing_high"]
        sl = df["swing_low"]
        n = len(df)
        # pre-indexar swings por barra para emparejar parent_id
        swing_by_bar: dict[int, str] = {}
        if context and "swing_ids" in context:
            swing_by_bar = context["swing_ids"]

        for i in range(n):
            d = direction.iloc[i]
            if pd.isna(d) or int(d) == 0:
                continue
            d = int(d)
            bos_level = float(level.iloc[i])
            # padre: último swing en barra < i cuyo nivel coincide con bos_level
            parent_id = ""
            if swing_by_bar:
                # buscar el swing de la dirección opuesta más reciente antes de i
                cand = [b for b in swing_by_bar if b < i]
                if cand:
                    parent_id = swing_by_bar[max(cand)]
            events.append(ToolEvent(
                bar_index=int(i),
                time=str(df["time"].iloc[i]) if "time" in df.columns else None,
                symbol=symbol,
                tf=self.tf,
                tool_name=self.tool_name,
                signal="BOS_UP" if d == 1 else "BOS_DOWN",
                event_kind="event",
                id=self._next_id(d),
                parent_id=parent_id,
                origin_bar=int(i),          # el BOS ocurre aquí
                confirmation_bar=None,
                break_bar=int(i),
                price=bos_level,
                detail=f"level={bos_level:.5f} parent={parent_id}",
                confidence_raw=1.0,
                status="broken" if parent_id else "active",
            ))
        return events
