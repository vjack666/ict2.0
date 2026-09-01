from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import AnalysisResult


class WyckoffAgent:
    name: str = "WYCKOFF"

    def __init__(self, lookback: int = 40, range_atr_threshold: float = 1.5) -> None:
        self.lookback = lookback
        self.range_atr_threshold = range_atr_threshold

    def analyze(self, context: pd.DataFrame, index: int) -> AnalysisResult:
        start = max(0, index - self.lookback)
        window = context.iloc[start : index + 1].reset_index(drop=True)
        row = window.iloc[-1]
        events: list[dict[str, Any]] = []
        evidence: dict[str, Any] = {}
        invalidation: list[str] = []
        n = len(window)

        phase = self._classify_phase(window)
        evidence["phase"] = phase

        if phase in ("ACCUMULATION", "ACCUMULATION_EARLY", "ACCUMULATION_LATE"):
            spring = self._detect_spring(window)
            if spring:
                events.append({"type": "SPRING", "detail": spring})
                evidence["spring"] = spring
                phase = "ACCUMULATION"

            sos = self._detect_sos(window)
            if sos:
                events.append({"type": "SOS", "detail": sos})
                evidence["sos"] = sos

            lps = self._detect_lps(window)
            if lps:
                events.append({"type": "LPS", "detail": lps})
                evidence["lps"] = lps

        elif phase in ("DISTRIBUTION", "DISTRIBUTION_EARLY", "DISTRIBUTION_LATE"):
            upthrust = self._detect_upthrust(window)
            if upthrust:
                events.append({"type": "UPTHRUST", "detail": upthrust})
                evidence["upthrust"] = upthrust
                phase = "DISTRIBUTION"

            sow = self._detect_sow(window)
            if sow:
                events.append({"type": "SOW", "detail": sow})
                evidence["sow"] = sow

            lpsy = self._detect_lpsy(window)
            if lpsy:
                events.append({"type": "LPSY", "detail": lpsy})
                evidence["lpsy"] = lpsy

        effort_result = self._detect_effort_result(window)
        evidence["effort_vs_result"] = effort_result
        if effort_result and effort_result.get("divergence"):
            events.append({"type": "EFFORT_RESULT_DIVERGENCE", "detail": effort_result})

        vol_regime = self._detect_volume_regime(window)
        evidence["volume_regime"] = vol_regime
        evidence["volume_confirmation"] = vol_regime in ("HIGH", "CLIMAX")

        stoch_exhaustion = self._detect_stochastic_exhaustion(window)
        if stoch_exhaustion:
            events.append({"type": stoch_exhaustion["type"], "detail": stoch_exhaustion})
            evidence["stoch_exhaustion"] = stoch_exhaustion
            if stoch_exhaustion.get("divergence"):
                events.append({"type": "STOCH_DIVERGENCE", "detail": stoch_exhaustion})

        confidence, bias = self._compute_confidence(phase, events, vol_regime, stoch_exhaustion)

        return AnalysisResult(
            agent_name="WYCKOFF",
            bias=bias,
            confidence=confidence,
            detected_events=events,
            evidence=evidence,
            invalidation_conditions=invalidation,
        )

    def _classify_phase(self, window: pd.DataFrame) -> str:
        n = len(window)
        if n < 10:
            return "UNKNOWN"

        high = window["high"].max()
        low = window["low"].min()
        mid = (high + low) / 2.0
        atr = float(window["atr"].iloc[-1]) if "atr" in window.columns else 1.0
        last_close = float(window["close"].iloc[-1])
        range_width = (high - low) / atr if atr > 1e-9 else 99.0

        if "swing_label" in window.columns:
            last_labels = window["swing_label"].dropna().unique()
            has_hh = any("HH" in str(l) for l in last_labels)
            has_ll = any("LL" in str(l) for l in last_labels)
            has_hl = any("HL" in str(l) for l in last_labels)
            has_lh = any("LH" in str(l) for l in last_labels)
        else:
            has_hh = has_ll = has_hl = has_lh = False

        prior_bias = str(window["macro_direction"].iloc[-1]) if "macro_direction" in window.columns else "RANGING"

        volume_high = self._volume_ratio(window) > 1.5 if "tick_volume" in window.columns else False

        in_range = range_width < self.range_atr_threshold * 2

        if in_range and prior_bias == "BEARISH" and (has_hl or last_close >= mid):
            if volume_high and last_close >= mid:
                return "ACCUMULATION_LATE"
            if has_ll:
                return "ACCUMULATION_EARLY"
            return "ACCUMULATION"

        if in_range and prior_bias == "BULLISH" and (has_lh or last_close <= mid):
            if volume_high and last_close <= mid:
                return "DISTRIBUTION_LATE"
            if has_hh:
                return "DISTRIBUTION_EARLY"
            return "DISTRIBUTION"

        if prior_bias == "BULLISH" and has_hh and not in_range:
            return "MARKUP"

        if prior_bias == "BEARISH" and has_ll and not in_range:
            return "MARKDOWN"

        return "UNKNOWN"

    def _volume_ratio(self, window: pd.DataFrame) -> float:
        if "tick_volume" not in window.columns:
            return 1.0
        vol = window["tick_volume"]
        current = float(vol.iloc[-1])
        avg = float(vol.iloc[:-1].mean()) if len(vol) > 1 else current
        return current / avg if avg > 1e-9 else 1.0

    def _detect_spring(self, window: pd.DataFrame) -> dict[str, Any] | None:
        n = len(window)
        if n < 5:
            return None
        lookback = min(n - 1, 10)
        support = window["low"].iloc[-lookback - 1 : -1].min()
        last = window.iloc[-1]
        current_low = float(last["low"])
        current_close = float(last["close"])
        prev_close = float(window.iloc[-2]["close"]) if n >= 2 else current_close
        spring = current_low < support and current_close > support
        volume_high = self._volume_ratio(window) > 1.5
        if spring:
            return {
                "low_vs_support": round((support - current_low) / (window["high"].max() - window["low"].min() + 1e-9), 4),
                "close_back_inside": current_close > support,
                "high_volume": volume_high,
            }
        return None

    def _detect_upthrust(self, window: pd.DataFrame) -> dict[str, Any] | None:
        n = len(window)
        if n < 5:
            return None
        lookback = min(n - 1, 10)
        resistance = window["high"].iloc[-lookback - 1 : -1].max()
        last = window.iloc[-1]
        current_high = float(last["high"])
        current_close = float(last["close"])
        upthrust = current_high > resistance and current_close < resistance
        volume_high = self._volume_ratio(window) > 1.5
        if upthrust:
            return {
                "high_vs_resistance": round((current_high - resistance) / (window["high"].max() - window["low"].min() + 1e-9), 4),
                "close_back_inside": current_close < resistance,
                "high_volume": volume_high,
            }
        return None

    def _detect_sos(self, window: pd.DataFrame) -> dict[str, Any] | None:
        n = len(window)
        if n < 5:
            return None
        last = window.iloc[-1]
        current_range = float(last["high"]) - float(last["low"])
        prior_avg_range = window["high"].iloc[-6:-1].sub(window["low"].iloc[-6:-1]).mean() if n >= 6 else current_range
        if prior_avg_range <= 1e-9:
            return None
        range_ratio = current_range / prior_avg_range
        close = float(last["close"])
        open_ = float(last["open"])
        body_ratio = abs(close - open_) / current_range if current_range > 1e-9 else 0.0
        volume_high = self._volume_ratio(window) > 1.5
        if range_ratio > 1.5 and body_ratio > 0.6 and volume_high and close > open_:
            return {"range_ratio": round(range_ratio, 2), "body_ratio": round(body_ratio, 2)}
        return None

    def _detect_sow(self, window: pd.DataFrame) -> dict[str, Any] | None:
        n = len(window)
        if n < 5:
            return None
        last = window.iloc[-1]
        current_range = float(last["high"]) - float(last["low"])
        prior_avg_range = window["high"].iloc[-6:-1].sub(window["low"].iloc[-6:-1]).mean() if n >= 6 else current_range
        if prior_avg_range <= 1e-9:
            return None
        range_ratio = current_range / prior_avg_range
        close = float(last["close"])
        open_ = float(last["open"])
        body_ratio = abs(close - open_) / current_range if current_range > 1e-9 else 0.0
        volume_high = self._volume_ratio(window) > 1.5
        if range_ratio > 1.5 and body_ratio > 0.6 and volume_high and close < open_:
            return {"range_ratio": round(range_ratio, 2), "body_ratio": round(body_ratio, 2)}
        return None

    def _detect_lps(self, window: pd.DataFrame) -> dict[str, Any] | None:
        n = len(window)
        if n < 8:
            return None
        last = window.iloc[-1]
        current_low = float(last["low"])
        prior_min = window["low"].iloc[-8:-1].min()
        volume_low = self._volume_ratio(window) < 0.7
        narrow_range = (float(last["high"]) - current_low) < self._avg_candle_range(window) * 0.8
        if current_low >= prior_min * 0.999 and volume_low and narrow_range:
            return {"pullback_to_support": True, "low_volume": volume_low}
        return None

    def _detect_lpsy(self, window: pd.DataFrame) -> dict[str, Any] | None:
        n = len(window)
        if n < 8:
            return None
        last = window.iloc[-1]
        current_high = float(last["high"])
        prior_max = window["high"].iloc[-8:-1].max()
        volume_low = self._volume_ratio(window) < 0.7
        narrow_range = (current_high - float(last["low"])) < self._avg_candle_range(window) * 0.8
        if current_high <= prior_max * 1.001 and volume_low and narrow_range:
            return {"bounce_to_resistance": True, "low_volume": volume_low}
        return None

    def _avg_candle_range(self, window: pd.DataFrame) -> float:
        if len(window) < 2:
            return 0.0
        return float((window["high"] - window["low"]).iloc[-5:].mean())

    def _detect_stochastic_exhaustion(self, window: pd.DataFrame) -> dict[str, Any] | None:
        if "stoch_k" not in window.columns or "stoch_d" not in window.columns:
            return None
        n = len(window)
        if n < 10:
            return None

        last_k = float(window["stoch_k"].iloc[-1])
        last_d = float(window["stoch_d"].iloc[-1])

        exhaustion_type = None
        bars_since_cross = None

        for i in range(1, min(6, n)):
            prev_k = float(window["stoch_k"].iloc[-i - 1])
            curr_k = float(window["stoch_k"].iloc[-i])
            if prev_k > 80.0 and curr_k <= 80.0:
                exhaustion_type = "BEARISH_EXHAUSTION"
                bars_since_cross = i
                break
            if prev_k < 20.0 and curr_k >= 20.0:
                exhaustion_type = "BULLISH_EXHAUSTION"
                bars_since_cross = i
                break

        if exhaustion_type is None:
            return None

        divergence = False
        div_lookback = min(14, n // 2)
        if n >= div_lookback * 2:
            recent = window.iloc[-div_lookback:]
            prior = window.iloc[-div_lookback * 2 : -div_lookback]

            recent_high = float(recent["high"].max())
            prior_high = float(prior["high"].max())
            recent_k_at_high = float(recent.loc[recent["high"].idxmax(), "stoch_k"])
            prior_k_at_high = float(prior.loc[prior["high"].idxmax(), "stoch_k"])

            recent_low = float(recent["low"].min())
            prior_low = float(prior["low"].min())
            recent_k_at_low = float(recent.loc[recent["low"].idxmin(), "stoch_k"])
            prior_k_at_low = float(prior.loc[prior["low"].idxmin(), "stoch_k"])

            bearish_div = recent_high > prior_high and recent_k_at_high < prior_k_at_high
            bullish_div = recent_low < prior_low and recent_k_at_low > prior_k_at_low
            divergence = bearish_div or bullish_div

        volume_confirmed = self._volume_ratio(window) > 1.5

        return {
            "type": exhaustion_type,
            "divergence": divergence,
            "volume_confirmed": volume_confirmed,
            "stoch_k": round(last_k, 4),
            "stoch_d": round(last_d, 4),
            "bars_since_cross": bars_since_cross,
        }

    def _detect_effort_result(self, window: pd.DataFrame) -> dict[str, Any] | None:
        n = len(window)
        if n < 5 or "tick_volume" not in window.columns:
            return None
        vol = window["tick_volume"].iloc[-3:]
        range_ = (window["high"] - window["low"]).iloc[-3:]
        avg_vol = window["tick_volume"].iloc[-6:-3].mean() if n >= 6 else vol.mean()
        avg_range = (window["high"] - window["low"]).iloc[-6:-3].mean() if n >= 6 else range_.mean()
        if avg_vol <= 1e-9 or avg_range <= 1e-9:
            return None
        vol_ratio = float(vol.mean()) / float(avg_vol)
        range_ratio = float(range_.mean()) / float(avg_range)
        divergence = vol_ratio > 1.5 and range_ratio < 0.8
        return {
            "volume_ratio": round(vol_ratio, 2),
            "range_ratio": round(range_ratio, 2),
            "divergence": divergence,
            "interpretation": "absorption" if divergence else "normal",
        }

    def _detect_volume_regime(self, window: pd.DataFrame) -> str:
        if "tick_volume" not in window.columns:
            return "UNKNOWN"
        vr = self._volume_ratio(window)
        if vr > 2.0:
            return "CLIMAX"
        if vr > 1.5:
            return "HIGH"
        if vr < 0.5:
            return "LOW"
        if vr < 0.7:
            return "DRYING"
        return "NORMAL"

    def _compute_confidence(
        self,
        phase: str,
        events: list[dict[str, Any]],
        vol_regime: str,
        exhaustion: dict[str, Any] | None = None,
    ) -> tuple[float, str]:
        phase_scores = {
            "ACCUMULATION": 0.35,
            "ACCUMULATION_EARLY": 0.25,
            "ACCUMULATION_LATE": 0.50,
            "DISTRIBUTION": 0.35,
            "DISTRIBUTION_EARLY": 0.25,
            "DISTRIBUTION_LATE": 0.50,
            "MARKUP": 0.55,
            "MARKDOWN": 0.55,
        }
        base = phase_scores.get(phase, 0.15)
        event_bonus = min(len(events) * 0.08, 0.25)
        vol_bonus = 0.05 if vol_regime in ("HIGH", "CLIMAX") else -0.05 if vol_regime == "DRYING" else 0.0
        exhaustion_bonus = 0.10 if (exhaustion and exhaustion.get("volume_confirmed")) else 0.05 if exhaustion else 0.0
        confidence = min(max(base + event_bonus + vol_bonus + exhaustion_bonus, 0.0), 0.95)

        if phase in ("MARKUP", "ACCUMULATION", "ACCUMULATION_LATE"):
            bias = "BULLISH"
        elif phase in ("MARKDOWN", "DISTRIBUTION", "DISTRIBUTION_LATE"):
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return round(confidence, 4), bias
