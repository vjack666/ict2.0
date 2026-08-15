"""ict_backtest/plot_equity_curve.py — Capa 2 (params optimos) + curva de equidad.

Re-corre la Capa 2 (sequence) con los params optimos de la Capa 3 y grafica
la curva de equidad (R acumulado) por tiempo de salida de cada trade.

Uso:
  python ict_backtest/plot_equity_curve.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless: genera PNG, no abre ventana
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames  # noqa: E402
from engine.market_structure import detect_market_structure  # noqa: E402
from ict_backtest.sequence import run_sequence, SequenceConfig  # noqa: E402
from ict_backtest._util import closed_row_at_time, tf_duration, avg_candle_range  # noqa: E402
from ict_backtest.engine import simulate_trade, ICTSignal  # noqa: E402

SYMBOL, HTF, LTF = "EURUSD", "H4", "M15"
DISPLACE_GAP, BOS_GAP = 12, 8
REQ_DISP = True
TP_MODE = "liquidity"
MAX_HOLD = 96


def main() -> None:
    print(f"[PLOT] Cargando {SYMBOL} {HTF}/{LTF} + market_structure ...", flush=True)
    frames = load_frames(SYMBOL, (HTF, LTF, "D1"))
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[LTF].reset_index(drop=True)
    htf_df = ms.get(HTF, ltf_df)

    def est_htf_fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(HTF))
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    print("[PLOT] run_sequence (params optimos Capa 3) ...", flush=True)
    raw_sigs, _phases = run_sequence(
        ltf_df, est_htf_fn,
        SequenceConfig(counter_trend=False, tp_mode=TP_MODE,
                       require_displacement=REQ_DISP,
                       displace_gap=DISPLACE_GAP, bos_gap=BOS_GAP))

    signals = []
    rng_series = avg_candle_range(ltf_df, window=50)
    for s in raw_sigs:
        direction = s["direction"]
        entry = s["entry"]
        rng = float(rng_series.iloc[s["entry_at"]]) if s["entry_at"] < len(rng_series) else 0.0
        if not (rng > 0):
            continue
        bos_lvl = s.get("bos_level", float("nan"))
        sl = bos_lvl - 0.5 * rng if np.isfinite(bos_lvl) else entry - rng
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp = entry + 2.0 * risk if direction == 1 else entry - 2.0 * risk
        signals.append(ICTSignal(symbol=SYMBOL, time=s["time"], direction=direction,
                                 entry=entry, stop_loss=sl, take_profit=tp,
                                 model="sequence"))

    print(f"[PLOT] {len(signals)} senales -> simulando trades ...", flush=True)
    rows = []
    for sig in signals:
        trade, meta = simulate_trade(ltf_df, sig, MAX_HOLD)
        if trade is not None:
            rows.append({"exit_time": pd.to_datetime(trade.exit_time),
                         "pnl_r": trade.pnl_r,
                         "reason": meta.get("exit_reason", "n/a") if isinstance(meta, dict) else "n/a",
                         "direction": trade.direction})
    df = pd.DataFrame(rows).sort_values("exit_time").reset_index(drop=True)
    df["equity"] = df["pnl_r"].cumsum()
    df["peak"] = df["equity"].cummax()
    df["drawdown"] = df["equity"] - df["peak"]

    print(f"[PLOT] trades={len(df)} PF={df['pnl_r'].clip(lower=0).sum()/df['pnl_r'].clip(upper=0).abs().sum():.3f} "
          f"WR={(df['pnl_r']>0).mean()*100:.1f}% total_R={df['pnl_r'].sum():.1f} maxDD={df['drawdown'].min():.1f}", flush=True)

    # --- Grafica ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(f"Capa 2 EURUSD M15 (params optimos Capa 3) — curva de equidad\n"
                 f"displace_gap={DISPLACE_GAP} bos_gap={BOS_GAP} req_disp={REQ_DISP} tp={TP_MODE}",
                 fontsize=13, fontweight="bold")

    ax1.plot(df["exit_time"], df["equity"], color="#1f77b4", lw=1.4, label="Equidad (R acum)")
    ax1.fill_between(df["exit_time"], df["equity"], 0,
                     where=df["equity"] >= 0, color="#1f77b4", alpha=0.15)
    ax1.fill_between(df["exit_time"], df["equity"], 0,
                     where=df["equity"] < 0, color="#d62728", alpha=0.15)
    # marcar trades ganadores/perdedores
    wins = df[df["pnl_r"] > 0]
    loss = df[df["pnl_r"] <= 0]
    ax1.scatter(wins["exit_time"], wins["equity"], color="#2ca02c", s=14, zorder=3, label="Trade +R")
    ax1.scatter(loss["exit_time"], loss["equity"], color="#d62728", s=14, zorder=3, label="Trade -R")
    ax1.axhline(0, color="k", lw=0.8)
    ax1.set_ylabel("R acumulado")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.25)

    ax2.fill_between(df["exit_time"], df["drawdown"], 0, color="#d62728", alpha=0.3)
    ax2.plot(df["exit_time"], df["drawdown"], color="#d62728", lw=1.0)
    ax2.set_ylabel("Drawdown (R)")
    ax2.grid(alpha=0.25)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.set_xlabel("Tiempo (salida de cada trade)")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = ROOT / "docs" / "ict" / "plots" / "CAPA2_EQUITY_CURVE_OPT.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    print(f"[PLOT] guardado: {out}", flush=True)


if __name__ == "__main__":
    main()
