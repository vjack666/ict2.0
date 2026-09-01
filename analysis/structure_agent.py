from __future__ import annotations

from typing import Any

import pandas as pd

from .base import AnalysisResult


class StructureAgent:
    name: str = "STRUCTURE"

    def __init__(self, lookback: int = 30) -> None:
        self.lookback = lookback

    def analyze(self, context: pd.DataFrame, index: int) -> AnalysisResult:
        start = max(0, index - self.lookback)
        window = context.iloc[start : index + 1].reset_index(drop=True)
        row = window.iloc[-1]
        events: list[dict[str, Any]] = []
        evidence: dict[str, Any] = {}

        trend = self._detect_trend(window)
        evidence["trend"] = trend

        swing_counts = self._count_swing_labels(window)
        evidence["swing_label_counts"] = swing_counts
        if swing_counts["hh"] >= 2:
            events.append({"type": "CONSECUTIVE_HH", "count": swing_counts["hh"]})
        if swing_counts["ll"] >= 2:
            events.append({"type": "CONSECUTIVE_LL", "count": swing_counts["ll"]})

        regime = str(row.get("market_regime", "RANGING"))
        evidence["regime"] = regime

        vol_regime = str(row.get("volatility_regime", "RANGING"))
        evidence["volatility_regime"] = vol_regime

        trend_confidence = float(row.get("trend_confidence", 0.0))
        evidence["trend_confidence"] = trend_confidence

        mtf = self._detect_mtf(window, row)
        evidence["mtf"] = mtf
        if mtf["alignment"] == "BULLISH":
            events.append({"type": "MTF_BULLISH", "detail": mtf})
        elif mtf["alignment"] == "BEARISH":
            events.append({"type": "MTF_BEARISH", "detail": mtf})

        compression = float(row.get("range_compression", 1.0))
        evidence["range_compression"] = compression
        if compression < 0.6:
            events.append({"type": "RANGE_COMPRESSION", "ratio": round(compression, 2)})

        directional_eff = float(row.get("directional_efficiency", 0.0))
        evidence["directional_efficiency"] = directional_eff
        if directional_eff > 0.7:
            events.append({"type": "HIGH_DIRECTIONAL_EFFICIENCY", "value": round(directional_eff, 2)})

        bias = self._resolve_bias(trend, mtf)
        confidence = self._compute_confidence(trend_confidence, compression, directional_eff, len(events))

        return AnalysisResult(
            agent_name="STRUCTURE",
            bias=bias,
            confidence=confidence,
            detected_events=events,
            evidence=evidence,
            invalidation_conditions=[],
        )

    def _detect_trend(self, window: pd.DataFrame) -> str:
        if "macro_direction" in window.columns:
            val = window["macro_direction"].iloc[-1]
            return str(val) if str(val) in ("BULLISH", "BEARISH") else "RANGING"
        return "RANGING"

    def _count_swing_labels(self, window: pd.DataFrame) -> dict[str, int]:
        counts: dict[str, int] = {"hh": 0, "hl": 0, "lh": 0, "ll": 0}
        if "swing_label" not in window.columns:
            return counts
        for label in window["swing_label"].dropna():
            lbl = str(label)
            if lbl == "HH":
                counts["hh"] += 1
            elif lbl == "HL":
                counts["hl"] += 1
            elif lbl == "LH":
                counts["lh"] += 1
            elif lbl == "LL":
                counts["ll"] += 1
        return counts

    def _detect_mtf(self, window: pd.DataFrame, row: pd.Series) -> dict[str, Any]:
        d1 = str(row.get("d1_direction", "RANGING"))
        h4 = str(row.get("h4_trend", "RANGING"))
        ltf = str(row.get("macro_direction", "RANGING"))
        bullish = sum(1 for v in (d1, h4, ltf) if v == "BULLISH")
        bearish = sum(1 for v in (d1, h4, ltf) if v == "BEARISH")
        if bullish >= 2:
            alignment = "BULLISH"
        elif bearish >= 2:
            alignment = "BEARISH"
        else:
            alignment = "RANGING"
        return {"d1": d1, "h4": h4, "ltf": ltf, "alignment": alignment}

    def _resolve_bias(self, trend: str, mtf: dict[str, Any]) -> str:
        if mtf.get("alignment") in ("BULLISH", "BEARISH"):
            return mtf["alignment"]
        if trend in ("BULLISH", "BEARISH"):
            return trend
        return "NEUTRAL"

    def _compute_confidence(self, trend_conf: float, compression: float, dir_eff: float, event_count: int) -> float:
        base = trend_conf * 0.4
        comp_bonus = max(0.0, (1.0 - compression) * 0.15) if compression < 0.8 else 0.0
        eff_bonus = dir_eff * 0.15
        event_bonus = min(event_count * 0.05, 0.15)
        return round(min(base + comp_bonus + eff_bonus + event_bonus, 0.95), 4)
