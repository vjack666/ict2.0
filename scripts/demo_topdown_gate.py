"""scripts/demo_topdown_gate.py — Demostración del pipeline completo con datos 2006.

Encadena las 3 capas del motor ICT en modo offline:
  Capa 1: HTF Bias  (D1→H4→H1 → sesgo del día)
  Capa 2: A7 Funnel (SWEEP→DISPLACE→BOS→FVG/OB → señales)
  Capa 3: Fine Exec  (entry/SL/TP estructurales, libro 18)

Usa el dataset 2006-2010 (primer año disponible).
No requiere conexión, no usa indicadores, sin look-ahead.
"""

from __future__ import annotations

import sys, warnings
from pathlib import Path
from datetime import datetime, timezone

# ── paths ──────────────────────────────────────────────────────────────────
REPO = Path("/c/Users/v_jac/Desktop/ICT SYSTEM")
sys.path.insert(0, str(REPO))
DATA_DIR = REPO / "datasets" / "eurusd_dukascopy_intraday_2006_2010" / "raw"

# ── deps ──────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ── motor ─────────────────────────────────────────────────────────────────
from engine.bias.narrative import compute_htf_bias, HtfBias, BULLISH, BEARISH, NEUTRAL
from engine.bos.structure import detect_market_structure, StructureConfig
from engine.sequence import run_sequence, SequenceConfig, SequenceState
from engine.execution import fine_execution, STRUCT_SL_BUFFER_RANGE
from engine.market_object import MarketObject, ObjectType, ObjectState, Role

# ── helpers ────────────────────────────────────────────────────────────────

def load_m15(year: int = 2006) -> pd.DataFrame:
    """Carga el CSV anual de EURUSD M15."""
    csv_path = DATA_DIR / f"EURUSD_M15_{year}.csv.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe: {csv_path}")
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    print(f"  ✓ M15 cargado: {len(df):,} velas  {df.index[0]} → {df.index[-1]}")
    return df


