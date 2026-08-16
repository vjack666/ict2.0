"""Quality score de BOS/CHOCH (geometria pura) — rescate aislado de SMC-SYSTEMS.

Fuente: SMC-SYSTEMS/engine/bos/structure.py::_compute_bos_quality.
Adaptado a tools/ (aislado). Score 0-1 + is_real (score >= threshold).

Componentes (todos geometria de mercado, SIN ATR):
  1. displacement previo en la direccion (0/1)        -> tools.displacement
  2. cuerpo de la vela de break / rango de esa vela   (0-1)
  3. distancia del close al nivel roto / rango prom   (0-1, cap)
  4. confirmacion posterior: no retorno inmediato    (0/1)

Pesa 0.25 c/u. is_real = score >= quality_threshold.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tools.displacement import detect_displacement, DisplacementConfig


@dataclass
class QualityConfig:
    quality_threshold: float = 0.5
    confirm_bars: int = 2
    range_period: int = 14
    disp_config: DisplacementConfig = None


def compute_quality(
    d: pd.DataFrame,
    bos_dir_col: str = "bos_dir",
    bos_level_col: str = "bos_level",
    config: QualityConfig | None = None,
) -> tuple[pd.Series, pd.Series]:
    if config is None:
        config = QualityConfig()
    if config.disp_config is None:
        config.disp_config = DisplacementConfig()

    n = len(d)
    quality = pd.Series(np.nan, index=d.index, dtype=float)
    real = pd.Series(False, index=d.index, dtype=bool)
    if n == 0:
        return quality, real

    disp = detect_displacement(d, config.disp_config)
    disp_bull = disp["displacement_bullish"].to_numpy()
    disp_bear = disp["displacement_bearish"].to_numpy()

    body = (d["close"] - d["open"]).abs().to_numpy()
    candle_range = (d["high"] - d["low"]).replace(0, np.nan).to_numpy()
    body_ratio = np.where(np.isfinite(candle_range), body / candle_range, 0.0)

    avg_range = (d["high"] - d["low"]).clip(lower=0.0).rolling(config.range_period, min_periods=1).mean().to_numpy()
    close = d["close"].to_numpy()
    bos_levels = d[bos_level_col].to_numpy() if bos_level_col in d.columns else np.full(n, np.nan)
    bos_dir = d[bos_dir_col].to_numpy() if bos_dir_col in d.columns else np.zeros(n, dtype=int)

    for i in np.where(bos_dir != 0)[0]:
        direction = int(bos_dir[i])
        level = float(bos_levels[i]) if not np.isnan(bos_levels[i]) else np.nan
        cr = float(avg_range[i]) if avg_range[i] > 1e-9 else float(candle_range[i]) if np.isfinite(candle_range[i]) else 1e-9
        if cr <= 0:
            cr = 1e-9

        # 1. displacement previo
        disp_flag = 0.0
        if direction == 1 and i > 0 and bool(disp_bull[i]):
            disp_flag = 1.0
        elif direction == -1 and i > 0 and bool(disp_bear[i]):
            disp_flag = 1.0

        # 2. cuerpo del break
        body_score = float(body_ratio[i])

        # 3. distancia del close al nivel roto / rango promedio
        if np.isnan(level):
            close_score = 0.0
        else:
            if direction == 1:
                close_dist = (close[i] - level) / cr
            else:
                close_dist = (level - close[i]) / cr
            close_score = float(np.clip(close_dist / 0.5, 0.0, 1.0))

        # 4. confirmacion posterior (no retorno inmediato)
        confirm_score = 0.0
        if config.confirm_bars > 0 and i + config.confirm_bars < n:
            if direction == 1:
                confirm_score = 1.0 if close[i + config.confirm_bars] > level else 0.0
            else:
                confirm_score = 1.0 if close[i + config.confirm_bars] < level else 0.0

        score = disp_flag * 0.25 + body_score * 0.25 + close_score * 0.25 + confirm_score * 0.25
        quality.iloc[i] = float(np.clip(score, 0.0, 1.0))
        real.iloc[i] = quality.iloc[i] >= config.quality_threshold

    return quality, real
