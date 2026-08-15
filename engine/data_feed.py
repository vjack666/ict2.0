"""engine/data_feed.py — Carga de velas para el MOTOR (permanente).

Lee los parquet crudos de data/raw/<SYMBOL>_<TF>.parquet con columnas
time/open/high/low/close. El motor calcula SU propia estructura
(engine.bos.detect_market_structure) a partir de estas velas; NO aplica
features del backtest. Asi el motor es autónomo y el backtest desechable
lo consume. NUNCA importa ict_backtest/ (Ley).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"

_COLS = ["time", "open", "high", "low", "close"]


def load_tf(symbol: str, tf: str, data_dir: Path | str = DATA_DIR,
            start=None, end=None) -> pd.DataFrame:
    """Carga un TF crudo. Devuelve df con columnas time/open/high/low/close."""
    p = Path(data_dir) / f"{symbol}_{tf}.parquet"
    if not p.exists():
        return pd.DataFrame(columns=_COLS)
    df = pd.read_parquet(p)
    keep = [c for c in _COLS if c in df.columns]
    df = df[keep].copy()
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    if start is not None:
        df = df[df["time"] >= pd.to_datetime(start, utc=True, errors="coerce")]
    if end is not None:
        df = df[df["time"] <= pd.to_datetime(end, utc=True, errors="coerce")]
    df = df.sort_values("time").reset_index(drop=True)
    return df


def load_frames(symbol: str, timeframes: tuple[str, ...],
                data_dir: Path | str = DATA_DIR,
                start=None, end=None) -> dict[str, pd.DataFrame]:
    """Carga varios TF. Devuelve {tf: df}. Sin features del backtest."""
    return {tf: load_tf(symbol, tf, data_dir, start=start, end=end)
            for tf in timeframes}
