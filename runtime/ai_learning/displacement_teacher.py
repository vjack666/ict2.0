
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Profesor de desplazamiento ICT v1 — capas: geometría, episodio, contexto.

LOCAL_ONLY. Define las reglas del profesor para entrenar reconocimiento de
desplazamiento en tres capas, separando geometría de contexto ICT.

Estado: FASE1 — profesor coherente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class GeometricStrength(Enum):
    NONE = auto()
    WEAK = auto()
    STRONG = auto()
    UNKNOWN = auto()


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    NONE = auto()
    UNKNOWN = auto()


class IctContextStatus(Enum):
    SUPPORTED = auto()
    NOT_SUPPORTED = auto()
    PENDING = auto()
    UNKNOWN = auto()


@dataclass
class DisplacementProfile:
    geometric_strength: GeometricStrength
    direction: Direction
    ict_context_status: IctContextStatus
    body_to_range_ratio: float | None = None
    body_pips: float = 0.0
    range_pips: float = 0.0
    wick_ratio: float = 0.0
    start_time: int | None = None
    confirmation_time: int | None = None
    available_at: int | None = None
    duration_bars: int = 0
    probabilities: dict[str, float] = field(default_factory=dict)
    reasons: dict[str, Any] = field(default_factory=dict)


@dataclass
class DisplacementTeacherConfig:
    min_body_to_range_strong: float = 0.60
    min_body_to_range_weak: float = 0.50
    min_body_pips: float = 1.5
    max_wick_ratio: float = 0.40
    lookback_bars: int = 2
    min_history_bars: int = 5
    confirmation_bars: int = 1
    available_delay_bars: int = 0
    max_retracement_ratio: float = 0.50
    pip_size: float = 0.0001


