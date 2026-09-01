"""engine/execution.py — Ejecucion fina del trader humano (PERMANENTE, B2).

Brecha B2 del roadmap: el motor decidia la zona en M15, pero la TESIS (libro 18)
dice que la ENTRADA siempre va en el TF de ejecucion (M5/M1). Este modulo baja
la decision ya validada por el gate top-down (D1->H4->H1) a la entrada fina:
entry = breakout del ultimo swing en M5/M1, SL = mecha del sweep del exec TF
(estructural, no arbitrary), TP = RR 1:3 al objetivo de liquidez.

Ley: solo usa el motor (engine.bias._swing_points, engine.bos). NUNCA importa
ict_backtest/. Es geometria pura, sin indicadores. Anti look-ahead: solo velas
con time <= t (y <= sweep_ts) en el TF de ejecucion.

Contrato (B2):
  - Sin sweep_ts: entry/SL/TP desde swings del exec TF (fallback / modulo).
  - Con sweep_ts: SL se ancla a la MECHA DEL SWEEP del exec TF (libro 18: el
    SL estructural SIEMPRE en el TF mas fino, nunca en uno mayor). El SETUP se
    detecto en el LTF; aqui solo se reancla la entrada fina.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engine.bias.narrative import _swing_points

# Buffer del SL estructural en RANGO (high-low promedio). ICT mistake #4:
# stops 1 pip past the level get tagged on the spike. 0.3 * rango da aire sin
# romper el RR. Mismo contrato que ict_backtest.engine.STRUCT_SL_BUFFER_RANGE.
STRUCT_SL_BUFFER_RANGE = 0.3


def _closed_df_at_time(df: pd.DataFrame, t: Any) -> pd.DataFrame:
    """Recorta df a velas ya cerradas al tiempo t (time <= t)."""
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    if pd.isna(tt):
        return df.iloc[0:0]
    mask = times <= tt
    return df.loc[mask]


def _lvl(row: pd.Series, col: str) -> float | None:
    """Lee una columna de nivel (sweep_low/sweep_high) o None si ausente."""
    v = row.get(col, np.nan)
    fv = float(v) if not isinstance(v, float) else v
    if pd.isna(fv) or fv <= 0:
        return None
    return float(fv)


def fine_execution(
    ms: dict[str, pd.DataFrame],
    t: Any,
    direction: int,
    *,
    exec_tf: str = "M5",
    rr: float = 3.0,
    sweep_ts: Any | None = None,
) -> dict[str, Any]:
    """Entrada fina en M5/M1 para una direccion ya validada por el gate.

    Args:
        ms: frames por TF (debe incluir exec_tf; fallback a M15).
        t: tiempo de la vela LTF ya cerrada (anti look-ahead).
        direction: +1 long, -1 short.
        exec_tf: TF de ejecucion fina ("M5" por defecto; "M1" permitido).
        rr: ratio take-profit / stop-loss (1:3 ICT).
        sweep_ts: tiempo del sweep en el LTF. Si se da, el SL se ancla a la
            mecha del sweep del exec TF (libro 18). Si es None, el SL usa el
            ultimo swing opuesto (fallback / contrato de modulo).

    Returns:
        dict con keys: ok, exec_tf, entry, sl, tp, rr, reason.
        ok=False si no hay suficiente estructura en el TF de ejecucion.
    """
    df = ms.get(exec_tf)
    if df is None:  # fallback a M15 si no hay TF de ejecucion
        df = ms.get("M15")
    if df is None or len(df) == 0:
        return {"ok": False, "exec_tf": exec_tf, "reason": "no_exec_tf_data"}

    closed = _closed_df_at_time(df, t)
    if len(closed) < 5:
        return {"ok": False, "exec_tf": exec_tf, "reason": "not_enough_bars"}

    sh, sl = _swing_points(closed, lookback=2)
    sh_v = sh.dropna()
    sl_v = sl.dropna()

    # rng_exec: rango promedio de vela del exec TF (matematica pura, sin
    # indicadores). Fuente unica de volatilidad del SL estructural fino.
    _rng = (closed["high"] - closed["low"])
    rng_exec = float(_rng.tail(50).mean()) if len(_rng) >= 50 else float(_rng.mean())
    if rng_exec <= 0:
        return {"ok": False, "exec_tf": exec_tf, "reason": "zero_range"}
    buf = STRUCT_SL_BUFFER_RANGE * rng_exec

    # --- SL: mecha del sweep del exec TF (libro 18) si sweep_ts se da. ---
    if direction > 0:  # LONG
        if sweep_ts is not None:
            sweep_closed = _closed_df_at_time(df, sweep_ts)
            if len(sweep_closed) == 0:
                return {"ok": False, "exec_tf": exec_tf, "reason": "no_sweep_bar"}
            srow = sweep_closed.iloc[-1]
            sweep = _lvl(srow, "sweep_low")
            if sweep is None:
                sweep = float(srow["low"])
            sl_price = sweep - buf
            # Entry: breakout del ultimo swing high si hay swings (datos reales);
            # si no (datos planos), el toque de zona (close de la vela del entry).
            if sh_v.empty:
                entry = float(closed.iloc[-1]["close"])
            else:
                entry = float(sh_v.iloc[-1])
            # Fallback ICT (libro 18): SL SIEMPRE en estructura. Si la mecha del
            # sweep queda invalida en el TF fino (compresion M5: sl>=entry),
            # reanclar al ultimo swing low del exec TF (estructura real, no arbitrary).
            if sl_price >= entry:
                if sl_v.empty:
                    return {"ok": False, "exec_tf": exec_tf, "reason": "sl_invalid_long"}
                sl_price = float(sl_v.iloc[-1])
                entry = float(sh_v.iloc[-1]) if not sh_v.empty else sl_price
        else:
            if sl_v.empty:
                return {"ok": False, "exec_tf": exec_tf, "reason": "no_swings"}
            sl_price = float(sl_v.iloc[-1])
            entry = float(sh_v.iloc[-1]) if not sh_v.empty else float(sl_v.iloc[-1])
        if sl_price >= entry:
            return {"ok": False, "exec_tf": exec_tf, "reason": "sl_invalid_long"}
        tp_price = entry + rr * (entry - sl_price)
        tp_ext = float(closed["high"].max())  # liquidez externa = maximo high
    else:  # SHORT
        if sweep_ts is not None:
            sweep_closed = _closed_df_at_time(df, sweep_ts)
            if len(sweep_closed) == 0:
                return {"ok": False, "exec_tf": exec_tf, "reason": "no_sweep_bar"}
            srow = sweep_closed.iloc[-1]
            sweep = _lvl(srow, "sweep_high")
            if sweep is None:
                sweep = float(srow["high"])
            sl_price = sweep + buf
            if sl_v.empty:
                entry = float(closed.iloc[-1]["close"])
            else:
                entry = float(sl_v.iloc[-1])
            # Fallback ICT (libro 18): si la mecha del sweep queda invalida en el
            # TF fino, reanclar al ultimo swing high del exec TF (estructura real).
            if sl_price <= entry:
                if sh_v.empty:
                    return {"ok": False, "exec_tf": exec_tf, "reason": "sl_invalid_short"}
                sl_price = float(sh_v.iloc[-1])
                entry = float(sl_v.iloc[-1]) if not sl_v.empty else sl_price
        else:
            if sh_v.empty:
                return {"ok": False, "exec_tf": exec_tf, "reason": "no_swings"}
            sl_price = float(sh_v.iloc[-1])
            entry = float(sl_v.iloc[-1]) if not sl_v.empty else float(sh_v.iloc[-1])
        if sl_price <= entry:
            return {"ok": False, "exec_tf": exec_tf, "reason": "sl_invalid_short"}
        tp_price = entry - rr * (sl_price - entry)
        tp_ext = float(closed["low"].min())  # liquidez externa = minimo low
    return {
        "ok": True,
        "exec_tf": exec_tf,
        "entry": round(entry, 5),
        "sl": round(sl_price, 5),
        "tp": round(tp_price, 5),
        "tp_ext": round(tp_ext, 5),
        "rng_exec": rng_exec,
        "rr": rr,
        "reason": "fine_exec_structural",
    }
