"""scripts/run_ict_2006_batch.py — Pipeline ICT 2006 por mes en background.

Ejecuta run_visual_replay mes a mes para evitar timeout.
Resultado: CSV con todas las señales del año + resumen de win rate.
"""
from __future__ import annotations

import sys, json, warnings
from pathlib import Path
from datetime import datetime

REPO = Path(r"C:\Users\v_jac\Desktop\ICT SYSTEM")
sys.path.insert(0, str(REPO))

import pandas as pd
import numpy as np
warnings.filterwarnings("ignore")

from backtest.replay import run_visual_replay, ReplayConfig
from engine.sequence import SequenceConfig
from engine.market_features import build_features

MONTHLY_DIR = REPO / "datasets" / "eurusd_dukascopy_intraday_2006_2010" / "raw_monthly" / "2006"

def load_month(year: int, month: int) -> pd.DataFrame:
    """Carga un mes del directorio monthly."""
    path = MONTHLY_DIR / f"EURUSD_M15_{year}-{month:02d}.csv"
    if not path.exists():
        path = MONTHLY_DIR / f"eurusd-m15-bid-{year}-{month:02d}-01-{year}-{month+1 if month < 12 else year}-01.csv"
    if not path.exists():
        # buscar por glob
        import glob
        candidates = list(MONTHLY_DIR.glob(f"*{year}-{month:02d}*.csv"))
        if candidates:
            path = candidates[0]
        else:
            raise FileNotFoundError(f"No CSV para {year}-{month:02d} en {MONTHLY_DIR}")
    df = pd.read_csv(path)
    # Normalizar columnas
    if "timestamp" in df.columns:
        df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    elif "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        if df["time"].isna().all():
            df["time"] = pd.to_datetime(df.iloc[:, 0], unit="ms", utc=True)
    df = df.dropna(subset=["time"])
    df["time"] = df["time"].dt.tz_localize(None)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df.sort_values("time").reset_index(drop=True)
    return df[["time", "open", "high", "low", "close"]]

def resample_tf(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample con columnas time+OHLC para run_visual_replay."""
    out = df.set_index("time").resample(rule).agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna(how="all").reset_index()
    return out

def run_month(year: int, month: int) -> dict:
    """Ejecuta pipeline ICT para un mes. Devuelve dict de resultados."""
    print(f"  [{year}-{month:02d}] Cargando...", end=" ", flush=True)
    try:
        df = load_month(year, month)
    except FileNotFoundError as e:
        print(f"SALTADO: {e}")
        return {"year": year, "month": month, "n_signals": 0, "signals": [], "error": str(e)}

    print(f"{len(df)} velas. Pipeline...", end=" ", flush=True)

    # Construir frames para los 4 TFs
    frames = {
        "M15": df[["time", "open", "high", "low", "close"]],
        "H1": resample_tf(df, "1h"),
        "H4": resample_tf(df, "4h"),
        "D1": resample_tf(df, "1D"),
    }
    for tf in ["H1", "H4", "D1"]:
        if len(frames[tf]) < 2:
            print(f"TF {tf} vacío. Saltado.")
            return {"year": year, "month": month, "n_signals": 0, "signals": [], "error": f"{tf} vacío"}

    # Ejecutar replay
    cfg = ReplayConfig(
        symbol="EURUSD",
        timeframe="M15",
        htf_timeframe="H1",
        use_multitf_context=True,
        sequence=SequenceConfig(counter_trend=False),
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            artifact = run_visual_replay(frames, cfg)
    except Exception as e:
        print(f"ERROR: {e}")
        return {"year": year, "month": month, "n_signals": 0, "signals": [], "error": str(e)}

    signals = []
    for sig in (artifact.signals or []):
        sig_rec = {
            "year": year, "month": month,
            "decision_time": sig.get("decision_time"),
            "direction": "LONG" if int(sig.get("direction", 0)) > 0 else "SHORT",
            "htf_aligned": str(sig.get("features_at_t", {}).get("context_inputs", {}).get("h1_alignment", "NEUTRAL")),
            "sequence_depth": sig.get("features_at_t", {}).get("sequence_depth", 0),
            "can_trade": sig.get("can_trade", False),
        }
        signals.append(sig_rec)

    # Trades con outcome
    trades = []
    for tr in (artifact.trades or []):
        tr_rec = {
            "year": year, "month": month,
            "direction": tr.get("direction", ""),
            "entry": tr.get("entry"),
            "sl": tr.get("sl"),
            "tp": tr.get("tp"),
            "outcome": tr.get("outcome", ""),
            "exit_r": tr.get("exit_r"),
            "entry_time": tr.get("entry_time"),
            "exit_time": tr.get("exit_time"),
        }
        trades.append(tr_rec)

    print(f"✓ {len(signals)} señales, {len(trades)} trades")
    return {
        "year": year, "month": month,
        "n_signals": len(signals), "n_trades": len(trades),
        "signals": signals, "trades": trades,
        "phase_seen": getattr(artifact, "metadata", {}).get("phase_seen", {}),
        "error": None,
    }

if __name__ == "__main__":
    year = 2006
    print(f"PIPELINE ICT 2006 — por mes (batch)")
    print(f"Inicio: {datetime.now()}")
    print("=" * 50)

    all_signals = []
    all_trades = []
    phase_seen_all = {}
    errors = []

    for month in range(1, 13):
        result = run_month(year, month)
        if result["error"] and "vacío" not in result["error"]:
            errors.append(result)
        all_signals.extend(result.get("signals", []))
        all_trades.extend(result.get("trades", []))
        ps = result.get("phase_seen", {})
        for k, v in ps.items():
            phase_seen_all[k] = phase_seen_all.get(k, 0) + v

    # Guardar
    out_dir = REPO / "reports"
    out_dir.mkdir(exist_ok=True)

    if all_trades:
        df_trades = pd.DataFrame(all_trades)
        trades_path = out_dir / "ict_2006_trades.csv"
        df_trades.to_csv(trades_path, index=False)
        wins = sum(1 for t in all_trades if t.get("outcome") == "TP")
        closed = sum(1 for t in all_trades if t.get("outcome") in ("TP", "SL"))
        win_rate = (wins / closed * 100) if closed > 0 else 0
        print(f"\n{'='*50}")
        print(f"  RESULTADO 2006 — {len(all_trades)} trades")
        print(f"  WIN RATE: {win_rate:.1f}%  ({wins}/{closed})")
        print(f"  Long: {sum(1 for t in all_trades if t.get('direction')=='bullish')}")
        print(f"  Short: {sum(1 for t in all_trades if t.get('direction')=='bearish')}")
        print(f"  TP: {sum(1 for t in all_trades if t.get('outcome')=='TP')}")
        print(f"  SL: {sum(1 for t in all_trades if t.get('outcome')=='SL')}")
        print(f"  OPEN: {sum(1 for t in all_trades if t.get('outcome')=='OPEN')}")
        print(f"  Fase seen: {phase_seen_all}")
        print(f"  CSV → {trades_path}")
    else:
        print("\nSin trades. Errores:", errors)

    if all_signals:
        df_signals = pd.DataFrame(all_signals)
        sig_path = out_dir / "ict_2006_signals.csv"
        df_signals.to_csv(sig_path, index=False)
        print(f"  Señales CSV → {sig_path}")

    print(f"\nFin: {datetime.now()}")
