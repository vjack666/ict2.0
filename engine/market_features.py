"""engine/market_features.py — Cálculo de features del MOTOR (permanente).

Migrado desde ict_backtest/data_feed.py:build_features para que el motor sea
autónomo y el backtest desechable lo consuma (Ley: engine/ NUNCA importa
ict_backtest/). CERO imports de ict_backtest/.

Corre los detectores ICT puros (detectors/) + la estructura del motor
(engine.bos) y produce las columnas que el motor (engine._build_estructura /
sequence) espera:

  trend/macro_direction, bos_direction, bos_status, liquidity_sweep_up/down,
  fvg_state, ob_direction, atr (= avg_candle_range, rango high-low, fuente
  única de volatilidad; NO ATR), time, ohlc

Todo se calcula por TF. NO usa reloj de PC: la killzone la deriva el motor
del timestamp de cada vela.

El backtest (ict_backtest/data_feed.build_features) REENVÍA a esta función
para no duplicar lógica.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from detectors import detect_displacement, detect_fvg, detect_liquidity, detect_order_blocks
from engine._util import avg_candle_range
from engine.bos import StructureConfig, detect_market_structure


def _fvg_state(row: pd.Series) -> str:
    if bool(row.get("fvg_bullish", False)):
        return "bullish"
    if bool(row.get("fvg_bearish", False)):
        return "bearish"
    return "-"


def _ob_dir(row: pd.Series) -> str:
    if bool(row.get("ob_bullish", False)):
        return "bullish"
    if bool(row.get("ob_bearish", False)):
        return "bearish"
    return "-"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Corre detectores ICT sobre un frame OHLC y devuelve columnas del contrato."""
    d = df.copy().reset_index(drop=True)
    # --- Estructura canonica (BOS/CHOCH/trend) como UNICA fuente de verdad ---
    ms = detect_market_structure(d, StructureConfig(swing_lookback=5, confirm_bars=2))
    ms = ms.frame  # MarketStructure -> DataFrame anotado (contrato de columnas)
    d["bos_dir"] = ms["bos_dir"].astype(int).values
    d["choch_dir"] = ms["choch_dir"].astype(int).values
    d["bos_direction"] = (
        ms["bos_dir"].map({1: "BULLISH", -1: "BEARISH"}).fillna("NONE").astype(str).values
    )
    d["choch_signal"] = (
        ms["choch_dir"].map({1: "CHOCH_BULLISH", -1: "CHOCH_BEARISH"}).fillna("NONE").astype(str).values
    )
    d["bos_status"] = ms["bos_status"].where(ms["bos_dir"] != 0, "none").values
    d["choch_status"] = ms["choch_status"].values
    d["trend"] = ms["trend"].values
    d["swing_high"] = ms["swing_high"].values
    d["swing_low"] = ms["swing_low"].values
    d["swing_label"] = ms["swing_label"].values
    # Volatilidad/riesgo = FUENTE ÚNICA rango high-low (avg_candle_range), NO
    # ATR. La columna se sigue llamando "atr" por CONTRATO (object_adapter,
    # sequence.meta, translation la esperan con ese nombre).
    d["atr"] = avg_candle_range(d, window=50).to_numpy()
    f = detect_fvg(d)          # fvg_bullish, fvg_bearish, fvg_mid, ...
    d = f                      # PRESERVA las booleanas
    d["fvg_state"] = d.apply(_fvg_state, axis=1).values
    o = detect_order_blocks(d)  # ob_bullish, ob_bearish, ob_top/bottom, ...
    d = o                      # PRESERVA las booleanas
    d["ob_direction"] = d.apply(_ob_dir, axis=1).values
    # --- cruce FVG+OB y etiquetas de tipo/tier ---
    _rng = d["atr"] if "atr" in d.columns else pd.Series(0.0, index=d.index)
    tol = 0.3 * _rng.clip(lower=1e-9)
    fvg_b = d["fvg_bullish"].fillna(False).values
    fvg_be = d["fvg_bearish"].fillna(False).values
    _fvg_mid = d["fvg_mid"] if "fvg_mid" in d.columns else pd.Series(np.nan, index=d.index)
    fvg_mid_active = _fvg_mid.where(fvg_b | fvg_be).ffill()
    fvg_mid = fvg_mid_active.fillna(np.nan).values
    ob_up = d["ob_bullish"].fillna(False).values
    ob_dn = d["ob_bearish"].fillna(False).values
    ob_top = d["ob_top"].fillna(np.nan).values
    ob_bot = d["ob_bottom"].fillna(np.nan).values
    ob_dir = d["ob_direction"].values
    bos_dir = d["bos_dir"].fillna(0).values
    for i in range(len(d)):
        if ob_up[i] or ob_dn[i]:
            t = ob_top[i]
            b = ob_bot[i]
            if pd.isna(t) or pd.isna(b):
                continue
            in_ob = (not pd.isna(fvg_mid[i])) and (b <= fvg_mid[i] <= t)
            near_ob = (not pd.isna(fvg_mid[i])) and (
                abs(fvg_mid[i] - (t + b) / 2.0) <= tol[i])
            if in_ob or near_ob:
                d.at[i, "pd_tier"] = "T1"
            if (ob_dir[i] == 1 and bos_dir[i] == -1) or (ob_dir[i] == -1 and bos_dir[i] == 1):
                d.at[i, "pd_type"] = "BREAKER"
                if d.at[i, "pd_tier"] == "T2":
                    d.at[i, "pd_tier"] = "T1"
            if (not in_ob) and near_ob and d.at[i, "pd_type"] != "BREAKER":
                d.at[i, "pd_type"] = "MITIGATION_BLOCK"
                d.at[i, "pd_tier"] = "T3"
    d["choch_signal"] = d["choch_signal"]
    disp = detect_displacement(d)
    d["displacement_bullish"] = disp["displacement_bullish"].values
    d["displacement_bearish"] = disp["displacement_bearish"].values
    d["displacement_mag"] = disp["displacement_magnitude"].values
    liq = detect_liquidity(d)
    d["bsl_price"] = liq["bsl_price"].values
    d["ssl_price"] = liq["ssl_price"].values
    # Niveles de la MECHA del sweep (SL estructural, sin look-ahead).
    from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
    swept = canonical_sweep(d, lookback=DEFAULT_SWEEP_LOOKBACK)
    d["liquidity_sweep_up"] = swept["liquidity_sweep_up"].values
    d["liquidity_sweep_down"] = swept["liquidity_sweep_down"].values
    d["sweep_low"] = _sweep_level(cast(pd.Series, swept["liquidity_sweep_down"]),
                                  cast(pd.Series, d["low"]))
    d["sweep_high"] = _sweep_level(cast(pd.Series, swept["liquidity_sweep_up"]),
                                   cast(pd.Series, d["high"]))
    return d


def _sweep_level(flag: pd.Series, price: pd.Series) -> pd.Series:
    """Nivel (low/high) de la vela que barrio la liquidez, con .shift(1) para
    que el motor lea el sweep YA CERRADO (sin look-ahead)."""
    return price.where(flag).shift(1)


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"


def load_tf(symbol: str, timeframe: str, data_dir: Path | str = DATA_DIR,
            start=None, end=None) -> pd.DataFrame:
    """Carga un parquet OHLC crudo y le agrega las features ICT."""
    path = Path(data_dir) / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")
    df = pd.read_parquet(path)
    if start is not None or end is not None:
        mask = pd.Series(True, index=df.index)
        if start is not None:
            mask &= df["time"] >= pd.Timestamp(start)
        if end is not None:
            mask &= df["time"] <= pd.Timestamp(end)
        df = df[mask]
    return build_features(df)


def load_frames(symbol: str, timeframes: tuple[str, ...],
                data_dir: Path | str = DATA_DIR,
                start=None, end=None) -> dict[str, pd.DataFrame]:
    """Carga varios TF con features. Devuelve {tf: df}."""
    return {tf: load_tf(symbol, tf, data_dir, start=start, end=end)
            for tf in timeframes}
