from __future__ import annotations

import numpy as np
import pandas as pd


def detect_order_blocks(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["ob_bullish"] = False
    data["ob_bearish"] = False

    body = (data["close"] - data["open"]).abs()
    candle_range = (data["high"] - data["low"]).replace(0.0, pd.NA)
    body_ratio = (body / candle_range).fillna(0.0)

    bearish_candle = data["close"] < data["open"]
    bullish_candle = data["close"] > data["open"]
    strong_impulse = body_ratio > 0.7

    # --- Causalidad (sin look-ahead): el OB se marca por la GEOMETRIA de la
    # propia vela de impulso, NO mirando la vela siguiente (close.shift(-1)
    # era fuga de futuro: el OB en k solo aparecia si k+1 confirmaba).
    # Un OB alcista = vela bajista de cuerpo fuerte cuyo CUERPO rompe el rango
    # de la vela anterior (desplazamiento ya visible en el close de k).
    # Un OB bajista = vela alcista de cuerpo fuerte cuyo cuerpo rompe el rango
    # de la vela anterior. Todo usa solo filas <= k.
    prev_high = data["high"].shift(1)
    prev_low = data["low"].shift(1)
    bullish_followthrough = bearish_candle & (data["close"] < prev_low)
    bearish_followthrough = bullish_candle & (data["close"] > prev_high)

    data["ob_bullish"] = bearish_candle & strong_impulse & bullish_followthrough
    data["ob_bearish"] = bullish_candle & strong_impulse & bearish_followthrough

    data["ob_top"] = pd.NA
    data["ob_bottom"] = pd.NA
    data.loc[data["ob_bullish"] | data["ob_bearish"], "ob_top"] = data["high"]
    data.loc[data["ob_bullish"] | data["ob_bearish"], "ob_bottom"] = data["low"]

    ob_highs = data["ob_top"].where(data["ob_bullish"] | data["ob_bearish"]).ffill().infer_objects()
    ob_lows = data["ob_bottom"].where(data["ob_bullish"] | data["ob_bearish"]).ffill().infer_objects()
    mask = ob_highs.notna()
    high_dist = (data["close"] - ob_highs).abs()
    low_dist = (data["close"] - ob_lows).abs()
    data["ob_distance"] = np.where(mask, np.minimum(high_dist, low_dist), 0.0)

    # --- Item E: invalidacion + envejecimiento ---
    data["ob_status"], data["ob_age"] = _track_ob_validity(data)

    # --- Fase B1 (SPEC §4): tipos finos de PD Array + jerarquía (metadatos) ---
    # Morfología del OB para clasificar tipo (libro 21 §2):
    #  - OB normal              -> "OB"          (T2)
    #  - vela de rechazo fuerte  -> "REJECTION_BLOCK" (T3): cuerpo fuerte Y mecha
    #    opuesta larga (>= 1.5x el cuerpo) en la dirección opuesta al impulso.
    #  - OB de continuación      -> "PROPULSION" (T2): ya es OB post-impulso.
    #  - BREAKER / MITIGATION se resuelven en data_feed (cruce con estructura/FVG).
    # NOTA: se PRESERVA el pd_type que vino de detect_fvg (FVG) y solo se
    #   sobreescribe en las filas que son OB (no se pisa el resto).
    upper = data[["high", "low", "open", "close"]].max(axis=1)
    lower = data[["high", "low", "open", "close"]].min(axis=1)
    wick_opp = np.where(
        bearish_candle,  # vela alcista de impulso: mecha inferior
        (data["open"] - data["low"]),
        np.where(bullish_candle,  # vela bajista de impulso: mecha superior
                 (data["high"] - data["open"]), 0.0),
    )
    rejection = strong_impulse & (wick_opp >= 1.5 * body.clip(lower=1e-9))

    is_ob = (data["ob_bullish"] | data["ob_bearish"])
    data["pd_type"] = data.get("pd_type", pd.Series("NONE", index=data.index))
    data.loc[is_ob, "pd_type"] = "OB"
    data.loc[rejection & is_ob, "pd_type"] = "REJECTION_BLOCK"

    data["pd_tier"] = data.get("pd_tier", pd.Series("NONE", index=data.index))
    data.loc[is_ob, "pd_tier"] = "T2"          # OB/PROPULSION T2
    data.loc[data["pd_type"] == "REJECTION_BLOCK", "pd_tier"] = "T3"  # rejection T3

    # MITIGATION_BLOCK / BREAKER / BPR (T1) se resuelven en data_feed con el cruce.
    return data


def _track_ob_validity(data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    n = len(data)
    status = pd.Series(["none"] * n, index=data.index, dtype=object)
    age = pd.Series([0] * n, index=data.index, dtype=int)
    last_dir = 0
    last_top = float("nan")
    last_bottom = float("nan")
    last_idx = -1
    active = False
    close = data["close"].to_numpy()
    ob_bull = data["ob_bullish"].to_numpy()
    ob_bear = data["ob_bearish"].to_numpy()
    ob_top = data["ob_top"].to_numpy()
    ob_bottom = data["ob_bottom"].to_numpy()
    for i in range(1, n):
        bull = bool(ob_bull[i])
        bear = bool(ob_bear[i])
        if bull or bear:
            last_dir = 1 if bull else -1
            last_top = float(ob_top[i]) if pd.notna(ob_top[i]) else last_top
            last_bottom = float(ob_bottom[i]) if pd.notna(ob_bottom[i]) else last_bottom
            last_idx, active = i, True
        if active:
            age.iloc[i] = i - last_idx
            broke = (
                (last_dir == 1 and close[i] < last_bottom)   # OB alcista: cierra debajo
                or (last_dir == -1 and close[i] > last_top)  # OB bajista: cierra encima
            )
            if broke:
                status.iloc[i], active = "invalidated", False
            else:
                # EVENT-DRIVEN: vive por EVENTO (cruce), no por tiempo.
                status.iloc[i] = "active"
    return status, age
