"""
M15 Evidence Assembler — Ensamblador canónico de evidencia M15 para cada
decision_time. Combina el productor histórico existente (historical_event_objects)
con el detector de sweep canónico (canonical_sweep) y una función de detección
de retest.

Este módulo no redefine BOS, displacement, FVG, OB, sweep ni retest. Compone
los detectores existentes para producir el formato m15_evidence que exige el
evaluador canónico (mechanical_signal_assessment.assess_mechanical_signal).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import sys

# ─────────────────────────────────────────────────────────────────────────────
# PATH CONFIG — Asegurar que ROOT/detectors/ esté en sys.path antes que
# engine/detectors/ para evitar conflictos de importación.
# ─────────────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
_DETECTORS_ROOT = _ROOT / "detectors"

if str(_DETECTORS_ROOT) not in sys.path:
    sys.path.insert(0, str(_DETECTORS_ROOT))


from detectors.liquidity_context import canonical_sweep
from engine.historical_event_objects import HistoricalEventConfig, build_historical_event_objects

__all__ = [
    "build_m15_evidence_for_decision_time",
    "M15EvidenceAssembler",
    "M15Evidence",
]


def _to_utc(value: Any) -> pd.Timestamp:
    """Convertir cualquier valor a Timestamp UTC."""
    result = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(result):
        raise ValueError(f"Invalid time value: {value!r}")
    return result


def _normalize_time_column(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Normalizar la columna de tiempo del dataframe a datetime64[ms, UTC]."""
    if "timestamp" in df.columns:
        df = df.copy()
        if df["timestamp"].dtype == "int64":
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        elif pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            if df["timestamp"].dt.tz is None:
                df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
            else:
                df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
        return df, "timestamp"
    if "time" in df.columns:
        df = df.copy()
        if df["time"].dtype == "datetime64[ms]":
            if df["time"].dt.tz is None:
                df["time"] = df["time"].dt.tz_localize("UTC")
            else:
                df["time"] = df["time"].dt.tz_convert("UTC")
        return df, "time"
    raise ValueError(f"No se encontró columna de tiempo en: {list(df.columns)}")


def _recortar_frame(frame: pd.DataFrame, time_col: str, decision_time: pd.Timestamp) -> pd.DataFrame:
    """Recortar el frame a velas con time <= decision_time."""
    mask = frame[time_col] <= decision_time
    return frame[mask]


