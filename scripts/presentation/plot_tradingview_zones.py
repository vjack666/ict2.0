"""Genera gráficos oscuros tipo TradingView para lectura EURUSD.

Solo percepción: velas, volumen, EQ/premium-discount y objetos canónicos
FVG/OB. No genera entry, SL, TP ni órdenes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.market_features import build_features


DATA_ROOT = ROOT / "data" / "raw"
OUT_ROOT = ROOT / "reports" / "charts"
TIMEFRAMES = ("D1", "H4", "H1", "M15")
WINDOWS = {"D1": 120, "H4": 160, "H1": 220, "M15": 260}
CALC_WINDOWS = {"D1": 500, "H4": 1500, "H1": 5000, "M15": 12000}

BG = "#0d1117"
PANEL = "#161b22"
GRID = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
BULL = "#26a69a"
BEAR = "#ef5350"
FVG_BULL = "#1b5e20"
FVG_BEAR = "#8e2424"
OB_BULL = "#4fc3f7"
OB_BEAR = "#ffb74d"


def _load(symbol: str, tf: str) -> pd.DataFrame:
    path = DATA_ROOT / symbol / f"{symbol}_{tf}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo MT5: {path}")
    df = pd.read_parquet(path).copy()
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    return df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)


def _zone_objects(df: pd.DataFrame, tf: str):
    rows = df[["time", "open", "high", "low", "close"]].to_dict("records")
    fvgs = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    obs = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    return fvgs, obs


def _timestamp(value) -> pd.Timestamp | None:
    value = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(value) else value


def _select_recent(objects, visible_start: pd.Timestamp, last_time: pd.Timestamp, current_low: float, current_high: float):
    candidates = []
    for obj in objects:
        confirm = _timestamp(obj.confirmation_time)
        if confirm is None or confirm > last_time:
            continue
        if confirm < visible_start - (last_time - visible_start) * 0.30:
            continue
        if obj.zone_high < current_low or obj.zone_low > current_high:
            continue
        candidates.append(obj)
    candidates.sort(key=lambda obj: (_timestamp(obj.confirmation_time), str(obj.id)))
    # Keep the chart readable while preserving the most recent zones by side.
    selected = []
    for direction in (1, -1):
        side = [obj for obj in candidates if int(obj.direction) == direction]
        selected.extend(side[-2:])
    return sorted(selected, key=lambda obj: (_timestamp(obj.confirmation_time), str(obj.id)))


def _x_for_time(times: pd.Series, value: object) -> int:
    ts = _timestamp(value)
    if ts is None:
        return 0
    return int(times.searchsorted(ts, side="left"))


def _format_price(value: float) -> str:
    return f"{value:.5f}"


def _plot(symbol: str, tf: str, out_path: Path) -> dict:
    raw = _load(symbol, tf)
    window = min(WINDOWS[tf], len(raw))
    visible = raw.tail(window).reset_index(drop=True)
    calc = raw.tail(min(CALC_WINDOWS[tf], len(raw))).reset_index(drop=True)
    features = build_features(calc)
    fvgs, obs = _zone_objects(calc, tf)

    times = visible["time"]
    last_time = times.iloc[-1]
    last_close = float(visible["close"].iloc[-1])
    range_high = float(visible["high"].max())
    range_low = float(visible["low"].min())
    eq = (range_high + range_low) / 2.0
    selected_fvgs = _select_recent(fvgs, times.iloc[0], last_time, range_low, range_high)
    selected_obs = _select_recent(obs, times.iloc[0], last_time, range_low, range_high)

    fig = plt.figure(figsize=(18, 9), facecolor=BG, layout="constrained")
    grid = fig.add_gridspec(4, 1, height_ratios=[3.8, 0.8, 0.10, 0.10], hspace=0.02)
    ax = fig.add_subplot(grid[0, 0], facecolor=PANEL)
    vol_ax = fig.add_subplot(grid[1, 0], sharex=ax, facecolor=PANEL)

    ax.axhspan(eq, range_high, color=BEAR, alpha=0.035, zorder=0)
    ax.axhspan(range_low, eq, color=BULL, alpha=0.035, zorder=0)
    ax.axhline(eq, color=MUTED, lw=0.8, ls="--", alpha=0.8, zorder=1)
    ax.text(0.995, 0.965, f"PREMIUM  >  EQ {_format_price(eq)}", transform=ax.transAxes,
            color=BEAR, ha="right", va="top", fontsize=8, alpha=0.85)
    ax.text(0.995, 0.035, "DISCOUNT", transform=ax.transAxes,
            color=BULL, ha="right", va="bottom", fontsize=8, alpha=0.85)

    # Draw zones behind candles; rectangles extend to the current chart edge.
    for obj in selected_fvgs:
        x0 = max(0, _x_for_time(times, obj.confirmation_time))
        x1 = len(visible) - 1
        color = FVG_BULL if obj.direction > 0 else FVG_BEAR
        edge = BULL if obj.direction > 0 else BEAR
        ax.add_patch(Rectangle((x0 - 0.5, obj.zone_low), max(0.5, x1 - x0 + 0.5),
                               obj.zone_high - obj.zone_low, facecolor=color,
                               edgecolor=edge, linewidth=0.8, alpha=0.22, zorder=1))
        label = "FVG BULL" if obj.direction > 0 else "FVG BEAR"
        ax.text(x0 + 1, obj.zone_high, f"{label} {_format_price(obj.zone_low)}–{_format_price(obj.zone_high)}",
                color=edge, fontsize=7, va="bottom", alpha=0.95, zorder=4)

    for obj in selected_obs:
        x0 = max(0, _x_for_time(times, obj.confirmation_time))
        x1 = len(visible) - 1
        color = OB_BULL if obj.direction > 0 else OB_BEAR
        ax.add_patch(Rectangle((x0 - 0.5, obj.zone_low), max(0.5, x1 - x0 + 0.5),
                               obj.zone_high - obj.zone_low, facecolor="none",
                               edgecolor=color, linewidth=1.0, linestyle=":", alpha=0.95, zorder=2))
        label = "OB BULL" if obj.direction > 0 else "OB BEAR"
        ax.text(x0 + 1, obj.zone_low, label, color=color, fontsize=7, va="top", alpha=0.95, zorder=4)

    # Candles and volume.
    width = 0.68
    for i, row in visible.iterrows():
        up = float(row["close"]) >= float(row["open"])
        color = BULL if up else BEAR
        ax.vlines(i, row["low"], row["high"], color=color, linewidth=0.75, alpha=0.9, zorder=3)
        bottom = min(float(row["open"]), float(row["close"]))
        height = max(abs(float(row["close"]) - float(row["open"])), 1e-7)
        ax.add_patch(Rectangle((i - width / 2, bottom), width, height,
                               facecolor=color, edgecolor=color, linewidth=0.5, zorder=3))
        volume = float(row.get("tick_volume", 0.0) or 0.0)
        vol_ax.bar(i, volume, width=width, color=color, alpha=0.45, linewidth=0)

    ax.axhline(last_close, color=TEXT, linewidth=0.8, linestyle="--", alpha=0.9, zorder=5)
    ax.text(len(visible) - 1, last_close, f"  {last_close:.5f}", color=TEXT,
            fontsize=9, va="center", ha="left", zorder=6)
    ax.set_ylim(range_low - (range_high - range_low) * 0.04, range_high + (range_high - range_low) * 0.04)
    ax.set_xlim(-2, len(visible) + 2)
    ax.set_ylabel("Precio", color=TEXT, fontsize=9)
    vol_ax.set_ylabel("Vol", color=MUTED, fontsize=8)
    vol_ax.set_xlabel("Tiempo UTC", color=TEXT, fontsize=9)
    tick_idx = sorted({round(i * (len(visible) - 1) / 7) for i in range(8)})
    vol_ax.set_xticks(tick_idx)
    vol_ax.set_xticklabels(
        [times.iloc[i].strftime("%m-%d\n%H:%M") for i in tick_idx],
        color=MUTED,
        fontsize=8,
    )

    for current_ax in (ax, vol_ax):
        current_ax.grid(True, color=GRID, linewidth=0.45, alpha=0.65)
        current_ax.tick_params(colors=MUTED, labelsize=8)
        for spine in current_ax.spines.values():
            spine.set_color(GRID)
        current_ax.yaxis.label.set_color(MUTED)

    trend = str(features.iloc[-1].get("trend", "RANGING"))
    title = f"{symbol} · {tf} · lectura MT5 · {last_time.strftime('%Y-%m-%d %H:%M UTC')}"
    fig.suptitle(title, color=TEXT, fontsize=14, x=0.08, ha="left", y=0.98)
    ax.set_title(
        f"Trend motor: {trend}  |  Close: {_format_price(last_close)}  |  EQ visible: {_format_price(eq)}  |  READ ONLY",
        color=MUTED, fontsize=9, loc="left", pad=8,
    )
    fig.text(0.08, 0.015, "FVG rellena · OB contorno punteado · EQ línea discontinua · zonas visuales, no entrada",
             color=MUTED, fontsize=8)
    fig.savefig(out_path, dpi=140, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return {
        "tf": tf,
        "last_time": str(last_time),
        "close": last_close,
        "trend": trend,
        "eq": eq,
        "fvg_count": len(selected_fvgs),
        "ob_count": len(selected_obs),
        "path": str(out_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gráficos TradingView-like de zonas canónicas EURUSD")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--tfs", default="D1 H4 H1 M15")
    args = parser.parse_args()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    tfs = [tf.upper() for tf in args.tfs.replace(",", " ").split() if tf.upper() in TIMEFRAMES]
    if not tfs:
        raise SystemExit("No hay temporalidades válidas")
    for tf in tfs:
        out = OUT_ROOT / f"{args.symbol.upper()}_{tf}_tradingview.png"
        print(_plot(args.symbol.upper(), tf, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
