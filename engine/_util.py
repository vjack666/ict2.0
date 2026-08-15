"""engine/_util.py — helpers compartidos del MOTOR (permanente).

Migrado desde ict_backtest/_util.py para que el motor sea autónomo y el
backtest desechable lo consuma (Ley: engine/ NUNCA importa ict_backtest/).
CERO imports de ict_backtest/. Solo pandas + numpy + stdlib.

Contiene la fuente única de volatilidad (avg_candle_range, rango high-low
puro, NO ATR) y las lecturas HTF closed-only (anti look-ahead cross-TF).
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def row_at_time(df: pd.DataFrame, t: Any, freq: Any = None) -> Any:
    """Devuelve la fila de `df` cuyo 'time' coincide con `t` (o la previa más
    cercana, búsqueda asof). Robusta a recortes de walk-forward donde el LTF y
    el HTF tienen rangos distintos.

    Si `freq` se indica, exige que la barra ya haya CERRADO (time + freq <= t)
    para evitar look-ahead cross-timeframe.
    """
    try:
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        cutoff = tt - pd.Timedelta(freq) if freq is not None else tt
        exact_idx = df.index[times == cutoff].to_numpy()
        if len(exact_idx):
            return df.iloc[int(exact_idx[0])]
        prior_idx = df.index[times <= cutoff].to_numpy()
        if len(prior_idx):
            return df.iloc[int(prior_idx[-1])]
    except Exception:
        pass
    return df.iloc[0]


def infer_tf_duration(df: pd.DataFrame) -> str:
    """Infiere la duracion de barra de `df` desde la diferencia de tiempo de
    sus dos primeras filas."""
    try:
        times = pd.to_datetime(df["time"], utc=True, errors="coerce").dropna()
        if len(times) >= 2:
            delta = (times.iloc[1] - times.iloc[0]).to_pytimedelta()
            if delta is not None and delta.total_seconds() > 0:
                secs = int(delta.total_seconds())
                return f"{secs}s"
    except Exception:
        pass
    return "1D"


def tf_duration(tf: str) -> str:
    """Duracion de una barra en pandas Timedelta string."""
    tf = (tf or "").upper()
    return {
        "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
        "H1": "1h", "H4": "4h", "H12": "12h", "D1": "1D", "W1": "1W",
    }.get(tf, "1D")


def closed_merge_asof(ltf: pd.DataFrame, htf_state: pd.DataFrame,
                      duration: str) -> pd.DataFrame:
    """merge_asof HTF->LTF CLOSED-ONLY (anti look-ahead cross-timeframe).

    Une el estado HTF al LTF usando `merge_asof(direction='backward')` pero
    EXIGIENDO que la barra HTF haya CERRADO: resta `duration` al tiempo de
    join del LTF. `duration` es OBLIGATORIO.
    """
    if duration is None:
        raise TypeError("closed_merge_asof requiere duration obligatorio (HTF closed-only)")
    cut = pd.Timedelta(duration)
    ltf_join = ltf.copy()
    ltf_join["time"] = pd.to_datetime(ltf_join["time"], utc=True, errors="coerce") - cut
    htf_sorted = htf_state.sort_values("time").reset_index(drop=True)
    merged = pd.merge_asof(
        ltf_join.sort_values("time"), htf_sorted, on="time", direction="backward"
    )
    merged["time"] = pd.to_datetime(ltf["time"], utc=True, errors="coerce").values
    return merged


def closed_row_at_time(df: pd.DataFrame, t: Any, duration: Any) -> Any:
    """Lectura HTF CLOSED-ONLY (anti look-ahead cross-timeframe).

    Devuelve la fila cuya barra ya CERRÓ respecto a `t` (time + duration <= t).
    `duration` es OBLIGATORIO.

    Si NINGUNA vela del TF cerró antes de `t - duration`, devuelve None
    (no hay disponibilidad). NUNCA devuelve la primera vela del DF cuando esta
    aún no ha cerrado: eso sería look-ahead (ver auditoría market_replay).
    """
    if duration is None:
        raise TypeError("closed_row_at_time requiere duration obligatorio (HTF closed-only)")
    try:
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        cutoff = tt - pd.Timedelta(duration)
        exact_idx = df.index[times == cutoff].to_numpy()
        if len(exact_idx):
            return df.iloc[int(exact_idx[0])]
        prior_idx = df.index[times <= cutoff].to_numpy()
        if len(prior_idx):
            return df.iloc[int(prior_idx[-1])]
        # Ninguna vela cerró antes del cutoff => no hay disponibilidad (anti look-ahead).
        return None
    except Exception:
        return None


def avg_candle_range(df: pd.DataFrame, window: int = 50) -> pd.Series:
    """FUENTE ÚNICA de volatilidad/riesgo del sistema.

    Rango promedio de la vela = promedio de (high - low) sobre una ventana
    móvil de `window` velas. MATEMÁTICA PURA del gráfico, SIN INDICADORES
    (equivalente a True Range promedio pero sin el componente close-anterior).
    Toda volatilidad/riesgo del sistema debe leer de AQUÍ.
    """
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    rng = pd.Series(high - low, index=df.index)
    rng = rng.mask(rng <= 0.0)
    # La ventana usa solo velas disponibles hasta i. No rellenar hacia atrás:
    # eso usaría rangos de velas futuras y violaría el contrato causal.
    avg = rng.rolling(window=window, min_periods=1).mean()
    return avg