class DisplacementTeacher:
    """
    Profesor de desplazamiento en 3 capas:
    1. GEOMETRÍA: características del movimiento
    2. EPISODIO: expansión direccional y confirmación
    3. CONTEXTO ICT: papel dentro del patrón ICT
    """

    def __init__(self, config: DisplacementTeacherConfig | None = None):
        self.config = config or DisplacementTeacherConfig()

    def evaluate(
        self,
        frame: Any,
        candle_idx: int,
        context: dict[str, Any] | None = None,
    ) -> DisplacementProfile:
        cfg = self.config
        row = frame.iloc[candle_idx]
        history = frame.iloc[max(0, candle_idx - cfg.lookback_bars):candle_idx]

        geometric = self._evaluate_geometry(frame, candle_idx, row, history, cfg)
        episode = self._evaluate_episode(frame, candle_idx, geometric, cfg)
        ict_context = self._evaluate_ict_context(candle_idx, context, cfg)

        return DisplacementProfile(
            geometric_strength=geometric.strength,
            direction=geometric.direction,
            ict_context_status=ict_context.status,
            body_to_range_ratio=geometric.body_to_range_ratio,
            body_pips=geometric.body_pips,
            range_pips=geometric.range_pips,
            wick_ratio=geometric.wick_ratio,
            start_time=episode.start_time,
            confirmation_time=episode.confirmation_time,
            available_at=episode.available_at,
            duration_bars=episode.duration_bars,
            probabilities={},
            reasons={
                "geometry": geometric.reasons,
                "episode": episode.reasons,
                "ict_context": ict_context.reasons,
            },
        )

    @dataclass
    class GeometryEvaluation:
        strength: GeometricStrength
        direction: Direction
        body_to_range_ratio: float | None = None
        body_pips: float = 0.0
        range_pips: float = 0.0
        wick_ratio: float = 0.0
        reasons: dict[str, Any] = field(default_factory=dict)

    def _evaluate_geometry(
        self, frame, candle_idx, row, history, cfg
    ) -> GeometryEvaluation:
        import pandas as pd
        
        reasons = {}

        if candle_idx < cfg.min_history_bars:
            return self.GeometryEvaluation(
                strength=GeometricStrength.UNKNOWN,
                direction=Direction.UNKNOWN,
                reasons={"history_insufficient": candle_idx},
            )
        reasons["history_ok"] = True

        body = abs(row["close"] - row["open"])
        bar_range = row["high"] - row["low"]

        if bar_range == 0 or pd.isna(bar_range):
            return self.GeometryEvaluation(
                strength=GeometricStrength.NONE,
                direction=Direction.NONE,
                reasons={"range_zero": True},
            )

        body_to_range_ratio = body / bar_range
        
        # Redondear para evitar problemas de precisión de punto flotante
        body_to_range_ratio = round(body_to_range_ratio, 6)
        body_pips = body / cfg.pip_size
        range_pips = bar_range / cfg.pip_size

        reasons["body_to_range_ratio"] = float(body_to_range_ratio)
        reasons["body_pips"] = float(body_pips)
        reasons["range_pips"] = float(range_pips)
        reasons["body"] = float(body)
        reasons["high"], reasons["low"] = float(row["high"]), float(row["low"])
        reasons["open"], reasons["close"] = float(row["open"]), float(row["close"])

        if body_to_range_ratio >= cfg.min_body_to_range_strong:
            strength = GeometricStrength.STRONG
            reasons["strength_reason"] = "cuerpo >= 60% del rango"
        elif body_to_range_ratio >= cfg.min_body_to_range_weak:
            strength = GeometricStrength.WEAK
            reasons["strength_reason"] = "cuerpo 50-60% del rango"
        else:
            strength = GeometricStrength.NONE
            reasons["strength_reason"] = f"cuerpo {body_to_range_ratio:.2%} < umbral débil"
            return self.GeometryEvaluation(
                strength=strength, direction=Direction.NONE,
                body_to_range_ratio=float(body_to_range_ratio),
                body_pips=float(body_pips), range_pips=float(range_pips),
                reasons=reasons,
            )

        upper_wick = row["high"] - max(row["open"], row["close"])
        lower_wick = min(row["open"], row["close"]) - row["low"]
        smaller_wick = min(upper_wick, lower_wick)
        wick_ratio = smaller_wick / bar_range if bar_range > 0 else 1.0

        reasons["wick_ratio"] = float(wick_ratio)
        reasons["upper_wick_ratio"] = float(upper_wick / bar_range) if bar_range > 0 else 0.0
        reasons["lower_wick_ratio"] = float(lower_wick / bar_range) if bar_range > 0 else 0.0

        if wick_ratio > cfg.max_wick_ratio:
            if strength == GeometricStrength.STRONG:
                reasons["strength_downgraded"] = "mecha grande reduce confianza"
                strength = GeometricStrength.WEAK
            elif strength == GeometricStrength.WEAK:
                reasons["strength_downgraded_to_none"] = "mecha grande + cuerpo moderado"
                return self.GeometryEvaluation(
                    strength=GeometricStrength.NONE, direction=Direction.NONE,
                    body_to_range_ratio=float(body_to_range_ratio),
                    body_pips=float(body_pips), range_pips=float(range_pips),
                    wick_ratio=float(wick_ratio), reasons=reasons,
                )

        prev_high = history["high"].max() if len(history) > 0 else row["high"]
        prev_low = history["low"].min() if len(history) > 0 else row["low"]

        reasons["prev_high"] = float(prev_high)
        reasons["prev_low"] = float(prev_low)

        is_bullish = row["close"] > prev_high and row["close"] > row["open"]
        is_bearish = row["close"] < prev_low and row["close"] < row["open"]

        if is_bullish:
            direction = Direction.UP
            reasons["direction"] = "alcista — cierre sobre máximo previo"
        elif is_bearish:
            direction = Direction.DOWN
            reasons["direction"] = "bajista — cierre bajo mínimo previo"
        else:
            direction = Direction.NONE
            reasons["direction"] = "sin ruptura clara de estructura previa"

        reasons["final"] = "geometry_evaluated"
        return self.GeometryEvaluation(
            strength=strength, direction=direction,
            body_to_range_ratio=float(body_to_range_ratio),
            body_pips=float(body_pips), range_pips=float(range_pips),
            wick_ratio=float(wick_ratio), reasons=reasons,
        )

    @dataclass
    class EpisodeEvaluation:
        strength: GeometricStrength
        direction: Direction
        start_time: int | None = None
        confirmation_time: int | None = None
        available_at: int | None = None
        duration_bars: int = 0
        reasons: dict[str, Any] = field(default_factory=dict)

    def _evaluate_episode(
        self, frame, candle_idx, geometry, cfg
    ) -> EpisodeEvaluation:
        import pandas as pd
        
        reasons = {}

        if geometry.strength == GeometricStrength.UNKNOWN:
            return self.EpisodeEvaluation(
                strength=geometry.strength, direction=geometry.direction,
                reasons={"episode": "no evaluable sin geometría"},
            )

        if geometry.strength == GeometricStrength.NONE:
            return self.EpisodeEvaluation(
                strength=geometry.strength, direction=geometry.direction,
                reasons={"episode": "geometría insuficiente para episodio"},
            )

        start_time = int(frame.iloc[candle_idx]["time"])
        available_at = start_time

        look_ahead = min(cfg.confirmation_bars + 2, len(frame) - candle_idx - 1)

        if look_ahead <= 0:
            return self.EpisodeEvaluation(
                strength=geometry.strength, direction=geometry.direction,
                start_time=start_time, confirmation_time=None,
                available_at=available_at, duration_bars=1,
                reasons={"confirmation": "pendiente — fin de datos", "episode_status": "CANDIDATE"},
            )

        direction_mult = 1 if geometry.direction == Direction.UP else -1
        net_advance = 0.0
        confirmed = False
        confirmation_idx = None
        bar_range_0 = frame.iloc[candle_idx]["high"] - frame.iloc[candle_idx]["low"]

        for i in range(1, look_ahead + 1):
            future_idx = candle_idx + i
            if future_idx >= len(frame):
                break

            future_row = frame.iloc[future_idx]
            close_diff = (future_row["close"] - frame.iloc[candle_idx]["close"]) * direction_mult

            if i > 1 and bar_range_0 > 0:
                prev_close = frame.iloc[future_idx - 1]["close"]
                retracement = abs(future_row["close"] - prev_close) / bar_range_0
                if retracement > cfg.max_retracement_ratio:
                    reasons[f"retracement_bar_{i}"] = float(retracement)

            net_advance += close_diff

            if close_diff > 0 and not confirmed:
                confirmed = True
                confirmation_idx = future_idx
                reasons[f"confirmation_bar_{i}"] = True

        duration_bars = (confirmation_idx or candle_idx) - candle_idx + 1

        if confirmed:
            reasons["episode_status"] = "CONFIRMED"
            reasons["net_advance_pips"] = float(net_advance * cfg.pip_size)
        else:
            reasons["episode_status"] = "CANDIDATE"
            reasons["no_follow_through"] = True
            reasons["not_invalidated"] = True

        return self.EpisodeEvaluation(
            strength=geometry.strength, direction=geometry.direction,
            start_time=start_time,
            confirmation_time=int(frame.iloc[confirmation_idx]["time"]) if confirmation_idx is not None else None,
            available_at=available_at, duration_bars=duration_bars,
            reasons=reasons,
        )

    @dataclass
    class IctContextEvaluation:
        status: IctContextStatus
        reasons: dict[str, Any] = field(default_factory=dict)

    def _evaluate_ict_context(
        self, candle_idx, context, cfg
    ) -> IctContextEvaluation:
        reasons = {}

        if context is None:
            return self.IctContextEvaluation(
                status=IctContextStatus.UNKNOWN,
                reasons={"context_available": False, "status": "UNKNOWN — sin contexto"},
            )

        reasons["context_available"] = True
        reasons["sweep_previo"] = context.get("sweep_previo", None)
        reasons["fvg_cercano"] = context.get("fvg_cercano", None)
        reasons["ob_cercano"] = context.get("ob_cercano", None)
        reasons["estructura_confirmada"] = context.get("estructura_confirmada", None)
        reasons["htf_sesgo"] = context.get("htf_sesgo", None)

        tiene_sweep = context.get("sweep_previo", False) is True
        tiene_pd = context.get("fvg_cercano", False) is True or context.get("ob_cercano", False) is True
        tiene_estructura = context.get("estructura_confirmada", False) is True

        sesgo = context.get("htf_sesgo", None)
        if sesgo == "BULLISH":
            sesgo_ok = True  # A sumar con geometría alcista
        elif sesgo == "BEARISH":
            sesgo_ok = True  # A sumar con geometría bajista
        else:
            sesgo_ok = None

        if tiene_sweep and (tiene_pd or tiene_estructura):
            return self.IctContextEvaluation(
                status=IctContextStatus.SUPPORTED,
                reasons={**reasons, "status": "SUPPORTED — narrativa ICT completa"},
            )

        if sesgo is not None and sesgo_ok is False:
            return self.IctContextEvaluation(
                status=IctContextStatus.NOT_SUPPORTED,
                reasons={**reasons, "status": "NOT_SUPPORTED — sesgo HTF contradice"},
            )

        fvg_pendiente = context.get("fvg_pendiente", False)
        if fvg_pendiente:
            return self.IctContextEvaluation(
                status=IctContextStatus.PENDING,
                reasons={**reasons, "status": "PENDING — FVG de 3 velas pendiente"},
            )

        return self.IctContextEvaluation(
            status=IctContextStatus.NOT_SUPPORTED,
            reasons={**reasons, "status": "NOT_SUPPORTED — geometría sin contexto ICT"},
        )


