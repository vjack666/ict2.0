"""Base de herramienta ICT individual (Fase 1).

Toda herramienta envuelve un detector existente en `detectors/` o `engine/`
y expone la interfaz común:

    run(df_m5, context) -> list[ToolEvent]

Además escribe su salida a un log append-only de aprendizaje
(`data/learning/<tool>/<sym>_M5_<mes>.jsonl`) para que el agente trader
humano + el Director califiquen (ver Fase 2 del plan).

Contexto: dict opcional con sesgo HTF (D1/H4/H1) ya leído de data/raw.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from tools.event import ToolEvent

ROOT = Path(__file__).resolve().parent.parent
LEARNING_DIR = ROOT / "data" / "learning"


class SingleTool(ABC):
    """Contrato de herramienta ICT individual (aislada, vela a vela)."""

    tool_name: str = ""          # p.ej. "bos", "choch", "fvg"
    tf: str = "M5"

    @abstractmethod
    def _detect(self, df: pd.DataFrame, context: dict | None = None) -> pd.DataFrame:
        """Llama al detector subyacente y devuelve DataFrame enriquecido."""
        raise NotImplementedError

    @abstractmethod
    def _to_events(self, df: pd.DataFrame, symbol: str, context: dict | None) -> list[ToolEvent]:
        """Convierte el DataFrame enriquecido en ToolEvents por barra."""
        raise NotImplementedError

    def run(self, df: pd.DataFrame, symbol: str = "", context: dict | None = None) -> list[ToolEvent]:
        enriched = self._detect(df.copy(), context)
        events = self._to_events(enriched, symbol, context)
        self._log(events, symbol, df)
        return events

    # ---- aprendizaje (Fase 2) ----
    def _month_tag(self, df: pd.DataFrame) -> str:
        if "time" in df.columns and len(df):
            try:
                t = pd.to_datetime(df["time"].iloc[0])
                return f"{t.year}-{t.month:02d}"
            except Exception:
                pass
        return "unknown"

    def _log_path(self, symbol: str, month: str) -> Path:
        sub = LEARNING_DIR / self.tool_name
        sub.mkdir(parents=True, exist_ok=True)
        return sub / f"{symbol}_{self.tf}_{month}.jsonl"

    def _log(self, events: list[ToolEvent], symbol: str, df: pd.DataFrame) -> None:
        """Append-only: cada evento como línea jsonl con human_score vacío.

        El agente trader humano llena human_score editando el .md de muestra
        (ver learning/export_review.py, Fase 2).
        """
        if not events:
            return
        month = self._month_tag(df)
        path = self._log_path(symbol, month)
        with path.open("a", encoding="utf-8") as f:
            for ev in events:
                rec = ev.to_dict()
                rec["human_score"] = None   # pendiente de calificación humana
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
