"""Grafico de lectura HTF (D1/H4/H1) sobre datos reales EURUSD.

Objetivo: mostrar hasta donde llega el setup HOY para plan de trading del lunes.
- 3 paneles apilados (D1, H4, H1)
- velas + zonas PD array (premium/discount) + OB/FVG detectados
- sesgo del orquestador por vela (barra lateral de color)
- ultimo sweep de liquidez y nivel actual
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, ".")
from engine.market_features import build_features
from orchestration.orchestrator import AgentOrchestrator


def load(tf, n=None):
    df = pd.read_parquet(f"data/raw/EURUSD/EURUSD_{tf}.parquet")
    if n:
        df = df.tail(n)
    return df


def bias_color(b):
    return {"BULLISH": "green", "BEARISH": "red"}.get(b, "gray")


def plot_tf(ax, df, feat, out, tf, last_n=120):
    d = df.tail(last_n).reset_index(drop=True)
    f = feat.tail(last_n).reset_index(drop=True)
    o = out.tail(last_n).reset_index(drop=True)
    x = np.arange(len(d))
    up = d["close"] >= d["open"]
    ax.vlines(x[up], d["low"][up], d["high"][up], color="green", lw=0.6, alpha=0.7)
    ax.vlines(x[~up], d["low"][~up], d["high"][~up], color="red", lw=0.6, alpha=0.7)
    ax.vlines(x[up], d["open"][up], d["close"][up], color="green", lw=2.5)
    ax.vlines(x[~up], d["open"][~up], d["close"][~up], color="red", lw=2.5)

    # zona premium/discount (trapecio discreto por vela)
    if "premium_discount_zone" in f.columns:
        for i in range(len(f)):
            z = f["premium_discount_zone"].iloc[i]
            if pd.isna(z):
                continue
            col = {"PREMIUM": "red", "DISCOUNT": "green", "EQUILIBRIUM": "gray"}.get(z, "gray")
            ax.axhline(y=d["close"].iloc[i], color=col, lw=0.0)
        # dibujar banda como texto al final
    # OB bullish/bearish como rectangulos en la vela donde aparecen
    for col, kind in [("ob_bullish", "BULL"), ("ob_bearish", "BEAR")]:
        if col in f.columns:
            for i in range(len(f)):
                if f[col].iloc[i] and not pd.isna(f[col].iloc[i]):
                    lo = min(d["open"].iloc[i], d["close"].iloc[i])
                    hi = max(d["open"].iloc[i], d["close"].iloc[i])
                    c = "green" if kind == "BULL" else "red"
                    ax.add_patch(Rectangle((i - 0.4, lo), 0.8, hi - lo,
                                           fill=False, edgecolor=c, lw=1.0, alpha=0.6))

    # barra de sesgo del orquestador al fondo
    for i in range(len(o)):
        b = o["agent_decision_bias"].iloc[i]
        ax.axvline(i, color=bias_color(b), lw=3, alpha=0.10, ymin=0.0, ymax=1.0)

    # nivel actual
    last_close = d["close"].iloc[-1]
    ax.axhline(last_close, color="black", lw=0.8, ls="--")
    ax.text(len(d) - 1, last_close, f" {last_close:.5f}", va="center", fontsize=8)

    ax.set_title(f"{tf}  |  sesgo Hoy: {o['agent_decision_bias'].iloc[-1]} "
                 f"(conf {o['agent_decision_confidence'].iloc[-1]:.2f})", fontsize=10)
    ax.tick_params(labelsize=7)
    ax.set_xticks([])


def main():
    orch = AgentOrchestrator()
    figs, axes = plt.subplots(3, 1, figsize=(16, 11), sharex=False)
    summary = {}
    for ax, tf in zip(axes, ["D1", "H4", "H1"]):
        df = load(tf)
        feat = build_features(df)
        out = orch.analyze_context(feat)
        plot_tf(ax, df, feat, out, tf, last_n=140)
        # resumen de sesgo en las ultimas 20 velas
        recent = out["agent_decision_bias"].tail(20)
        vc = recent.value_counts().to_dict()
        summary[tf] = {
            "sesgo_hoy": out["agent_decision_bias"].iloc[-1],
            "confianza": round(float(out["agent_decision_confidence"].iloc[-1]), 3),
            "distrib_20v": vc,
            "ultima_ventana": str(df["time"].iloc[-1]),
        }
    plt.tight_layout()
    out_p = "docs/lectura_HTF_EURUSD.png"
    plt.savefig(out_p, dpi=110)
    print("GRAFICO:", out_p)
    print("RESUMEN HTF:")
    for tf, s in summary.items():
        print(f"  {tf}: sesgo={s['sesgo_hoy']} conf={s['confianza']} | ultima vela {s['ultima_ventana']} | 20v {s['distrib_20v']}")


if __name__ == "__main__":
    main()