def resample_tf(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """OHLC resample sin look-ahead (usa solo columnas OHLCV)."""
    ohlc = {
        "open": "first", "high": "max",
        "low": "min", "close": "last",
        "volume": "sum",
    }
    return df.resample(rule).agg(ohlc).dropna(how="all")


def build_mtf_frames(m15: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Construye los 4 TFs necesarios para el pipeline."""
    m15 = m15.copy()
    frames = {
        "M15": m15,
        "H1":  resample_tf(m15, "1h"),
        "H4":  resample_tf(m15, "4h"),
        "D1":  resample_tf(m15, "1D"),
    }
    for tf, frame in frames.items():
        print(f"  ✓ {tf}: {len(frame):,} velas")
    return frames


def enrich_frame(df: pd.DataFrame, config: StructureConfig | None = None) -> pd.DataFrame:
    """Detecta estructura (BOS/CHOCH/FVG/OB/SWEEP) en un DataFrame M15."""
    if config is None:
        config = StructureConfig(swing_lookback=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ms = detect_market_structure(df, config)
    for col in ["bos_dir", "bos_status", "choch_dir", "choch_status",
                "fvg_bullish", "fvg_bearish", "ob_bullish", "ob_bearish",
                "ob_direction", "liquidity_sweep_up", "liquidity_sweep_down",
                "displacement_bullish", "displacement_bearish", "swing_high", "swing_low"]:
        if col in ms.frame.columns:
            df[col] = ms.frame[col]
    return df


def m15_to_objects(df: pd.DataFrame, tf: str = "M15") -> list[MarketObject]:
    """Convierte un df M15 enriquecido en lista de MarketObject (CANDLE)."""
    objs = []
    for i, (ts, row) in enumerate(df.iterrows()):
        meta = {col: row[col] for col in df.columns if col not in ("open", "high", "low", "close", "volume")}
        meta["time"] = ts
        meta["high"] = float(row["high"])
        meta["low"]  = float(row["low"])
        meta["open"] = float(row["open"])
        meta["close"]= float(row["close"])
        objs.append(MarketObject(
            type=ObjectType.CANDLE,
            origin_tf=tf,
            role=Role.REFINEMENT,
            state=ObjectState.ACTIVE,
            bar_index=i,
            bar_time=ts,
            meta=meta,
        ))
    return objs


def compute_bias_at(frames: dict, h4_ts: pd.Timestamp) -> HtfBias:
    """Sesgo HTF en el cierre de una vela H4 (punto de decisión)."""
    d1 = frames["D1"].loc[frames["D1"].index <= h4_ts]
    h4 = frames["H4"].loc[frames["H4"].index <= h4_ts]
    h1 = frames["H1"].loc[frames["H1"].index <= h4_ts]
    if len(d1) < 2 or len(h4) < 2 or len(h1) < 2:
        return HtfBias(d1=NEUTRAL, h4=NEUTRAL, h1=NEUTRAL)
    return compute_htf_bias(d1, h4, h1)


def run_sequence_on_objects(
    objects: list[MarketObject],
    state: SequenceState,  # contiene direction y otros flags
    config: SequenceConfig | None = None,
) -> dict:
    """Ejecuta el funnel A7 sobre objetos M15 usando el estado (incluye direction)."""
    if config is None:
        config = SequenceConfig()
    # run_sequence espera: (objects, direction, config)
    return run_sequence(objects, state.direction, config)


def compute_sl_tp(
    frames: dict,
    t: pd.Timestamp,
    direction: int,
    sweep_ts: pd.Timestamp | None = None,
    exec_tf: str = "M15",
) -> dict:
    """Capa 3: fine execution SL/TP (libro 18)."""
    return fine_execution(
        ms=frames,
        t=t,
        direction=direction,
        exec_tf=exec_tf,
        rr=3.0,
        sweep_ts=sweep_ts,
    )


# ── pipeline principal ─────────────────────────────────────────────────────

def run_demo(
    m15: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end:   pd.Timestamp | None = None,
    sample_days: int = 30,
):
    """
    Ejecuta el pipeline completo sobre las primeras `sample_days` velas H4.
    """
    frames = build_mtf_frames(m15)

    if start is None:
        start = frames["H4"].index[5]
    if end is None:
        end = frames["H4"].index[min(sample_days, len(frames["H4"])-1)]

    h4_slice = frames["H4"].loc[start:end]
    results: list[dict] = []

    print(f"\n{'═'*60}")
    print(f"  PIPELINE ICT — Top-Down Gate (primer año: 2006)")
    print(f"  Ventana: {start.date()} → {end.date()}  ({len(h4_slice)} velas H4)")
    print(f"{'═'*60}\n")

    for idx, (h4_ts, h4_row) in enumerate(h4_slice.iterrows()):
        bias = compute_bias_at(frames, h4_ts)
        if bias.direction == NEUTRAL:
            continue

        direction = 1 if bias.direction == BULLISH else -1
        dir_label = "LONG" if direction == 1 else "SHORT"

        print(f"[{idx+1:03d}/{len(h4_slice)}] H4={h4_ts.strftime('%Y-%m-%d %H:%M')}  "
              f"Bias={bias.direction}  D1={bias.d1} H4={bias.h4} H1={bias.h1}")

        # A7 Funnel
        m15_until_h4 = frames["M15"].loc[frames["M15"].index <= h4_ts].copy()
        m15_enr = enrich_frame(m15_until_h4)
        objects   = m15_to_objects(m15_enr)
        state = SequenceState()  # estado vacío
        state.direction = direction
        seq_result = run_sequence_on_objects(objects, state, config=None)

        signals = seq_result.get("signals", [])
        if not signals:
            print(f"           {dir_label}  →  sin señal")
            continue

        signal = signals[-1]
        sig_phase = signal.get("phase", "?")
        sig_bar  = signal.get("bar_index", -1)
        sig_time = signal.get("bar_time", h4_ts)
        sig_level = signal.get("zone_high", float("nan"))
        if np.isnan(sig_level):
            sig_level = signal.get("zone_low", float("nan"))

        print(f"           {dir_label}  ✓ Señal: {sig_phase}  @ bar={sig_bar}  nivel={sig_level:.5f}")

        # Capa 3: Fine Execution
        sweep_ts = signal.get("sweep_ts", None)
        exec_result = compute_sl_tp(frames, h4_ts, direction, sweep_ts, exec_tf="M15")

        if not exec_result.get("ok", False):
            reason = exec_result.get("reason", "?")
            print(f"           {dir_label}  ✗ fine_exec falló: {reason}\n")
            continue

        entry = exec_result["entry"]
        sl     = exec_result["sl"]
        tp     = exec_result["tp"]
        tp_ext = exec_result["tp_ext"]
        rr     = exec_result["rr"]
        rng    = exec_result["rng_exec"]
        buf    = STRUCT_SL_BUFFER_RANGE

        risk   = abs(entry - sl)
        reward = abs(tp - entry)
        rr_act = reward / risk if risk > 0 else 0

        print(f"           {dir_label}  ENTRY={entry:.5f}  SL={sl:.5f}  TP={tp:.5f}  "
              f"TP_ext={tp_ext:.5f}  RR={rr_act:.2f}  rng={rng:.5f}  buf={buf}")

        results.append({
            "h4_ts": h4_ts,
            "direction": dir_label,
            "bias": bias.direction,
            "signal_phase": sig_phase,
            "signal_bar": sig_bar,
            "signal_level": sig_level,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "tp_ext": tp_ext,
            "rr": rr_act,
            "rng_exec": rng,
            "buffer": buf,
            "risk_pips": risk * 10000,
            "reward_pips": reward * 10000,
        })
        print()

    print(f"\n{'═'*60}")
    print(f"  RESUMEN — {len(results)} señales en la ventana")
    print(f"{'═'*60}")
    if results:
        df_res = pd.DataFrame(results)
        print(f"  Long:  {(df_res.direction=='LONG').sum()}")
        print(f"  Short: {(df_res.direction=='SHORT').sum()}")
        print(f"  R/R promedio: {df_res['rr'].mean():.2f}  (min={df_res['rr'].min():.2f}  max={df_res['rr'].max():.2f})")
        print(f"  SL promedio (pips): {df_res['risk_pips'].mean():.1f}")
        print(f"  TP promedio (pips):  {df_res['reward_pips'].mean():.1f}")
        print(f"\n  Fases de señal:")
        for phase, cnt in df_res.signal_phase.value_counts().items():
            print(f"    {phase}: {cnt}")

        out_path = REPO / "reports" / f"topdown_gate_2006_{datetime.now().strftime('%H%M%S')}.csv"
        df_res.to_csv(out_path, index=False)
        print(f"\n  ✓ Resultados salvados → {out_path}")
    else:
        print("  Sin señales en la ventana analizada.")
    return results


if __name__ == "__main__":
    print("Cargando datos EURUSD M15 2006 …")
    m15 = load_m15(year=2006)

    run_demo(
        m15=m15,
        sample_days=30,
    )