def build_m15_evidence_for_decision_time(
    m15_frame: pd.DataFrame,
    h4_frame: pd.DataFrame | None = None,
    decision_time: pd.Timestamp | str | None = None,
    symbol: str = "EURUSD",
) -> dict[str, Any]:
    """Construir evidencia M15 canónica para un decision_time dado.

    Combina los detectores existentes para producir el formato m15_evidence
    que exige el evaluador canónico (mechanical_signal_assessment.assess_mechanical_signal).

    La cadena requerida por el evaluador:
        H4/H1 alineados → sweep M15 → displacement M15 → BOS/CHOCH M15
        → FVG u OB canónico M15 → retest M15 cerrado

    Args:
        m15_frame: DataFrame de velas M15 cerradas (time <= decision_time).
        h4_frame: DataFrame de velas H4 (opcional, para contexto de OB H4).
        decision_time: Momento de decisión (UTC).
        symbol: Instrumento (default EURUSD).

    Returns:
        dict con m15_evidence conteniendo:
        - sweep: {present, time, source, direction}
        - displacement: {present, time, source}
        - bos_or_choch: {present, time, source}
        - fvg_or_ob: {present, time, source}
        - retest: {present, time, source}
    """
    decision_time = _to_utc(decision_time) if decision_time is not None else None
    if decision_time is None:
        raise ValueError("decision_time es requerido")

    m15_norm, m15_tc = _normalize_time_column(m15_frame)
    m15_ctx = _recortar_frame(m15_norm, m15_tc, decision_time)

    if m15_ctx.empty:
        return _empty_evidence("no_m15_data")

    last_time = m15_ctx.iloc[-1][m15_tc]

    # 1. SWEEP — usando canonical_sweep (detector canónico único, libro 05)
    sweep_frame = canonical_sweep(m15_ctx.copy(), lookback=20)
    sweep_up = bool(sweep_frame.iloc[-1].get("liquidity_sweep_up", False))
    sweep_down = bool(sweep_frame.iloc[-1].get("liquidity_sweep_down", False))

    if sweep_up or sweep_down:
        sweep_present = True
        sweep_time = str(last_time)
        sweep_source = "canonical_sweep"
        sweep_direction = "up" if sweep_up else "down"
    else:
        sweep_present = False
        sweep_time = None
        sweep_source = "canonical_sweep"
        sweep_direction = None

    # 2. HISTORICAL EVENT OBJECTS — BOS, DISPLACEMENT, FVG/OB
    frames_para_heo: dict[str, pd.DataFrame] = {"M15": m15_ctx}
    if h4_frame is not None:
        h4_norm, h4_tc = _normalize_time_column(h4_frame)
        h4_ctx = _recortar_frame(h4_norm, h4_tc, decision_time)
        if not h4_ctx.empty:
            frames_para_heo["H4"] = h4_ctx

    heo_result = build_historical_event_objects(
        frames_para_heo, symbol=symbol
    )
    objetos = heo_result.get("objects", [])

    # Encontrar el último objeto de cada tipo con creation_time <= decision_time
    last_displacement: Any = None
    last_bos: Any = None
    last_fvg_or_ob: Any = None

    for obj in objetos:
        obj_time = _to_utc(obj.creation_time)
        if obj_time > decision_time:
            continue
        if obj.type.value == "DISPLACEMENT":
            if last_displacement is None or obj_time > _to_utc(last_displacement.creation_time):
                last_displacement = obj
        if obj.type.value == "BOS":
            if last_bos is None or obj_time > _to_utc(last_bos.creation_time):
                last_bos = obj
        if obj.type.value in ("FVG", "ORDER_BLOCK"):
            if last_fvg_or_ob is None or obj_time > _to_utc(last_fvg_or_ob.creation_time):
                last_fvg_or_ob = obj

    displacement_present = last_displacement is not None
    displacement_time = (
        str(last_displacement.creation_time)
        if last_displacement
        else None
    )

    bos_or_choch_present = last_bos is not None
    bos_or_choch_time = (
        str(last_bos.creation_time) if last_bos else None
    )

    fvg_or_ob_present = last_fvg_or_ob is not None
    fvg_or_ob_time = (
        str(last_fvg_or_ob.creation_time) if last_fvg_or_ob else None
    )

    # 3. RETEST — verificar si la última vela tocó la zona FVG/OB
    retest_present = False
    retest_time = None

    if fvg_or_ob_present and last_fvg_or_ob is not None:
        last_candle = m15_ctx.iloc[-1]
        zone_low = (
            float(last_fvg_or_ob.zone_low)
            if last_fvg_or_ob.zone_low
            else None
        )
        zone_high = (
            float(last_fvg_or_ob.zone_high)
            if last_fvg_or_ob.zone_high
            else None
        )

        if zone_low is not None and zone_high is not None:
            candle_low = float(last_candle["low"])
            candle_high = float(last_candle["high"])
            # Toque de zona: el rango de la vela intersecta con la zona del objeto
            if candle_low <= zone_high and candle_high >= zone_low:
                retest_present = True
                retest_time = str(last_time)

    return {
        "sweep": {
            "present": sweep_present,
            "time": sweep_time,
            "source": sweep_source,
            "direction": sweep_direction if sweep_direction else None,
        },
        "displacement": {
            "present": displacement_present,
            "time": displacement_time,
            "source": (
                "historical_event_objects"
                if displacement_present
                else "no_displacement"
            ),
        },
        "bos_or_choch": {
            "present": bos_or_choch_present,
            "time": bos_or_choch_time,
            "source": (
                "historical_event_objects"
                if bos_or_choch_present
                else "no_structure"
            ),
        },
        "fvg_or_ob": {
            "present": fvg_or_ob_present,
            "time": fvg_or_ob_time,
            "source": (
                "historical_event_objects"
                if fvg_or_ob_present
                else "no_poi"
            ),
        },
        "retest": {
            "present": retest_present,
            "time": retest_time,
            "source": _retest_source(
                retest_present, fvg_or_ob_present
            ),
        },
    }


