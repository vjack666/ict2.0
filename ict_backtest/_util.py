"""ict_backtest/_util.py — helpers compartidos (único punto de verdad).

Evita duplicar _row_at_time entre engine.py y sequence.py (hallazgo #7).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from engine._util import avg_candle_range as _engine_avg_candle_range


def row_at_time(df: pd.DataFrame, t: Any, freq: Any = None) -> Any:
    """Devuelve la fila de `df` cuyo 'time' coincide con `t` (o la previa más
    cercana, búsqueda asof). Robusta a recortes de walk-forward donde el LTF y
    el HTF tienen rangos distintos.

    Si `freq` se indica, exige que la barra ya haya CERRADO (time + freq <= t)
    para evitar look-ahead cross-timeframe: al leer el HTF desde una vela LTF
    en formación, la barra HTF aún no cerró y sus indicadores (trend, BOS,
    CHOCH) usan precio futuro. Ver AUDIT_LOOKAHEAD_HTF.md.
    """
    try:
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        # Cierre de la barra: para exigir HTF ya cerrado usamos cutoff = tt - freq.
        # El ajuste se aplica TAMBIEN al match exacto (no solo al asof), sino una
        # vela LTF en el limite de apertura del HTF (ej M5 08:00 == open H4 08:00)
        # devolveria la vela HTF sin cerrar (look-ahead residual). Ver AUDIT_LOOKAHEAD_HTF.md.
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
    sus dos primeras filas (R6.1.2). Evita propagar el nombre del TF por toda
    la cadena de llamadas: el call site HTF solo tiene el df, no el string TF.
    """
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
    """Duracion de una barra en pandas Timedelta string (R6.1.2).

    Mapa TF -> duration. Usado por closed_row_at_time para exigir cierre
    de la barra HTF antes de leerla (anti look-ahead cross-timeframe).
    """
    tf = (tf or "").upper()
    return {
        "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
        "H1": "1h", "H4": "4h", "H12": "12h", "D1": "1D", "W1": "1W",
    }.get(tf, "1D")


def closed_merge_asof(ltf: pd.DataFrame, htf_state: pd.DataFrame,
                      duration: str) -> pd.DataFrame:
    """merge_asof HTF->LTF CLOSED-ONLY (R6.1.4 / G1).

    Une el estado HTF al LTF usando `merge_asof(direction='backward')` pero
    EXIGIENDO que la barra HTF haya CERRADO: resta `duration` al tiempo de
    join del LTF para que el backward caiga en la vela HTF ya cerrada, no en
    la que está en formación (look-ahead cross-timeframe). El 'time' del
    resultado se restaura al del LTF.

    `duration` es OBLIGATORIO (ej "4h", "1D").
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
    """Lectura HTF CLOSED-ONLY (R6.1 / G1).

    Devuelve la fila de `df` cuya barra ya CERRÓ respecto a `t`
    (time + duration <= t). Nunca devuelve una vela HTF en formación:
    eso sería look-ahead cross-timeframe (la barra HTF aún no cerró y sus
    indicadores usan precio futuro). Ver AUDIT_LOOKAHEAD_HTF.md.

    `duration` es OBLIGATORIO (ej "4h", "1d"): el contrato closed-only no
    admite un "modo abierto". Los call sites HTF deben migrar aquí para no
    poder leer velas sin cerrar aunque se les olvide pasar el corte.
    """
    if duration is None:
        raise TypeError(
            "closed_row_at_time requiere duration obligatorio (HTF closed-only)"
        )
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
    except Exception:
        pass
    return df.iloc[0]


def avg_candle_range(df: pd.DataFrame, window: int = 50) -> pd.Series:
    """FUENTE ÚNICA de volatilidad/riesgo del sistema.

    Rango promedio de la vela = promedio de (high - low) sobre una ventana
    móvil de `window` velas. MATEMÁTICA PURA del gráfico, SIN INDICADORES
    (equivalente a True Range promedio pero sin el componente
    close-anterior, que solo aporta ruido en TF intradía).

    Es la MISMA métrica que usa ``confirmation_window`` (sequence.py:268) y
    ``build_bos_table`` (bos_table_builder.py:104) para la fuerza del BOS.
    Toda volatilidad/riesgo del sistema debe leer de AQUÍ, para no tener dos
    caminos (rango nuevo + ATR viejo). Ver migración ATR -> rango (Fase 1).

    - Ventanas con high==low (rango 0) se tratan como NA para no contaminar
      el promedio ni producir división por cero en los consumidores.
    - Devuelve una Serie alineada al índice de `df`; durante el calentamiento
      usa solo las velas válidas ya observadas.
    """
    # Shim de compatibilidad: la implementación permanente vive en engine/.
    return _engine_avg_candle_range(df, window=window)

