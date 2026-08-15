"""engine/turtle_soup.py — Turtle Soup (C3, PERMANENTE).

Rescatado de ict_backtest/setups/turtle_soup.py. Unica fuente del motor; el
backtest LO CONSUME. Ley: engine/ NUNCA importa ict_backtest/.

Geometria pura (sin indicadores): Turtle Soup = ir a buscar el BARRIDO del
maximo/minimo del DIA ANTERIOR (PDH/PDL) y revertir: el stop-hunt que falla y
continua en la direccion del trade. El volumen es confirmacion OPCIONAL del
sweep (participacion en el barrido), no indicador.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engine._volume import volume_confirm


def _coerce_ts(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tz else ts.tz_localize("UTC")


def _prev_day_ohlc(frames: dict[str, pd.DataFrame], ltf: str, sweep_ts: pd.Timestamp) -> dict | None:
    """(pdh, pdl) del DIA PREVIO al de sweep_ts en frames[ltf]."""
    if ltf not in frames:
        return None
    series = frames[ltf]
    times = pd.to_datetime(series["time"], utc=True, errors="coerce")
    if len(times) == 0:
        return None
    sweep_day = sweep_ts.normalize()
    mask_prev = times.dt.normalize() < sweep_day
    if not mask_prev.any():
        return None
    prev = series.loc[mask_prev]
    return {"pdh": float(prev["high"].max()), "pdl": float(prev["low"].min()),
            "n": int(mask_prev.sum())}


def _sweep_broke(sweep_row: pd.Series, meta_pd: dict, direction: int) -> tuple[bool, bool]:
    """¿El sweep rompio PDH (short) / PDL (long) del dia previo? -> (broke_pdh, broke_pdl)."""
    pdh = meta_pd["pdh"]
    pdl = meta_pd["pdl"]
    low = float(sweep_row.get("low", np.nan))
    high = float(sweep_row.get("high", np.nan))
    broke_pdl = direction == 1 and (not pd.isna(low)) and low < pdl
    broke_pdh = direction == -1 and (not pd.isna(high)) and high > pdh
    return bool(broke_pdh), bool(broke_pdl)


def _has_reversal(df_ltf: pd.DataFrame, sweep_idx: int, direction: int) -> bool:
    """Displacement opuesto AL sweep en ~20 velas (reversion). Cuerpo >= 0.6*rango."""
    n = len(df_ltf)
    if sweep_idx < 0 or sweep_idx >= n:
        return False
    end = min(n, sweep_idx + 21)
    window = df_ltf.iloc[sweep_idx:end]
    if len(window) == 0:
        return False
    rng = (window["high"] - window["low"]).replace(0, np.nan)
    avg_rng = float(rng.mean(skipna=True)) or 1e-6
    body = (window["close"] - window["open"]).to_numpy(dtype=float)
    if direction == 1:
        return bool(np.any(body > 0.6 * avg_rng))
    return bool(np.any(body < -0.6 * avg_rng))


def _volume_on_sweep(df: pd.DataFrame, idx: int, window: int = 20) -> float | None:
    """Confirmacion OPCIONAL por volumen del sweep (dato, no indicador)."""
    return volume_confirm(df, idx, window)


def is_turtle_soup(
    sweep_ts: Any,
    direction: int,
    frames: dict[str, pd.DataFrame],
    ltf: str = "M15",
) -> tuple[bool, dict]:
    """Detecta Turtle Soup (sweep PDH/PDL dia previo + reversion)."""
    meta = {"ts_broke_pdh": False, "ts_broke_pdl": False, "ts_reversal": False}
    ts = _coerce_ts(sweep_ts)
    if ts is None or ltf not in frames:
        return False, meta
    df_ltf = frames[ltf]
    times = pd.to_datetime(df_ltf["time"], utc=True, errors="coerce")
    exact = df_ltf.index[times == ts]
    if len(exact):
        sweep_idx = int(exact[0])
    else:
        prior = df_ltf.index[times <= ts]
        if len(prior) == 0:
            return False, meta
        sweep_idx = int(prior[-1])
    prev = _prev_day_ohlc(frames, ltf, ts)
    if prev is None:
        return False, meta
    sweep_row = df_ltf.iloc[sweep_idx]
    broke_pdh, broke_pdl = _sweep_broke(sweep_row, prev, direction)
    meta["ts_broke_pdh"] = broke_pdh
    meta["ts_broke_pdl"] = broke_pdl
    broke = broke_pdh or broke_pdl
    if broke:
        meta["ts_reversal"] = _has_reversal(df_ltf, sweep_idx, direction)
    confirmed = broke and meta["ts_reversal"]
    return bool(confirmed), meta


def flag_turtle_soup(signals: list, frames: dict[str, pd.DataFrame], ltf: str = "M15") -> list:
    """Anota turtle_confirmed / turtle_broke en cada senal (atributos dinamicos)."""
    for sig in signals:
        direction = int(getattr(sig, "direction", 0) or 0)
        if direction == 0:
            sig.turtle_confirmed = False
            sig.turtle_broke = False
            continue
        ts = None
        sweep_idx = getattr(sig, "sweep_at", None)
        if sweep_idx is not None and ltf in frames and 0 <= int(sweep_idx) < len(frames[ltf]):
            ts = frames[ltf].iloc[int(sweep_idx)]["time"]
        if ts is None:
            ts = getattr(sig, "time", None)
        if ts is None:
            sig.turtle_confirmed = False
            sig.turtle_broke = False
            continue
        ok, meta = is_turtle_soup(ts, direction, frames, ltf)
        sig.turtle_confirmed = bool(ok)
        sig.turtle_broke = bool(meta["ts_broke_pdh"] or meta["ts_broke_pdl"])
    return signals
