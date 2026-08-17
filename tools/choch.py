"""Herramienta CHOCH (individual, Fase 1) — CORREGIDA segun tesis 02_MSS_CHOCH.

DEFINICION DE TESIS (§0 #2, §1):
  CHOCH = primera ruptura del swing CONTRARIO, idealmente del nivel del
  ultimo BOS. NO depende de medias moviles (ese era el bug de detectors.choch:
  rolling(50) da NaN en TFs grandes -> 0 CHOCH en D1/H4).

  - uptrend:  rompe el HL del ultimo BOS -> LL   (CHOCH_BEARISH = aviso de giro bajista)
  - downtrend: rompe el LH del ultimo BOS -> HH  (CHOCH_BULLISH = aviso de giro alcista)

IMPLEMENTACION AISLADA (reusa swings y BOS ya calculados):
  - SwingTool da swings etiquetados HH/HL/LH/LL (objeto persistente).
  - BOSTool da BOS (evento hijo) con su nivel y direccion.
  - CHOCH se define por ruptura del swing contrario al ultimo BOS vigente.
  - parent_id = swing roto (linaje padre-hijo, igual que BOS).

Salida: ToolEvent por cada CHOCH con event_kind="event", parent_id del swing
roto, break_bar, price=nivel roto, status. Se escribe a data/learning/choch/.

Nota: esta herramienta NO importa detectors.choch (bug de rolling(50) en TFs
grandes). Es logica pura de swings/BOS, aislada, sin engine/.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tools.base import SingleTool
from tools.event import ToolEvent


class CHOCHTool(SingleTool):
    tool_name = "choch"
    tf = "M5"

    def __init__(self, lookback: int = 5):
        self.lookback = lookback
        self._counter = 0

    def _detect(self, df: pd.DataFrame, context: dict | None = None) -> pd.DataFrame:
        # CHOCH no necesita columna propia; se deriva de swings + BOS via context.
        return df.copy()

    def _next_id(self, direction: int) -> str:
        self._counter += 1
        return f"CHOCH_{'UP' if direction == 1 else 'DN'}_{self._counter:04d}"

    def _to_events(self, df: pd.DataFrame, symbol: str, context: dict | None) -> list[ToolEvent]:
        events: list[ToolEvent] = []
        broken_levels: set[tuple] = set()  # (dir, level) anti-flood
        if not context:
            return events

        swings = context.get("swings", [])
        boses = context.get("boses", [])
        if not swings:
            return events

        closes = df["close"] if "close" in df.columns else None
        times = df["time"] if "time" in df.columns else None

        # swings ordenados por barra
        swings_sorted = sorted(swings, key=lambda e: (e.origin_bar if e.origin_bar is not None else 0))
        # boses vigentes (no invalidados) ordenados por break_bar
        boses_active = [b for b in boses if getattr(b, "status", "") != "invalidated"]
        boses_sorted = sorted(boses_active, key=lambda e: (e.break_bar if e.break_bar is not None else 0))

        # Para cada barra, determinar ultimo BOS vigente y romper su swing contrario
        for i in range(1, len(df)):
            # ultimo BOS ya roto antes de i
            last_bos = None
            for b in boses_sorted:
                bb = b.break_bar if b.break_bar is not None else b.bar_index
                if bb < i:
                    last_bos = b
                else:
                    break
            if last_bos is None:
                # No hay BOS previo: el fallback de swings (abajo) infiere la marea.
                # No hacemos continue: dejamos que bos_dir se determine por swings.
                pass

            # Determinar direccion de la marea (bos_dir):
            #  primario: ultimo BOS vigente (tesis canonica: CHOCH rompe nivel del ultimo BOS)
            #  fallback: estructura de swings si no hay BOS previo (TFs grandes / inicio)
            bos_dir = None
            if last_bos is not None:
                bos_dir = 1 if last_bos.signal == "BOS_UP" else -1
            else:
                # inferir de los ultimos 2 swings del mismo tipo
                last_hh = [s for s in swings_sorted if s.signal == "SWING_HH" and s.origin_bar is not None and s.origin_bar < i]
                last_ll = [s for s in swings_sorted if s.signal == "SWING_LL" and s.origin_bar is not None and s.origin_bar < i]
                if len(last_hh) >= 2 and last_hh[-1].price is not None and last_hh[-2].price is not None:
                    bos_dir = 1 if last_hh[-1].price > last_hh[-2].price else -1
                elif len(last_ll) >= 2 and last_ll[-1].price is not None and last_ll[-2].price is not None:
                    bos_dir = -1 if last_ll[-1].price < last_ll[-2].price else 1
            if bos_dir is None:
                continue

            # swing contrario al BOS (senales de SwingTool: SWING_HH/HL/LH/LL):
            #  BOS_UP (alcista) -> CHOCH bajista rompe HL (SWING_HL)
            #  BOS_DOWN (bajista) -> CHOCH alcista rompe LH (SWING_LH)
            target_type = "SWING_HL" if bos_dir == 1 else "SWING_LH"
            # encontrar ultimo swing de ese tipo antes de i
            last_swing = None
            for s in swings_sorted:
                if s.origin_bar is None or s.origin_bar >= i:
                    break
                if s.signal in (target_type, f"{target_type}_UP", f"{target_type}_DN"):
                    last_swing = s
            if last_swing is None or last_swing.price is None:
                continue

            level = float(last_swing.price)
            c = float(closes.iloc[i])
            # CHOCH_DOWN (giro bajista): cierra por debajo del HL
            if bos_dir == 1 and c < level:
                direction = -1
            # CHOCH_UP (giro alcista): cierra por encima del LH
            elif bos_dir == -1 and c > level:
                direction = 1
            else:
                continue

            # FIX 2026-08-17: un solo CHOCH por (dirección, nivel). Evita flood
            # mientras el precio sigue al otro lado del mismo HL/LH.
            key = (direction, round(level, 5))
            if key in broken_levels:
                continue
            # cruce real: barra previa no había cerrado del otro lado
            prev_c = float(closes.iloc[i - 1]) if i > 0 else c
            if direction == 1 and prev_c > level:
                continue
            if direction == -1 and prev_c < level:
                continue
            broken_levels.add(key)

            events.append(ToolEvent(
                bar_index=int(i),
                time=str(times.iloc[i]) if times is not None else None,
                symbol=symbol,
                tf=self.tf,
                tool_name=self.tool_name,
                signal="CHOCH_UP" if direction == 1 else "CHOCH_DOWN",
                event_kind="event",
                id=self._next_id(direction),
                parent_id=last_swing.id,
                origin_bar=int(i),
                confirmation_bar=None,
                break_bar=int(i),
                price=level,
                detail=f"level={level:.5f} parent={last_swing.id} last_bos={last_bos.id if last_bos is not None else 'NONE(swing-fallback)'}",
                confidence_raw=1.0,
                status="active",
            ))
        return events
