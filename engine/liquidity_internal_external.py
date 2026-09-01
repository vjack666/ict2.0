"""engine/liquidity_internal_external.py — Liquidez interna (IRL) y externa (ERL).

ERL (External Range Liquidity): los extremos del rango (swing high/low) donde
descansan los stops. IRL (Internal Range Liquidity): las ineficiencias internas
(FVG no llenados) hacia las que el precio retrocede tras barrer el externo.

Reglas (AGENTS.md):
  - `engine/` NUNCA importa `ict_backtest/`.
  - Geometría pura: high/low/open/close. Sin indicadores (no ATR/EMA).
  - El volumen es OPCIONAL y sólo se REPORTA: nunca decide un booleano.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine._volume import volume_confirm as _volume_confirm

__all__ = [
    "LiquidityModelConfig",
    "classify_liquidity",
    "volume_confirm",
    "flag_liquidity_irl_erl",
]


def volume_confirm(df: pd.DataFrame, idx: int, window: int = 20):
    """Ratio volumen vela / media previa. None si no hay columna 'volume'.
  DRY (MDS_VOLUMEN): delega en `engine._volume.volume_confirm`.
  """
    return _volume_confirm(df, idx, window)


@dataclass(frozen=True)
class LiquidityModelConfig:
    """Parámetros del modelo IRL/ERL."""

    erl_swing_lookback: int = 10
    irl_fvg_min_size: float = 0.0
    volume_confirm_window: int = 20


def _range_bounds(data: pd.DataFrame, lookback: int, dealing_range) -> tuple:
    """Swings previos (shift(1) => sin look-ahead) del rango vigente."""
    if dealing_range is not None:
        lb = int(getattr(dealing_range, "lookback", lookback) or lookback)
    else:
        lb = int(lookback)
    lb = max(1, lb)
    swing_high = data["high"].rolling(lb, min_periods=1).max().shift(1)
    swing_low = data["low"].rolling(lb, min_periods=1).min().shift(1)
    return swing_high, swing_low


def classify_liquidity(
    df: pd.DataFrame,
    direction: int,
    *,
    dealing_range=None,
    fvg_df: pd.DataFrame | None = None,
    htf_bias=None,
    volume_confirm_fn=None,
    config: LiquidityModelConfig | None = None,
) -> dict:
    """Clasifica liquidez externa (ERL) e interna (IRL).

    Devuelve dict con: erl_sweep, erl_level, erl_idx, irl_target, irl_fvg_idx,
    seq_erl_then_irl, erl_volume_ratio, irl_volume_ratio.
    """
    cfg = config or LiquidityModelConfig()
    out = {
        "erl_sweep": False,
        "erl_level": None,
        "erl_idx": None,
        "irl_target": None,
        "irl_fvg_idx": None,
        "seq_erl_then_irl": False,
        "erl_volume_ratio": None,
        "irl_volume_ratio": None,
        "direction": int(direction),
    }
    if df is None or len(df) == 0:
        return out

    data = df.reset_index(drop=True)
    swing_high, swing_low = _range_bounds(data, cfg.erl_swing_lookback, dealing_range)

    # --- ERL: barrida del extremo OPUESTO a la dirección buscada -------------
    # direction +1 (long) -> se barre la SSL (low bajo swing_low previo).
    # direction -1 (short) -> se barre la BSL (high sobre swing_high previo).
    erl_idx = None
    erl_level = None
    if int(direction) >= 0:
        hit = (data["low"] < swing_low).fillna(False)
        levels = swing_low
    else:
        hit = (data["high"] > swing_high).fillna(False)
        levels = swing_high
    idxs = list(np.flatnonzero(hit.to_numpy()))
    if idxs:
        erl_idx = int(idxs[-1])
        lvl = levels.iloc[erl_idx]
        erl_level = None if pd.isna(lvl) else float(lvl)
        out["erl_sweep"] = True
        out["erl_idx"] = erl_idx
        out["erl_level"] = erl_level

    # --- IRL: FVG interno no llenado dentro del rango ------------------------
    range_high = float(data["high"].max())
    range_low = float(data["low"].min())
    last_close = float(data["close"].iloc[-1])

    irl_idx = None
    irl_target = None
    if fvg_df is not None and len(fvg_df) and "fvg_mid" in fvg_df.columns:
        f = fvg_df.reset_index(drop=True)
        best = None
        for i in range(len(f)):
            is_bull = bool(f["fvg_bullish"].iloc[i]) if "fvg_bullish" in f else False
            is_bear = bool(f["fvg_bearish"].iloc[i]) if "fvg_bearish" in f else False
            if not (is_bull or is_bear):
                continue
            status = str(f["fvg_fill_status"].iloc[i]) if "fvg_fill_status" in f else "none"
            if status == "filled":
                continue
            size = float(f["fvg_size"].iloc[i]) if "fvg_size" in f else 0.0
            if size < float(cfg.irl_fvg_min_size):
                continue
            mid = f["fvg_mid"].iloc[i]
            if pd.isna(mid):
                continue
            mid = float(mid)
            if not (range_low <= mid <= range_high):
                continue
            # Dirección: long busca FVG alcista (soporte), short busca bajista.
            if int(direction) >= 0 and not is_bull:
                continue
            if int(direction) < 0 and not is_bear:
                continue
            dist = abs(last_close - mid)
            if best is None or dist < best[0]:
                best = (dist, i, mid)
        if best is not None:
            irl_idx = int(best[1])
            irl_target = float(best[2])
    out["irl_fvg_idx"] = irl_idx
    out["irl_target"] = irl_target

    # --- Secuencia ERL -> IRL ------------------------------------------------
    irl_return_idx = None
    if erl_idx is not None and irl_target is not None:
        for i in range(erl_idx + 1, len(data)):
            lo = float(data["low"].iloc[i])
            hi = float(data["high"].iloc[i])
            if lo <= irl_target <= hi:
                irl_return_idx = i
                break
        if irl_return_idx is None:
            # Retroceso hacia el objetivo sin tocarlo: cierre se acerca al IRL.
            after = data.iloc[erl_idx + 1 :]
            if len(after):
                closes = after["close"].astype(float).to_numpy()
                sweep_close = float(data["close"].iloc[erl_idx])
                moved = np.abs(closes - irl_target) < abs(sweep_close - irl_target)
                if moved.any():
                    irl_return_idx = int(erl_idx + 1 + int(np.flatnonzero(moved)[0]))
        out["seq_erl_then_irl"] = irl_return_idx is not None

    # --- Volumen (sólo informativo) -----------------------------------------
    if volume_confirm_fn is not None:
        if erl_idx is not None:
            out["erl_volume_ratio"] = volume_confirm_fn(
                data, erl_idx, cfg.volume_confirm_window
            )
        if irl_return_idx is not None:
            out["irl_volume_ratio"] = volume_confirm_fn(
                data, irl_return_idx, cfg.volume_confirm_window
            )

    return out


# ---------------------------------------------------------------------------
# Flag consumidor (para el backtest / ICTSignal) — patrón Brecha D.
# Solo ANOTA metadato en cada senal; NO filtra ni altera entry/SL/TP.
# El backtest (ict_backtest/) LO CONSUME; engine/ nunca importa ict_backtest/.
# ---------------------------------------------------------------------------
from engine.fvg_poi import detect_fvg


def flag_liquidity_irl_erl(signals, frames, ltf: str = "M15", config: "LiquidityModelConfig | None" = None):
    """Anota en cada ICTSignal: erl_sweep, irl_target, irl_fvg_idx,
    seq_erl_then_irl, erl_vol_ratio, irl_vol_ratio (atributos dinamicos).

    No filtra ni cambia entry/SL/TP (principio Brecha D). Quien consuma
    (scoring / UI / E1) decide con ese metadato.
    """
    if not isinstance(signals, (list, tuple)):
        signals = list(signals)
    if not isinstance(frames, dict) or ltf not in frames:
        for sig in signals:
            sig.erl_sweep = None
            sig.irl_target = None
            sig.irl_fvg_idx = None
            sig.seq_erl_then_irl = None
            sig.erl_vol_ratio = None
            sig.irl_vol_ratio = None
        return signals

    df = frames[ltf]
    fvg_df = detect_fvg(df)
    cfg = config or LiquidityModelConfig()
    for sig in signals:
        direction = int(getattr(sig, "direction", 0) or 0)
        if direction == 0:
            sig.erl_sweep = False
            sig.irl_target = None
            sig.irl_fvg_idx = None
            sig.seq_erl_then_irl = False
            sig.erl_vol_ratio = None
            sig.irl_vol_ratio = None
            continue
        entry_at = getattr(sig, "entry_at", None)
        end = int(entry_at) + 1 if entry_at is not None else len(df)
        end = min(end, len(df))
        window = df.iloc[:end]
        meta = classify_liquidity(
            window, direction,
            fvg_df=fvg_df.iloc[:end] if len(fvg_df) >= end else fvg_df,
            volume_confirm_fn=volume_confirm, config=cfg,
        )
        sig.erl_sweep = bool(meta.get("erl_sweep", False))
        sig.irl_target = meta.get("irl_target")
        sig.irl_fvg_idx = meta.get("irl_fvg_idx")
        sig.seq_erl_then_irl = bool(meta.get("seq_erl_then_irl", False))
        sig.erl_vol_ratio = meta.get("erl_volume_ratio")
        sig.irl_vol_ratio = meta.get("irl_volume_ratio")
    return signals