def validate_boundaries():
    """Validar fronteras del profesor."""
    import pandas as pd
    import numpy as np

    cfg = DisplacementTeacherConfig()
    teacher = DisplacementTeacher(cfg)

    casos = []

    for body_pct, label in [(0.49, "NONE"), (0.50, "WEAK"), (0.59, "WEAK"), (0.60, "STRONG"), (0.70, "STRONG")]:
        # body_pct es el ratio cuerpo/rango que queremos probar
        # Usamos: body = body_pct * range, y range = high - low
        bar_range = 0.01  # 100 pips de rango
        body = body_pct * bar_range
        frame = pd.DataFrame({
            "time": list(range(10)),
            "open": [1.0000] * 10,
            "high": [1.0000 + bar_range] * 10,
            "low": [1.0000] * 10,
            "close": [1.0000 + body] * 10,  # close dentro del body
        })
        profile = teacher.evaluate(frame, 5)
        casos.append({"body_pct": body_pct, "expected": label, "got": profile.geometric_strength.name})

    for direction, close_offset in [("UP", 0.002), ("DOWN", -0.002)]:
        frame = pd.DataFrame({
            "time": list(range(10)),
            "open": [1.0000] * 10,
            "high": [1.0000 + 0.003] * 10,
            "low": [1.0000 - 0.001] * 10,
            "close": [1.0000] * 10,
        })
        # Vela 5 con cierre rompiendo estructura previa
        if direction == "UP":
            frame.loc[5, "close"] = 1.0000 + 0.003 + 0.001  # rompe high previo
        else:
            frame.loc[5, "close"] = 1.0000 - 0.001 - 0.001  # rompe low previo
        profile = teacher.evaluate(frame, 5)
        casos.append({"direction_test": direction, "got": profile.direction.name})

    for wick_ratio_val, expected_strength in [(0.30, "STRONG"), (0.45, "WEAK"), (0.60, "NONE")]:
        # body_ratio = 0.60, wick_ratio = menor_wick / rango
        # Para obtener wick_ratio específico, ajustamos los extremos
        frame = pd.DataFrame({
            "time": list(range(10)),
            "open": [1.0000] * 10,
            "high": [1.0000 + 0.01] * 10,   # rango = 0.01
            "low": [1.0000] * 10,             # rango = 0.01
            "close": [1.0000 + 0.006] * 10,  # body = 0.006, body/range = 0.60
        })
        # Ajustar el máximo para controlar la mecha
        if wick_ratio_val <= 0.40:
            # Mecha pequeña -> fuerza mantener STRONG o WEAK
            frame.loc[5, "high"] = 1.0000 + 0.006 + 0.001  # upper wick = 0.001, wick_ratio = 0.001/0.01 = 0.10
        elif wick_ratio_val <= 0.50:
            frame.loc[5, "high"] = 1.0000 + 0.006 + 0.003  # upper wick = 0.003, wick_ratio = 0.003/0.01 = 0.30
        else:
            frame.loc[5, "high"] = 1.0000 + 0.006 + 0.006  # upper wick = 0.006, wick_ratio = 0.006/0.01 = 0.60
            frame.loc[5, "low"] = 1.0000 - 0.001  # lower wick pequeña
        profile = teacher.evaluate(frame, 5)
        casos.append({"wick_ratio_test": wick_ratio_val, "got_strength": profile.geometric_strength.name})

    for ctx_status, ctx in [
        ("UNKNOWN", None),
        ("SUPPORTED", {"sweep_previo": True, "fvg_cercano": True}),
        ("NOT_SUPPORTED", {"sweep_previo": False}),
        ("PENDING", {"fvg_pendiente": True}),
    ]:
        frame = pd.DataFrame({
            "time": list(range(10)),
            "open": [1.0000] * 10,
            "high": [1.0000 + 0.005] * 10,
            "low": [1.0000 - 0.001] * 10,
            "close": [1.0000 + 0.004] * 10,
        })
        profile = teacher.evaluate(frame, 5, context=ctx)
        casos.append({"ctx_test": ctx_status, "got": profile.ict_context_status.name})

    return casos


if __name__ == "__main__":
    import pandas as pd
    
    casos = validate_boundaries()
    print("=== VALIDACIÓN DE FRONTERAS ===")
    for c in casos:
        print(c)
    
    print("\n=== PRUEBA COMPLETA ===")
    frame = pd.DataFrame({
        "time": list(range(100)),
        "open": [1.0000 + i * 0.0001 for i in range(100)],
        "high": [1.0000 + i * 0.0001 + 0.0005 for i in range(100)],
        "low": [1.0000 + i * 0.0001 - 0.0005 for i in range(100)],
        "close": [1.0000 + i * 0.0001 for i in range(100)],
    })
    
    teacher = DisplacementTeacher()
    
    for i in range(10, 20):
        profile = teacher.evaluate(frame, i)
        print(f"Vela {i}: geom={profile.geometric_strength.name}, dir={profile.direction.name}, ctx={profile.ict_context_status.name}, body/ratio={profile.body_to_range_ratio:.2%}")
