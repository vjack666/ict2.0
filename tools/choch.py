"""Herramienta CHOCH (individual, Fase 1) — evento de giro (aviso).

Envuelve detectors.choch.detect_choch de forma AISLADA (solo pandas,
ventanas 20/50 hardcodeadas; NO importa engine/). Emite CHOCH como evento
cartesiano con parent_id = swing roto (last_swing_high/low que rompió),
mismo patrón que BOS (linaje padre-hijo, SMC-SYSTEMS).

Teoría (02_MSS_CHOCH §0 #2, SPEC §8):
  CHOCH = primera ruptura del swing CONTRARIO (aviso de giro, no confirmación).
  En uptrend: rompe el HL del último BOS → LL.
  En downtrend: rompe el LH del último BOS → HH.

El filtro de tesis (tools.bos_filter no aplica directo a CHOCH porque la
regla de "a favor/en contra" es inversa; pero reusamos confirm_bars + fusión
+ HTF con la misma cascada). CHOCH a favor de sesgo HTF = continuación de
giro (MSS si luego hay BOS); en contra = Turtle Soup de giro.

Salida: ToolEvent por cada CHOCH con event_kind="event", parent_id del swing
roto, break_bar, price=nivel roto, status. Se escribe a data/learning/choch/.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from detectors.choch import detect_choch
from tools.base import SingleTool
from tools.event import ToolEvent


class CHOCHTool(SingleTool):
    tool_name = "choch"
    tf = "M5"

    def __init__(self, lookback: int = 20):
        # lookback usado solo para nombre; detect_choch usa 20/50 internas
        self.lookback = lookback
        self._counter = 0

    def _detect(self, df: pd.DataFrame, context: dict | None = None) -> pd.DataFrame:
        return detect_choch(df.copy())

    def _next_id(self, direction: int) -> str:
        self._counter += 1
        return f"CHOCH_{'UP' if direction == 1 else 'DN'}_{self._counter:04d}"

    def _to_events(self, df: pd.DataFrame, symbol: str, context: dict | None) -> list[ToolEvent]:
        events: list[ToolEvent] = []
        sig = df["choch_signal"]
        last_sh = df["last_swing_high"]
        last_sl = df["last_swing_low"]
        swing_ids: dict[int, str] = {}
        if context and "swing_ids" in context:
            swing_ids = context["swing_ids"]

        for i in range(len(df)):
            s = sig.iloc[i]
            if s in (None, "NONE", ""):
                continue
            direction = 1 if s == "CHOCH_BULLISH" else -1
            # nivel roto = last_swing opuesto
            level = float(last_sh.iloc[i]) if direction == 1 else float(last_sl.iloc[i])
            parent_id = ""
            if swing_ids:
                cand = [b for b in swing_ids if b < i]
                if cand:
                    parent_id = swing_ids[max(cand)]
            events.append(ToolEvent(
                bar_index=int(i),
                time=str(df["time"].iloc[i]) if "time" in df.columns else None,
                symbol=symbol,
                tf=self.tf,
                tool_name=self.tool_name,
                signal="CHOCH_UP" if direction == 1 else "CHOCH_DOWN",
                event_kind="event",
                id=self._next_id(direction),
                parent_id=parent_id,
                origin_bar=int(i),
                confirmation_bar=None,
                break_bar=int(i),
                price=level,
                detail=f"level={level:.5f} parent={parent_id}",
                confidence_raw=1.0,
                status="active",
            ))
        return events
