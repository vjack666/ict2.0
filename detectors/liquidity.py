"""
Liquidez (Buyside/Sellside) — port de LuxAlgo ICT Concepts a Python.

LuxAlgo la define como: clusters de swings (pivots) cuyos precios caen dentro de
un margen atr/a uno del otro (a = 10/margin, margin default 4 => atr/4). Si hay
mas de 2 swings en ese rango, es una zona de liquidez.

Buyside (BSL): por encima del precio (toma de máximos).
Sellside (SSL): por debajo del precio (toma de mínimos).

Devuelve un DataFrame con columnas:
  bsl_price, bsl_top, bsl_bot   (zona buyside activa mas reciente)
  ssl_price, ssl_top, ssl_bot   (zona sellside activa mas reciente)
Solo informativo para pintar en el mapa; no afecta la rutina de trading.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _swing_highs_lows(df: pd.DataFrame, left: int = 3) -> tuple[pd.Series, pd.Series]:
    """Pivots clasicos (igual que LuxAlgo ta.pivothigh/low con left=right=3)."""
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    n = len(high)
    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)
    for i in range(left, n - left):
        win_h = high[i - left : i + left + 1]
        win_l = low[i - left : i + left + 1]
        if high[i] == win_h.max():
            ph[i] = high[i]
        if low[i] == win_l.min():
            pl[i] = low[i]
    return pd.Series(ph, index=df.index), pd.Series(pl, index=df.index)


def detect_liquidity(df: pd.DataFrame, margin: float = 4.0, atr_period: int = 10,
                     min_count: int = 3, visible: int = 2) -> pd.DataFrame:
    """Detecta zonas de liquidez buyside/sellside.

    Args:
        margin: divisor del ATR (LuxAlgo a = 10/margin => rango = atr/margin).
        atr_period: periodo para ATR.
        min_count: minima cantidad de swings en rango para considerar zona.
        visible: cuantas zonas (en cada direccion) mantener visibles.
    """
    out = df.copy()
    out["bsl_price"] = np.nan
    out["bsl_top"] = np.nan
    out["bsl_bot"] = np.nan
    out["ssl_price"] = np.nan
    out["ssl_top"] = np.nan
    out["ssl_bot"] = np.nan

    # ATR
    tr = np.maximum.reduce([
        df["high"].to_numpy() - df["low"].to_numpy(),
        np.abs(df["high"].to_numpy() - df["close"].shift(1).to_numpy()),
        np.abs(df["low"].to_numpy() - df["close"].shift(1).to_numpy()),
    ])
    atr_series = pd.Series(tr, index=df.index).rolling(atr_period, min_periods=1).mean()

    ph, pl = _swing_highs_lows(df, left=3)

    # Recolectar swings como (index, price)
    highs = [(i, p) for i, p in ph.dropna().items()]
    lows = [(i, p) for i, p in pl.dropna().items()]

    def _cluster(swings, is_high: bool):
        """Devuelve lista de dicts zona con top/bot/precio y el indice donde se confirmo."""
        zones = []
        i = 0
        arr = sorted(swings, key=lambda x: x[0])
        n = len(arr)
        while i < n:
            ref_i, ref_p = arr[i]
            pos = df.index.get_loc(ref_i) if ref_i in df.index else len(df) - 1
            atr_i = float(atr_series.iloc[pos])
            band = atr_i / margin if atr_i > 0 else 0.0
            cluster = [arr[i]]
            j = i + 1
            while j < n and abs(arr[j][1] - ref_p) <= band:
                cluster.append(arr[j])
                j += 1
            if len(cluster) > min_count:
                prices = [p for _, p in cluster]
                top = max(prices) + band
                bot = min(prices) - band
                mid = float(np.mean(prices))
                zones.append({
                    "x": cluster[-1][0],
                    "top": top, "bot": bot, "price": mid,
                    "is_high": is_high,
                })
            i = j
        return zones

    bsl = _cluster(highs, is_high=True)
    ssl = _cluster(lows, is_high=False)

    # Asignar a cada vela la zona activa mas reciente (hasta visible zonas)
    for zones, pre, tcol, bcol in (
        (bsl[-visible:] if bsl else [], "bsl_price", "bsl_top", "bsl_bot"),
        (ssl[-visible:] if ssl else [], "ssl_price", "ssl_top", "ssl_bot"),
    ):
        for z in zones:
            xi = df.index.get_loc(z["x"]) if z["x"] in df.index else len(df) - 1
            out.loc[out.index[xi:], pre] = z["price"]
            out.loc[out.index[xi:], tcol] = z["top"]
            out.loc[out.index[xi:], bcol] = z["bot"]
    return out