def _empty_evidence(reason: str) -> dict[str, Any]:
    """Evidencia vacía por falta de datos."""
    return {
        "sweep": {
            "present": False,
            "time": None,
            "source": reason,
            "direction": None,
        },
        "displacement": {
            "present": False,
            "time": None,
            "source": reason,
        },
        "bos_or_choch": {
            "present": False,
            "time": None,
            "source": reason,
        },
        "fvg_or_ob": {
            "present": False,
            "time": None,
            "source": reason,
        },
        "retest": {
            "present": False,
            "time": None,
            "source": reason,
        },
    }


def _retest_source(
    retest_present: bool, fvg_or_ob_present: bool
) -> str:
    """Determinar el source del retest según el resultado."""
    if retest_present:
        return "m15_candle_retest_check"
    if not fvg_or_ob_present:
        return "no_poi"
    return "m15_candle_retest_check_failed"


class M15EvidenceAssembler:
    """Ensamblador de evidencia M15 con estado opcional para rendimiento.

    Incluye el ensamblador HEO (Historical Event Objects) para evitar
    reconstruir los objetos en cada llamada si los frames no cambian.
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        config: HistoricalEventConfig | None = None,
    ) -> None:
        self.symbol = symbol
        self.config = config or HistoricalEventConfig()
        self._last_heo_result: dict | None = None
        self._last_heo_frames_hash: str = ""

    def build(
        self,
        m15_frame: pd.DataFrame,
        h4_frame: pd.DataFrame | None = None,
        decision_time: pd.Timestamp | str | None = None,
    ) -> dict[str, Any]:
        """Construir evidencia M15 para un decision_time dado."""
        decision_time = (
            _to_utc(decision_time)
            if decision_time is not None
            else None
        )
        if decision_time is None:
            raise ValueError("decision_time es requerido")

        m15_norm, m15_tc = _normalize_time_column(m15_frame)
        m15_ctx = _recortar_frame(m15_norm, m15_tc, decision_time)

        if m15_ctx.empty:
            return _empty_evidence("no_m15_data")

        last_time = m15_ctx.iloc[-1][m15_tc]

        # Sweep
        sweep_frame = canonical_sweep(m15_ctx.copy(), lookback=20)
        sweep_up = bool(
            sweep_frame.iloc[-1].get("liquidity_sweep_up", False)
        )
        sweep_down = bool(
            sweep_frame.iloc[-1].get("liquidity_sweep_down", False)
        )

        if sweep_up or sweep_down:
            sweep_present = True
            sweep_time = str(last_time)
            sweep_source = "canonical_sweep"
            sweep_direction = "up" if sweep_up else "down"
        else:
            sweep_present = False
            sweep_time = None
            sweep_source = "canonical_sweep"
            sweep_direction = None

        # Historical event objects
        frames_para_heo: dict[str, pd.DataFrame] = {"M15": m15_ctx}
        if h4_frame is not None:
            h4_norm, h4_tc = _normalize_time_column(h4_frame)
            h4_ctx = _recortar_frame(h4_norm, h4_tc, decision_time)
            if not h4_ctx.empty:
                frames_para_heo["H4"] = h4_ctx

        heo_result = build_historical_event_objects(
            frames_para_heo,
            symbol=self.symbol,
            config=self.config,
        )
        objetos = heo_result.get("objects", [])

        # Encontrar el último objeto de cada tipo con creation_time <= decision_time
        last_displacement: Any = None
        last_bos: Any = None
        last_fvg_or_ob: Any = None

        for obj in objetos:
            obj_time = _to_utc(obj.creation_time)
            if obj_time > decision_time:
                continue
            if obj.type.value == "DISPLACEMENT":
                if (
                    last_displacement is None
                    or obj_time > _to_utc(last_displacement.creation_time)
                ):
                    last_displacement = obj
            if obj.type.value == "BOS":
                if (
                    last_bos is None
                    or obj_time > _to_utc(last_bos.creation_time)
                ):
                    last_bos = obj
            if obj.type.value in ("FVG", "ORDER_BLOCK"):
                if (
                    last_fvg_or_ob is None
                    or obj_time > _to_utc(last_fvg_or_ob.creation_time)
                ):
                    last_fvg_or_ob = obj

        displacement_present = last_displacement is not None
        displacement_time = (
            str(last_displacement.creation_time)
            if last_displacement
            else None
        )

        bos_or_choch_present = last_bos is not None
        bos_or_choch_time = (
            str(last_bos.creation_time) if last_bos else None
        )

        fvg_or_ob_present = last_fvg_or_ob is not None
        fvg_or_ob_time = (
            str(last_fvg_or_ob.creation_time) if last_fvg_or_ob else None
        )

        # Retest
        retest_present = False
        retest_time = None

        if fvg_or_ob_present and last_fvg_or_ob is not None:
            last_candle = m15_ctx.iloc[-1]
            zone_low = (
                float(last_fvg_or_ob.zone_low)
                if last_fvg_or_ob.zone_low
                else None
            )
            zone_high = (
                float(last_fvg_or_ob.zone_high)
                if last_fvg_or_ob.zone_high
                else None
            )

            if zone_low is not None and zone_high is not None:
                candle_low = float(last_candle["low"])
                candle_high = float(last_candle["high"])
                if candle_low <= zone_high and candle_high >= zone_low:
                    retest_present = True
                    retest_time = str(last_time)

        return {
            "sweep": {
                "present": sweep_present,
                "time": sweep_time,
                "source": sweep_source,
                "direction": (
                    sweep_direction if sweep_direction else None
                ),
            },
            "displacement": {
                "present": displacement_present,
                "time": displacement_time,
                "source": (
                    "historical_event_objects"
                    if displacement_present
                    else "no_displacement"
                ),
            },
            "bos_or_choch": {
                "present": bos_or_choch_present,
                "time": bos_or_choch_time,
                "source": (
                    "historical_event_objects"
                    if bos_or_choch_present
                    else "no_structure"
                ),
            },
            "fvg_or_ob": {
                "present": fvg_or_ob_present,
                "time": fvg_or_ob_time,
                "source": (
                    "historical_event_objects"
                    if fvg_or_ob_present
                    else "no_poi"
                ),
            },
            "retest": {
                "present": retest_present,
                "time": retest_time,
                "source": _retest_source(
                    retest_present, fvg_or_ob_present
                ),
            },
        }


if __name__ == "__main__":
    import numpy as np
    from datetime import datetime, timezone

    print("=" * 60)
    print("TEST: M15EvidenceAssembler — Datos sintéticos")
    print("=" * 60)

    # Crear datos sintéticos con estructura definida
    np.random.seed(42)
    n_bars = 200

    times = pd.date_range(
        "2024-01-01", periods=n_bars, freq="15min", tz="UTC"
    )

    # Tendencia bajista inicial, luego rally
    prices = 1.0850 + np.cumsum(
        np.random.uniform(-0.0005, 0.0005, n_bars)
    )
    opens = prices + np.random.uniform(-0.0002, 0.0002, n_bars)
    closes = opens + np.random.uniform(-0.0008, 0.0008, n_bars)
    highs = (
        np.maximum(opens, closes)
        + np.random.uniform(0, 0.0003, n_bars)
    )
    lows = (
        np.minimum(opens, closes)
        - np.random.uniform(0, 0.0003, n_bars)
    )

    m15_df = pd.DataFrame(
        {
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
        }
    )

    decision_time = m15_df["time"].iloc[-1]
    print(f"M15: {len(m15_df)} velas, {m15_df['time'].min()} -> {m15_df['time'].max()}")
    print(f"Decision time: {decision_time}")

    evidence = build_m15_evidence_for_decision_time(
        m15_frame=m15_df,
        decision_time=decision_time,
        symbol="EURUSD",
    )

    print(f"\nEvidencia M15:")
    for key, value in evidence.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("TEST COMPLETADO")
    print("=" * 60)
