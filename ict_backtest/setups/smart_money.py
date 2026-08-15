"""ict_backtest/setups/smart_money.py — Smart Money Techniques/Concepts (SMT).

Concepto
--------
Smart Money Techniques/Concepts se manifiestan en el gráfico como **señales de
presencia institucional (smart money)** accionables SIN indicadores externos,
solo con OHLC y trigonometría del propio DataFrame.

Este detector implementa 3 pilares:

1. **Zonas de acumulación/distribución (EQH/EQL)**
   - EQH = Equal Highs  : máximos iguales en rangos cercanos.
   - EQL = Equal Lows   : mínimos iguales en rangos cercanos.
   La igualdad se tolera con ``tol_ratio`` relativo al rango promedio local
   (sin ATR). Una "zona" es el cluster de velas donde se forman >=2 extremos
   "iguales". Devuelve intervalos [zone_low, zone_high] normalizados.

2. **Sweeps de liquidez**
   - Liquidez arriba (BSL): close > high_barrido e inmediatamente reversión
     bajista (close < close anterior o body negativo fuerte).
   - Liquidez abajo (SSL): close < low_barrido e inmediatamente reversión
     alcista (close > close anterior o body positivo fuerte).
   El barrido se define contra una banda de liquidez reciente
   (lookback velas), NO contra un nivel fijo arbitrario.

3. **Displacement (desplazamiento direccional)**
   - Después del sweep + reversión hay un cuerpo direccional fuerte.
     - Alcista: close > open y body > 0.6 * rango promedio local.
     - Bajista: close < open y body < -0.6 * rango promedio local.
   - Zona anclada: el displacement se inicia DESDE la zona detectada en
     (1), medido como cuerpos direccionales superiores a 0.3 * body máximo
     de la ventana de retorno, con primer close dentro de la banda de zona.

Contrato
--------
- Función pública::

    is_smart_money(df: pd.DataFrame, context: dict | None = None) -> dict

- df debe contener al menos ``time``, ``open``, ``high``, ``low``, ``close``.
- context opcional:
    - ``ltf``: timeframe (default 'M15')
    - ``sweep_lookback``: velas atrás para buscar liquidity sweeps (default 20)
    - ``zone_lookback``: velas atrás para buscar igualdades (default 40)
    - ``min_touches``: toques mínimos para formar zona (default 2)
    - ``tol_ratio``: tolerancia relativa al rango promedio (default 0.08)
- Returns::

    {
      "smart_money_active": bool,
      "evidence": {
        "sweep_up": bool | None,
        "sweep_down": bool | None,
        "eqh_detected": bool | None,
        "eql_detected": bool | None,
        "displacement_direction": int | None,  # +1/-1/0
        "zone_anchored": bool | None,
        "num_zones": int,
      },
      "zones": [
        {"type": "EQH"|"EQL", "level": float, "start": int, "end": int,
         "touch_count": int, "band": [low, high]},
        ...
      ]
    }

Restricciones
-------------
- SIN ATR, SIN indicadores técnicos, SIN constantes arbitrarias de mercado.
- Solo matemáticas/trigonometría propia del DataFrame.
- Principio arquitectónico: todo parámetro es umbral de señal o buffer de
  seguridad, no concepto de mercado.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers de rango (FUENTE ÚNICA sin ATR): equivale a avg_candle_range pero
# localizado para no importar circularidades. Usa (high - low) puro.
# ---------------------------------------------------------------------------

def _avg_range(df: pd.DataFrame, window: int = 50) -> pd.Series:
    """Rango promedio de vela en una ventana móvil, SIN ATR."""
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    rng = pd.Series(high - low, index=df.index)
    rng = rng.mask(rng <= 0.0)
    avg = rng.rolling(window=window, min_periods=max(1, window // 2)).mean().ffill().bfill()
    return avg


def _body(df: pd.DataFrame) -> pd.Series:
    """Cuerpo dirigido signado: close - open."""
    return (df["close"] - df["open"]).astype(float)


def _strong_body(df: pd.DataFrame, avg_r: pd.Series, threshold: float = 0.6) -> pd.Series:
    """Cuerpo 'fuerte' si |body| >= threshold * avg_r."""
    body = _body(df)
    return body.abs() >= (threshold * avg_r)


# ---------------------------------------------------------------------------
# Zonas EQH/EQL
# ---------------------------------------------------------------------------

def _find_equal_levels(
    df: pd.DataFrame,
    lookback: int = 40,
    min_touches: int = 2,
    tol_ratio: float = 0.08,
) -> list[dict]:
    """Busca clusters de máximos iguales (EQH) y mínimos iguales (EQL).

    EQH/EQL son manifestaciones de zonas institucionales: niveles donde el
    precio tocó varias veces el MISMO extremo, dentro de una tolerancia
    relativa al rango promedio (sin ATR).

    Devuelve una lista de zonas detectadas ordenadas por índice de inicio.
    """
    n = len(df)
    if n < min_touches + 2:
        return []

    avg_r = _avg_range(df, window=max(10, lookback // 2))
    zones: list[dict] = []

    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)

    def _register(_type: str, level: float, start: int, end: int, touches: int):
        band_low = level - avg_r.iloc[max(0, start)] * tol_ratio if pd.notna(avg_r.iloc[max(0, start)]) else level - avg_r.iloc[max(0, start)] if pd.notna(avg_r.iloc[max(0, start)]) else level
        band_high = level + avg_r.iloc[max(0, start)] * tol_ratio if pd.notna(avg_r.iloc[max(0, start)]) else level + avg_r.iloc[max(0, start)] if pd.notna(avg_r.iloc[max(0, start)]) else level
        zones.append({
            "type": _type,
            "level": float(level),
            "start": int(start),
            "end": int(end),
            "touch_count": int(touches),
            "band": [float(band_low), float(band_high)],
        })

    # EQH cluster detection
    touched_eqh: list[tuple[int, float]] = []
    touched_eql: list[tuple[int, float]] = []

    def _tol(tol_val: float, base: float) -> float:
        return max(tol_ratio * base, 5e-5)

    # EQH: contiguous clusters of highs <= tol apart, cluster size >= min_touches.
    i = n - 1
    while i >= 0:
        level = high[i]
        if not np.isfinite(level):
            i -= 1
            continue
        tol = _tol(tol_ratio, avg_r.iloc[i] if i < len(avg_r) else 1e-9)
        end_i = i
        start_i = i
        while start_i - 1 >= max(0, i - lookback + 1) and abs(high[start_i - 1] - level) <= tol:
            start_i -= 1
        if end_i - start_i + 1 >= min_touches:
            _register("EQH", float(np.mean(high[start_i:end_i + 1])), start_i, end_i, end_i - start_i + 1)
            i = start_i - 1
        else:
            i -= 1

    # EQL: contiguous clusters of lows <= tol apart.
    i = n - 1
    while i >= 0:
        level = low[i]
        if not np.isfinite(level):
            i -= 1
            continue
        tol = _tol(tol_ratio, avg_r.iloc[i] if i < len(avg_r) else 1e-9)
        end_i = i
        start_i = i
        while start_i - 1 >= max(0, i - lookback + 1) and abs(low[start_i - 1] - level) <= tol:
            start_i -= 1
        if end_i - start_i + 1 >= min_touches:
            _register("EQL", float(np.mean(low[start_i:end_i + 1])), start_i, end_i, end_i - start_i + 1)
            i = start_i - 1
        else:
            i -= 1

    # De-dup overlapping zones keeping strongest (more touches)
    dedup: list[dict] = []
    for z in sorted(zones, key=lambda x: x["touch_count"], reverse=True):
        if any(
            not (z["end"] < d["start"] or z["start"] > d["end"])
            for d in dedup
        ):
            continue
        dedup.append(z)

    return sorted(dedup, key=lambda x: x["start"])


# ---------------------------------------------------------------------------
# Liquidity sweeps
# ---------------------------------------------------------------------------

def _detect_sweeps(
    df: pd.DataFrame,
    lookback: int = 20,
) -> tuple[bool | None, bool | None]:
    """Detecta barridos de liquidez recientes en las últimas `lookback` velas.

    - **sweep_up** (BSL): precio supera un high reciente y revierte bajista
      (close < prev_close o body negativo >= 0.5 * avg_range).
    - **sweep_down** (SSL): precio perfora un low reciente y revierte alcista
      (close > prev_close o body positivo >= 0.5 * avg_range).

    Devuelve (sweep_up, sweep_down) donde cada elemento es bool o None
    (cuando no hay datos suficientes para definir el evento).
    """
    n = len(df)
    if n < max(4, lookback + 2):
        return None, None

    avg_r = _avg_range(df, window=lookback)
    tail = df.iloc[-lookback:].reset_index(drop=True)
    nrow = len(tail)

    prev_high = tail["high"].shift(1)
    prev_low = tail["low"].shift(1)
    prev_close = tail["close"].shift(1)
    body = _body(tail)

    # Sweep up: high > previous high AND bearish reversal
    sweep_up = False
    if nrow > 2:
        prev_hi = prev_high.to_numpy(dtype=float)
        prev_cl = prev_close.to_numpy(dtype=float)
        cur_hi = tail["high"].to_numpy(dtype=float)
        cur_cl = tail["close"].to_numpy(dtype=float)
        cur_body = body.to_numpy(dtype=float)
        avg_vals = avg_r.iloc[-lookback:].to_numpy(dtype=float)
        avg_vals = np.resize(avg_vals, nrow)
        bull_kill = (cur_hi > np.nan_to_num(prev_hi, nan=cur_hi)) & (
            (cur_cl < np.nan_to_num(prev_cl, nan=cur_cl)) |
            (cur_body <= -0.5 * np.maximum(avg_vals, 1e-9))
        )
        if bool(np.any(bull_kill)):
            sweep_up = True

    # Sweep down: low < previous low AND bullish reversal
    sweep_down = False
    if nrow > 2:
        prev_lo = prev_low.to_numpy(dtype=float)
        prev_cl = prev_close.to_numpy(dtype=float)
        cur_lo = tail["low"].to_numpy(dtype=float)
        cur_cl = tail["close"].to_numpy(dtype=float)
        cur_body = body.to_numpy(dtype=float)
        avg_vals = avg_r.iloc[-lookback:].to_numpy(dtype=float)
        avg_vals = np.resize(avg_vals, nrow)
        bear_kill = (cur_lo < np.nan_to_num(prev_lo, nan=cur_lo)) & (
            (cur_cl > np.nan_to_num(prev_cl, nan=cur_cl)) |
            (cur_body >= 0.5 * np.maximum(avg_vals, 1e-9))
        )
        if bool(np.any(bear_kill)):
            sweep_down = True

    return sweep_up, sweep_down


# ---------------------------------------------------------------------------
# Displacement + anclaje a zona
# ---------------------------------------------------------------------------

def _detect_displacement(
    df: pd.DataFrame,
    zones: list[dict],
    avg_r: pd.Series,
    lookahead: int = 20,
) -> tuple[int | None, bool | None]:
    """Detecta displacement direccional y si está anclado a alguna zona.

    Busca en las velas finales (hasta lookahead) un cuerpo fuerte en la
    dirección del cierre. Si el close de inicio del displacement cae
    dentro o inmediatamente fuera de una banda de zona, marca zone_anchored.

    Devuelve (direction, zone_anchored):
      - direction: +1 (bullish), -1 (bearish), 0 (sin displacement).
      - zone_anchored: True/False/None.
    """
    n = len(df)
    if n < 4:
        return 0, None

    available = min(lookahead, n)
    tail = df.iloc[-available:]
    body = _body(tail)
    avg_r_tail = avg_r.iloc[-available:].bfill().fillna(1e-9)

    bull = body > 0.6 * avg_r_tail
    bear = body < -0.6 * avg_r_tail

    direction = 0
    if bool(bull.any()) and not bool(bear.any()):
        direction = 1
    elif bool(bear.any()) and not bool(bull.any()):
        direction = -1
    elif bool(bull.any()) and bool(bear.any()):
        # si hay ambos, dirección la que tenga cuerpo medio mayor
        bull_mean = body[bull].abs().mean() if bool(bull.any()) else 0.0
        bear_mean = body[bear].abs().mean() if bool(bear.any()) else 0.0
        direction = 1 if bull_mean >= bear_mean else -1

    if direction == 0:
        return 0, None

    # zone anchored: el primer close direccional está dentro/sobre la banda
    zone_anchored = None
    if zones:
        first_dir_idx = None
        if direction == 1:
            for idx in range(len(body)):
                if bool(bull.iloc[idx]):
                    first_dir_idx = idx
                    break
        else:
            for idx in range(len(body)):
                if bool(bear.iloc[idx]):
                    first_dir_idx = idx
                    break

        if first_dir_idx is not None:
            close_price = float(tail.iloc[first_dir_idx]["close"])
            for z in zones:
                if z["band"][0] <= close_price <= z["band"][1]:
                    zone_anchored = True
                    break
            if zone_anchored is None:
                # acepta "cerca" de la banda si Close en el 20% extra
                expanded = [
                    (z["band"][0] - 0.2 * (z["band"][1] - z["band"][0]), z["band"][1] + 0.2 * (z["band"][1] - z["band"][0]))
                    for z in zones
                ]
                for low_b, high_b in expanded:
                    if low_b <= close_price <= high_b:
                        zone_anchored = True
                        break
                if zone_anchored is None:
                    zone_anchored = False

    return direction, zone_anchored


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def is_smart_money(
    df: pd.DataFrame,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detecta presencia de Smart Money Techniques/Concepts en el DataFrame.

    Evalúa zonas igualadas (EQH/EQL), sweeps de liquidez (up/down) y
    displacement direccional anclado a zona. No usa ATR ni indicadores.

    Args:
        df: DataFrame con columnas ``time``, ``open``, ``high``, ``low``,
            ``close``. Debe tener al menos unas 60 velas para fiabilidad.
            El índice se normaliza a rango 0..n-1 internamente.
        context: dict opcional con parámetros sobreescribibles:
            - ``ltf`` (str): timeframe, default ``'M15'``.
            - ``sweep_lookback`` (int): velas hacia atrás para sweeps, default 20.
            - ``zone_lookback`` (int): velas hacia atrás para zonas, default 40.
            - ``min_touches`` (int): toques mínimos para zona, default 2.
            - ``tol_ratio`` (float): tolerancia relativa al avg range, default 0.08.

    Returns:
        dict con:
          - ``smart_money_active`` (bool): True si el detector activa SMT
            completo (sweep + zones + displacement + zone_anchored).
          - ``evidence`` (dict): detalle de evidencia recolectada.
          - ``zones`` (list[dict]): zonas detectadas con sus bandas y metadatos.
    """
    if context is None:
        context = {}

    ltf: str = str(context.get("ltf", "M15"))
    sweep_lookback: int = int(context.get("sweep_lookback", 20))
    zone_lookback: int = int(context.get("zone_lookback", 60))
    min_touches: int = int(context.get("min_touches", 2))
    tol_ratio: float = float(context.get("tol_ratio", 0.08))

    required_cols = {"time", "open", "high", "low", "close"}
    if not required_cols.issubset(df.columns):
        missing = sorted(required_cols - set(df.columns))
        return {
            "smart_money_active": False,
            "evidence": {
                "sweep_up": None, "sweep_down": None,
                "eqh_detected": None, "eql_detected": None,
                "displacement_direction": 0,
                "zone_anchored": None,
                "num_zones": 0,
                "error": f"columnas faltantes: {missing}",
            },
            "zones": [],
        }

    work = df.copy().reset_index(drop=True)
    if len(work) < 12:
        return {
            "smart_money_active": False,
            "evidence": {
                "sweep_up": None, "sweep_down": None,
                "eqh_detected": None, "eql_detected": None,
                "displacement_direction": 0,
                "zone_anchored": None,
                "num_zones": 0,
                "error": "insufficient bars",
            },
            "zones": [],
        }

    # Zonas EQH/EQL
    zones = _find_equal_levels(
        work,
        lookback=zone_lookback,
        min_touches=min_touches,
        tol_ratio=tol_ratio,
    )
    eqh_detected = any(z["type"] == "EQH" for z in zones)
    eql_detected = any(z["type"] == "EQL" for z in zones)

    # Sweeps de liquidez
    sweep_up, sweep_down = _detect_sweeps(work, lookback=sweep_lookback)

    avg_r = _avg_range(work, window=max(10, sweep_lookback))
    direction, zone_anchored = _detect_displacement(work, zones, avg_r, lookahead=min(24, len(work)))

    smart_money_active = False
    if direction != 0 and zones:
        if sweep_up or sweep_down:
            smart_money_active = bool(zone_anchored) if zone_anchored is not None else True

    evidence = {
        "sweep_up": sweep_up,
        "sweep_down": sweep_down,
        "eqh_detected": eqh_detected,
        "eql_detected": eql_detected,
        "displacement_direction": int(direction) if direction is not None else 0,
        "zone_anchored": zone_anchored,
        "num_zones": len(zones),
        "ltf": ltf,
    }

    return {
        "smart_money_active": smart_money_active,
        "evidence": evidence,
        "zones": zones,
    }
