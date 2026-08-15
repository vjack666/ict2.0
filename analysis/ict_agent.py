"""ICT agent — R7 consumer of precomputed structure features (not a motor).

Does NOT reimplement BOS/CHOCH/sweep/FVG/OB geometry. Those come from detectors
(or market_structure) already written into the context DataFrame columns.

Trade signals (entry/SL/TP) must come from ``ict_backtest.canonical.evaluate_signals``
(sequence). This agent only scores bias/confidence for the orchestrator vote.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import AnalysisResult

# R7: trade decisions live in ict_backtest.canonical (sequence). Do NOT import
# that package here — circular import (agents → ict_backtest → signals → agents).
CANONICAL_ENGINE = "sequence"


class ICTAgent:
    name: str = "ICT"

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.decision_engine = CANONICAL_ENGINE  # R7: document who decides trades

    def analyze(self, context: pd.DataFrame, index: int) -> AnalysisResult:
        """Read feature columns already present; do not invent structure."""
        row = context.iloc[index]
        events: list[dict[str, Any]] = []
        evidence: dict[str, Any] = {"decision_engine": CANONICAL_ENGINE}
        invalidation: list[str] = []
        start = max(0, index - self.lookback)
        window = context.iloc[start : index + 1]

        trend = self._read_trend(window)
        evidence["market_structure"] = trend

        bos = self._read_bos(window, trend)
        if bos:
            events.append({"type": "BOS", "direction": trend, "detail": bos})
            evidence["bos"] = bos

        choch = self._read_choch(window, trend)
        if choch:
            events.append({"type": "CHOCH", "direction": choch})
            evidence["choch"] = choch
            invalidation.append(f"CHOCH against {trend} trend — structure shift possible")

        sweep = self._read_sweep(window)
        if sweep:
            events.append({"type": "LIQUIDITY_SWEEP", "side": sweep})
            evidence["liquidity_sweep"] = sweep

        fvg = self._read_fvg(window)
        if fvg:
            events.append({"type": "FVG", "detail": fvg})
            evidence["fvg"] = fvg

        ob = self._read_ob(window)
        if ob:
            events.append({"type": "ORDER_BLOCK", "detail": ob})
            evidence["order_block"] = ob

        premium_discount = self._read_zone(row)
        evidence["zone"] = premium_discount

        displacement = self._read_displacement(window)
        if displacement:
            events.append({"type": "DISPLACEMENT", "direction": displacement})
            evidence["displacement"] = displacement

        mtf = self._read_mtf_alignment(context, index)
        evidence["mtf_alignment"] = mtf
        if mtf == "ALIGNED":
            events.append({"type": "MTF_ALIGNMENT", "detail": "HTF and LTF agree"})

        confidence, bias = self._compute_confidence(events, trend, premium_discount)

        return AnalysisResult(
            agent_name="ICT",
            bias=bias,
            confidence=confidence,
            detected_events=events,
            evidence=evidence,
            invalidation_conditions=invalidation,
        )

    # ------------------------------------------------------------------ readers
    # Only consume columns already produced by detectors / market_structure.

    def _read_trend(self, window: pd.DataFrame) -> str:
        if "swing_label" in window.columns:
            labels = window["swing_label"].dropna().unique()
            has_hh = any("HH" in str(l) for l in labels)
            has_ll = any("LL" in str(l) for l in labels)
            if has_hh and not has_ll:
                return "BULLISH"
            if has_ll and not has_hh:
                return "BEARISH"
        if "macro_direction" in window.columns:
            last = window["macro_direction"].iloc[-1]
            if str(last) in ("BULLISH", "BEARISH"):
                return str(last)
        if "trend" in window.columns:
            last = str(window["trend"].iloc[-1]).upper()
            if last in ("BULLISH", "BEARISH"):
                return last
        return "RANGING"

    def _read_bos(self, window: pd.DataFrame, trend: str) -> str | None:
        col = "bos_direction" if "bos_direction" in window.columns else (
            "bos_dir" if "bos_dir" in window.columns else None
        )
        if col is None:
            return None
        series = window[col].iloc[-3:] if len(window) >= 3 else window[col]
        try:
            bos = float(series.max())
        except (TypeError, ValueError):
            return None
        if trend == "BULLISH" and bos > 0:
            return "bullish_break"
        if trend == "BEARISH" and bos < 0:
            return "bearish_break"
        return None

    def _read_choch(self, window: pd.DataFrame, trend: str) -> str | None:
        if "choch_signal" in window.columns:
            recent = (
                window["choch_signal"].iloc[-5:].dropna().unique()
                if len(window) >= 5
                else window["choch_signal"].dropna().unique()
            )
            if trend == "BULLISH" and any("BEARISH" in str(c) for c in recent):
                return "BEARISH"
            if trend == "BEARISH" and any("BULLISH" in str(c) for c in recent):
                return "BULLISH"
            return None
        # market_structure style: choch_dir numeric
        if "choch_dir" in window.columns:
            try:
                v = float(window["choch_dir"].iloc[-1])
            except (TypeError, ValueError):
                return None
            if trend == "BULLISH" and v < 0:
                return "BEARISH"
            if trend == "BEARISH" and v > 0:
                return "BULLISH"
        return None

    def _read_sweep(self, window: pd.DataFrame) -> str | None:
        last = window.iloc[-1]
        if "liquidity_sweep_up" in window.columns and bool(last.get("liquidity_sweep_up", False)):
            return "buy_side"
        if "liquidity_sweep_down" in window.columns and bool(last.get("liquidity_sweep_down", False)):
            return "sell_side"
        if "recent_sweep_up" in window.columns and bool(last.get("recent_sweep_up", False)):
            return "buy_side_swept"
        if "recent_sweep_down" in window.columns and bool(last.get("recent_sweep_down", False)):
            return "sell_side_swept"
        return None

    def _read_fvg(self, window: pd.DataFrame) -> dict[str, Any] | None:
        last = window.iloc[-1]
        bullish = bool(last.get("fvg_bullish", False))
        bearish = bool(last.get("fvg_bearish", False))
        if not bullish and not bearish:
            if "fvg_fill_status" in window.columns:
                status = str(last.get("fvg_fill_status", "none"))
                if status != "none":
                    return {
                        "status": status,
                        "direction": "bullish" if "bullish" in status else "bearish",
                    }
            return None
        size = float(last.get("fvg_size", 0.0) or 0.0)
        atr = float(last.get("atr", 1.0) or 1.0)
        quality = min(size / atr, 1.0) if atr > 1e-9 else 0.0
        return {
            "direction": "bullish" if bullish else "bearish",
            "size_points": size,
            "quality": round(quality, 4),
        }

    def _read_ob(self, window: pd.DataFrame) -> dict[str, Any] | None:
        last = window.iloc[-1]
        bullish = bool(last.get("ob_bullish", False))
        bearish = bool(last.get("ob_bearish", False))
        if not bullish and not bearish:
            return None
        distance = float(last.get("ob_distance", 0.0) or 0.0)
        atr = float(last.get("atr", 1.0) or 1.0)
        proximity = distance / atr if atr > 1e-9 else 99.0
        return {
            "direction": "bullish" if bullish else "bearish",
            "distance_atr": round(proximity, 2),
        }

    def _read_zone(self, row: pd.Series) -> str:
        zone = row.get("premium_discount_zone", "NONE")
        return str(zone) if str(zone) != "NONE" else "UNKNOWN"

    def _read_displacement(self, window: pd.DataFrame) -> str | None:
        if len(window) < 1:
            return None
        last = window.iloc[-1]
        if bool(last.get("displacement_bullish", False)):
            return "BULLISH"
        if bool(last.get("displacement_bearish", False)):
            return "BEARISH"
        return None

    def _read_mtf_alignment(self, context: pd.DataFrame, index: int) -> str:
        row = context.iloc[index]
        macro = str(row.get("macro_direction", "RANGING"))
        d1 = str(row.get("d1_direction", row.get("trend", "RANGING")))
        if macro == d1 and macro in ("BULLISH", "BEARISH"):
            return "ALIGNED"
        if macro in ("BULLISH", "BEARISH") and d1 in ("BULLISH", "BEARISH"):
            return "PARTIAL"
        return "CONFLICTING"

    def _compute_confidence(
        self, events: list[dict[str, Any]], trend: str, zone: str
    ) -> tuple[float, str]:
        score = 0.0
        max_score = 0.0
        weights = {
            "BOS": 1.0,
            "CHOCH": 2.0,
            "LIQUIDITY_SWEEP": 2.0,
            "FVG": 2.0,
            "ORDER_BLOCK": 2.0,
            "DISPLACEMENT": 2.0,
            "MTF_ALIGNMENT": 3.0,
        }
        for e in events:
            w = weights.get(e["type"], 1.0)
            max_score += w
            score += w
        if max_score == 0.0:
            return 0.0, "NEUTRAL"
        raw = score / max_score
        zone_bonus = 0.05 if "OTE" in zone or "DISCOUNT" in zone or "PREMIUM" in zone else 0.0
        trend_bonus = 0.05 if trend in ("BULLISH", "BEARISH") else -0.05
        confidence = min(max(raw + zone_bonus + trend_bonus, 0.0), 0.95)
        if confidence >= 0.5 and trend in ("BULLISH", "BEARISH"):
            bias = trend
        else:
            bias = "NEUTRAL"
        return round(confidence, 4), bias
