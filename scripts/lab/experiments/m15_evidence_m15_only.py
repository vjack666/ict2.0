#!/usr/bin/env python3
"""M15-only evidence extractor para auditoría semántica de setup_grammar.

Busca displacement y FVG/OB en M15 cerrado hasta decision_time, SIN necesidad de H4.

Esto permite auditar las 73 NO_ZONE y las 219 con zona del dataset
SETUP_GRAMMAR_DATASET_V1 cuando H4 no está disponible en exec_tf_evidence.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.detectors.displacement import DisplacementConfig, detect_displacement


def extract_m15_evidence_m15_only(
    m15_frame: pd.DataFrame,
    decision_time: pd.Timestamp,
    symbol: str = "EURUSD",
) -> dict[str, Any]:
    """Extraer evidencia M15-only (sin H4) para auditoría semántica.

    Detecta:
    - Displacement en M15 (hasta decision_time)
    - FVG/OB en M15 (hasta decision_time)

    No requiere H4. No ejecuta canonical_sweep (que requiere estructura más
    compleja). Usa los detectores existentes directamente sobre M15.

    Args:
        m15_frame: DataFrame M15 filtrado hasta decision_time.
        decision_time: Momento de decisión (UTC).
        symbol: Instrumento (default EURUSD).

    Returns:
        dict con:
            - displacement: {present, time, source, direction, magnitude}
            - fvg_or_ob: {present, time, source, type, zone_low, zone_high}
            - bos_or_choch: {present, time, source} (si está disponible)
            - retest: {present, time, source} (si está disponible)
    """
    # Normalizar tiempo
    if m15_frame["timestamp"].dtype == "int64":
        ts = pd.to_datetime(m15_frame["timestamp"], unit="ms", utc=True)
    else:
        ts = pd.to_datetime(m15_frame["timestamp"], utc=True, errors="coerce")

    mask = ts <= decision_time
    m15_ctx = m15_frame[mask].copy().reset_index(drop=True)

    if m15_ctx.empty:
        return _empty_evidence("no_m15_data_until_decision_time")

    # Detectar displacement en M15
    try:
        displacement_cfg = DisplacementConfig()
        displacement_df = detect_displacement(m15_ctx, displacement_cfg)
        disp_mask = (
            displacement_df["displacement_bullish"] | displacement_df["displacement_bearish"]
        )
        displacement_present = bool(disp_mask.any())

        if displacement_present:
            last_disp_idx = displacement_df.index[disp_mask][-1]
            last_disp_row = displacement_df.iloc[last_disp_idx]
            disp_direction = 1 if bool(last_disp_row["displacement_bullish"]) else -1
            disp_time = ts.iloc[last_disp_idx]
            disp_magnitude = float(last_disp_row.get("displacement_mag", 0))
        else:
            disp_direction = None
            disp_time = None
            disp_magnitude = None
    except Exception as e:
        displacement_present = False
        disp_direction = None
        disp_time = None
        disp_magnitude = None
        # No fallar la auditoría por error en displacement

    # Detectar FVG en M15
    try:
        fvg_df = detect_fvg(m15_ctx)
        fvg_present = not fvg_df.empty

        if fvg_present:
            last_fvg_idx = fvg_df.index[-1]
            last_fvg = fvg_df.iloc[last_fvg_idx]
            fvg_time = ts.iloc[last_fvg_idx]
            fvg_type = str(last_fvg.get("fvg_type", "FVG")).upper()
            fvg_zone_low = float(last_fvg.get("fvg_low", fvg_df.iloc[last_fvg_idx].get("low", 0)))
            fvg_zone_high = float(last_fvg.get("fvg_high", fvg_df.iloc[last_fvg_idx].get("high", 0)))
        else:
            fvg_time = None
            fvg_type = None
            fvg_zone_low = None
            fvg_zone_high = None
    except Exception as e:
        fvg_present = False
        fvg_time = None
        fvg_type = None
        fvg_zone_low = None
        fvg_zone_high = None

    # Detectar OB en M15
    try:
        ob_list = detect_order_blocks(m15_ctx.to_dict("records"), timeframe="M15", symbol=symbol)
        ob_present = len(ob_list) > 0

        if ob_present:
            last_ob = ob_list[-1]
            ob_time = pd.to_datetime(last_ob.creation_time, utc=True)
            ob_zone_low = float(last_ob.zone_low) if last_ob.zone_low else None
            ob_zone_high = float(last_ob.zone_high) if last_ob.zone_high else None
        else:
            ob_time = None
            ob_zone_low = None
            ob_zone_high = None
    except Exception as e:
        ob_present = False
        ob_time = None
        ob_zone_low = None
        ob_zone_high = None

    # Combinar FVG + OB
    fvg_or_ob_present = fvg_present or ob_present
    if fvg_present:
        fvg_or_ob_time = fvg_time
        fvg_or_ob_type = fvg_type
        fvg_or_ob_zone_low = fvg_zone_low
        fvg_or_ob_zone_high = fvg_zone_high
        fvg_or_ob_source = "m15_fvg"
    elif ob_present:
        fvg_or_ob_time = ob_time
        fvg_or_ob_type = "ORDER_BLOCK"
        fvg_or_ob_zone_low = ob_zone_low
        fvg_or_ob_zone_high = ob_zone_high
        fvg_or_ob_source = "m15_order_block"
    else:
        fvg_or_ob_time = None
        fvg_or_ob_type = None
        fvg_or_ob_zone_low = None
        fvg_or_ob_zone_high = None
        fvg_or_ob_source = "no_poi"

    return {
        "displacement": {
            "present": displacement_present,
            "time": str(disp_time) if disp_time is not None else None,
            "source": ("m15_displacement_detector" if displacement_present else "no_displacement"),
            "direction": disp_direction,
            "magnitude": disp_magnitude,
        },
        "fvg_or_ob": {
            "present": fvg_or_ob_present,
            "time": str(fvg_or_ob_time) if fvg_or_ob_time is not None else None,
            "source": fvg_or_ob_source,
            "type": fvg_or_ob_type,
            "zone_low": fvg_or_ob_zone_low,
            "zone_high": fvg_or_ob_zone_high,
        },
        "bos_or_choch": {
            "present": False,
            "time": None,
            "source": "not_extracted_m15_only",
        },
        "sweep": {
            "present": False,
            "time": None,
            "source": "canonical_sweep_not_run_m15_only",
        },
        "retest": {
            "present": False,
            "time": None,
            "source": "not_extracted_m15_only",
        },
    }


def _empty_evidence(reason: str) -> dict[str, Any]:
    """Evidencia vacía por falta de datos."""
    return {
        "displacement": {"present": False, "time": None, "source": reason},
        "fvg_or_ob": {"present": False, "time": None, "source": reason},
        "bos_or_choch": {"present": False, "time": None, "source": reason},
        "sweep": {"present": False, "time": None, "source": reason},
        "retest": {"present": False, "time": None, "source": reason},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Compatibilidad con semantic_pd_array_eval_v1
# ─────────────────────────────────────────────────────────────────────────────

def m15_evidence_compat(m15_evidence: dict[str, Any]) -> dict[str, Any]:
    """Convertir la evidencia M15-only al formato que espera semantic_pd_array_eval_v1.

    El detector semántico espera:
        - displacement: {present, time, source}
        - fvg_or_ob: {present, time, source}

    Pero la evidencia M15-only tiene campos adicionales (direction, magnitude, type, zone_low, zone_high).
    Esta función los normaliza al formato compatible.
    """
    disp = m15_evidence.get("displacement", {})
    fvg_or_ob = m15_evidence.get("fvg_or_ob", {})

    return {
        "displacement": {
            "present": disp.get("present", False),
            "time": disp.get("time"),
            "source": disp.get("source", "unknown"),
        },
        "fvg_or_ob": {
            "present": fvg_or_ob.get("present", False),
            "time": fvg_or_ob.get("time"),
            "source": fvg_or_ob.get("source", "unknown"),
        },
    }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("TEST: extract_m15_evidence_m15_only — datos sintéticos")
    print("=" * 60)

    import numpy as np
    from datetime import datetime, timezone

    np.random.seed(42)
    n_bars = 500
    times = pd.date_range("2024-01-01", periods=n_bars, freq="15min", tz="UTC")
    prices = 1.0850 + np.cumsum(np.random.uniform(-0.0005, 0.0005, n_bars))
    opens = prices + np.random.uniform(-0.0002, 0.0002, n_bars)
    closes = opens + np.random.uniform(-0.0008, 0.0008, n_bars)
    highs = np.maximum(opens, closes) + np.random.uniform(0, 0.0003, n_bars)
    lows = np.minimum(opens, closes) - np.random.uniform(0, 0.0003, n_bars)

    m15_df = pd.DataFrame({
        "timestamp": (times - pd.Timestamp("1970-01-01", tz="UTC")).astype("int64") // 10**6,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
    })

    decision_time = m15_df["timestamp"].iloc[-1]
    evidence = extract_m15_evidence_m15_only(m15_df, decision_time)

    print(f"\nEvidencia M15-only:")
    for key, value in evidence.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("TEST COMPLETADO")
    print("=" * 60)
