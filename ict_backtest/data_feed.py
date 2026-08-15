"""ict_backtest/data_feed.py — Conector datos -> features -> motor.

Carga OHLC (parquet en data/raw), corre los detectores ICT del repo
(detect_bos, detect_trend, detect_fvg, detect_order_blocks) y produce
las columnas que el motor (engine._build_estructura) espera:

  trend/macro_direction, bos_direction, bos_status,
  liquidity_sweep_up/down, fvg_state, ob_direction, atr (= avg_candle_range,
  rango high-low, fuente unica de volatilidad; ver nota Fase 1), time, ohlc

Todo se calcula por TF (D1, H4, ...). NO usa reloj de PC: la killzone
la deriva el motor del timestamp de cada vela.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# El cálculo de features vive AHORA en el motor permanente (engine.market_features).
# El backtest (ict_backtest) LO CONSUME y reenvía; no duplica lógica (Ley:
# engine/ NUNCA importa ict_backtest/, y el backtest solo consume al motor).
from engine.market_features import build_features  # noqa: F401  (reexport del canon)
from engine._util import avg_candle_range  # noqa: F401  (fuente única de volatilidad)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"


# NOTA: build_features (cálculo de features ICT) y avg_candle_range (volatilidad)
# viven AHORA en el motor permanente (engine.market_features / engine._util) y se
# reexportan arriba. Este módulo SOLO provee los wrappers de CARGA de parquet
# (load_tf / load_frames / build_objects) que el backtest usa para alimentar al
# motor. No contiene lógica de detección: el backtest es consumidor puro.

def load_tf(symbol: str, timeframe: str, data_dir: Path | str = DATA_DIR,
            start=None, end=None) -> pd.DataFrame:
    """Carga un parquet OHLC y le agrega las features ICT (motor permanente).

    `start`/`end` (Timestamp/str opcional): filtran el parquet POR FECHA
    ANTES de `build_features` (ahorra I/O y computo en ventanas cortas).
    No altera ninguna columna ni la logica de senales (R1 intacto).
    """
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
    """Carga varios TF con features. Devuelve {tf: df}.

    `start`/`end` recortan cada TF ANTES de features (ventana, sin look-ahead).
    """
    return {tf: load_tf(symbol, tf, data_dir, start=start, end=end)
            for tf in timeframes}


def bias_from_trend(frames: dict[str, pd.DataFrame], htf: str) -> str:
    """Sesgo global = ultima tendencia del HTF (para el backtest completo).

    NOTA: esto es un sesgo estatico de fin de serie; para backtest honesto el
    motor lee la tendencia POR VELA via _build_estructura. Este helper solo da
    un default. El sesgo real por vela sale de la columna 'trend' de cada TF.
    """
    df = frames.get(htf)
    if df is None or len(df) == 0 or "trend" not in df.columns:
        return "NEUTRAL"
    return str(df["trend"].iloc[-1])


def build_objects(frames: dict[str, pd.DataFrame],
                 symbol: str = "") -> list:
    """Produce MarketObjects desde {tf: df} sellando la capa (origen + rol).

    NO borra columnas: build_features sigue devolviendo el df con las columnas
    que leen sequence/rules/engine/pipeline/ML/UI. Solo AGREGA la vista de
    objetos como fuente canonica, via translation.df_to_objects.

    Garantiza NO-ROMPER: los consumidores existentes siguen recibiendo las
    columnas de siempre (ver tests/test_compat_consumidores.py).
    """
    feature_frames: dict[str, pd.DataFrame] = {}
    for tf, df in frames.items():
        # Si ya trae features (columna bos_direction), no las recalcula.
        if "bos_direction" in df.columns:
            feature_frames[tf] = df
        else:
            feature_frames[tf] = build_features(df.copy())
    from ict_backtest.translation import df_to_objects
    return df_to_objects(feature_frames, symbol=symbol)


if __name__ == "__main__":
    fr = load_frames("XAUUSD", ("H4",))
    h4 = fr["H4"]
    print("H4 filas:", len(h4))
    print("cols clave:", [c for c in ("trend", "bos_direction", "bos_status",
          "liquidity_sweep_up", "liquidity_sweep_down", "fvg_state",
          "ob_direction", "atr") if c in h4.columns])
    print(h4[["time", "trend", "bos_direction", "bos_status", "fvg_state", "ob_direction"]].tail(3).to_string())
