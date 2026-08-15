"""
BRIEF DE LECTURA ICT/WYCKOFF — preparado para revisar ANTES de la sesión NY.

ESTADO HONESTO (leer antes de usar):
  - Este script NO emite señales ejecutables. Es un MAPA DE CONTEXTO: sesgo HTF,
    zonas (dealing range / OTE), liquidez BSL/SSL, PD arrays activos (FVG/OB con
    tier), sweeps recientes, killzones a vigilar y setups a BUSCAR + nivel de
    invalidación por estructura.
  - El motor de SEÑALES (entry retorno-a-zona, TP liquidez cercana, exec_tf separado,
    RR 1:3, POI bonus anclado) está PENDIENTE (v30, ver docs/ict/CIERRE_FASE2.md).
    Por eso el brief dice "VIGILAR", no "ENTRA AHORA".
  - Sin feed en vivo: usa data/raw/*.parquet (corte al 2026-08-06 aprox). El brief
    marca la fecha del dato para que veas el desfase.
  - macro_direction / market_regime / divergence / volume_confirmed NO se producen
    hoy en el motor; el sesgo HTF se infiere de `trend` D1/H4 (válido como lectura).

Uso:
  .venv/Scripts/python.exe scripts/brief_lunes.py [--symbols EURUSD GBPUSD XAUUSD USDJPY]
Salida:
  docs/briefs/brief_<YYYY-MM-DD>.md   (uno por corrida, fecha de GENERACION)
"""

from __future__ import annotations
import argparse
import os
import sys
import time
import datetime as dt

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SYMS_DEFAULT = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]
# Para el brief solo necesitamos la cola reciente: el M15 completo (114k barras)
# tarda ~56s en build_features; con 4000 barras (~42 dias) basta y corre en <3s.
M15_TAIL = 4000
# Para sesgo HTF solo usamos la ultima barra de cada TF; una cola larga basta
# y build_features corre rapido. H1 de EURUSD (138k barras) era el cuello de botella.
TAIL = {"D1": 2000, "H4": 5000, "H1": 5000, "M15": M15_TAIL}
GENERATED = dt.datetime.now(dt.timezone.utc)


def ok(x):
    """True si x es un valor util (no None, no NaN)."""
    return x is not None and not pd.isna(x)


def as_float(value):
    """Convierte un valor a float de forma segura, devolviendo None si no aplica."""
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return None
        try:
            return float(txt)
        except ValueError:
            return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# Ventanas killzone (documentadas en docs/ict/01_KILLZONES.md y 18).
# ET en verano (EDT = UTC-4). Ecuador = UTC-5 => restar 1h en agosto.
KILLZONES = [
    ("London Open",   "02:00-05:00 ET", "01:00-04:00 Ecuador (ago)"),
    ("New York AM",   "08:30-11:00 ET", "07:30-10:00 Ecuador (ago)"),
    ("New York PM",   "13:00-16:00 ET", "12:00-15:00 Ecuador (ago)"),
    ("Silver Bullet", "10:00-11:00 ET / 14:00-15:00 ET", "09:00-10:00 / 13:00-14:00 Ecuador (ago)"),
]


def load_raw(sym, tf, tail=None):
    p = os.path.join(ROOT, "data", "raw", sym, f"{sym}_{tf}.parquet")
    if not os.path.exists(p):
        return None, None
    df = pd.read_parquet(p)
    tcol = [c for c in df.columns if c.lower() in ("time", "timestamp", "datetime", "date")][0]
    if tcol != "time":
        df = df.rename(columns={tcol: "time"})
    mx = pd.to_datetime(df["time"]).max()
    if tail:
        df = df.tail(tail).reset_index(drop=True)
    return df, mx


def compute(sym):
    """Construye features UNA vez por símbolo para todos los TF necesarios."""
    out = {}
    dates = {}
    t0 = time.time()
    from engine.market_features import build_features
    for tf, tail in [("D1", TAIL["D1"]), ("H4", TAIL["H4"]), ("H1", TAIL["H1"]), ("M15", TAIL["M15"])]:
        df, mx = load_raw(sym, tf, tail)
        if df is None or len(df) < 50:
            out[tf] = None
            dates[tf] = mx
            continue
        out[tf] = build_features(df.copy())
        dates[tf] = mx
    return out, dates, time.time() - t0


def last_val(f, col):
    if f is None or col not in f.columns:
        return None
    s = f[col].dropna()
    return s.iloc[-1] if len(s) else None


def active_pd_array(f, side):
    if f is None:
        return None
    col = f"fvg_{side}"
    if col not in f.columns:
        return None
    sub = f[f[col].fillna(False).astype(bool)].tail(5)
    if len(sub) == 0:
        return None
    r = sub.iloc[-1]
    price = last_val(f, "close")
    mid = r.get("fvg_mid", np.nan)
    atr = last_val(f, "atr")
    dist = (price - mid) / atr if ok(mid) and ok(atr) and atr else np.nan
    return {
        "type": "FVG",
        "mid": mid,
        "tier": r.get("pd_tier", None),
        "dist_atr": dist,
        "fill": r.get("fvg_fill_status", None),
    }


def recent_sweep(f, n=30):
    if f is None:
        return None
    out = []
    dn = f[f["liquidity_sweep_down"].fillna(False).astype(bool)].tail(n)
    up = f[f["liquidity_sweep_up"].fillna(False).astype(bool)].tail(n)
    if len(dn):
        out.append(("SSL (bear sweep / liquida largos)", dn.iloc[-1].get("sweep_low")))
    if len(up):
        out.append(("BSL (bull sweep / liquida cortos)", up.iloc[-1].get("sweep_high")))
    return out or None


def htf_bias(f_d1, f_h4, f_h1):
    d1 = last_val(f_d1, "trend")
    h4 = last_val(f_h4, "trend")
    h1 = last_val(f_h1, "trend")
    if ok(d1) and ok(h4) and d1 == h4:
        bias, src = d1, "D1+H4"
    elif ok(h4):
        bias, src = h4, "H4"
    elif ok(d1):
        bias, src = d1, "D1"
    else:
        bias, src = "RANGING", "n/a"
    return bias, src, {"D1": d1, "H4": h4, "H1": h1}


def build_symbol_section(sym, feats, last_dates):
    lines = [f"\n## {sym}\n"]
    f_d1, f_h4, f_h1, f_m15 = (feats.get(t) for t in ["D1", "H4", "H1", "M15"])
    if all(v is None for v in (f_d1, f_h4, f_h1, f_m15)):
        lines.append("\n  **SIN DATOS para este símbolo** — se omite.\n")
        return "\n".join(lines)

    t0 = time.time()
    price = last_val(f_m15, "close")
    bias, src, per_tf = htf_bias(f_d1, f_h4, f_h1)

    ld = {tf: (str(d)[:16] if d is not None else "—") for tf, d in last_dates.items()}

    # advertencia de desfase de datos
    m15_date = last_dates.get("M15")
    if m15_date is not None:
        dias = (GENERATED - m15_date).total_seconds() / 86400.0
        if dias > 3:
            lines.append(f"> ⚠️ **DESFASE DE DATOS:** el M15 llega hasta {ld['M15']} "
                         f"(hace ~{dias:.0f} días). El brief es contexto, no espejo del lunes en vivo.")
            lines.append("")
    lines.append(f"- **Precio actual (M15 cierre):** `{price:.5f}`" if ok(price) else "- precio n/a")
    lines.append(f"- **Sesgo HTF:** `{bias}` (fuente {src}) · D1={per_tf['D1']} H4={per_tf['H4']} H1={per_tf['H1']}")
    lines.append(f"- **Datos hasta:** D1 {ld['D1']} · H4 {ld['H4']} · H1 {ld['H1']} · M15 {ld['M15']}")
    lines.append("")

    # Dealing range (H4)
    lines.append("### Zona (dealing range H4)")
    pdr = last_val(f_h4, "premium_discount_zone")
    zh = last_val(f_h4, "zone_high"); zl = last_val(f_h4, "zone_low"); zm = last_val(f_h4, "zone_mid")
    olmin = last_val(f_h4, "ote_long_min"); olmax = last_val(f_h4, "ote_long_max")
    osmin = last_val(f_h4, "ote_short_min"); osmax = last_val(f_h4, "ote_short_max")
    lines.append(f"- Zona premium/discount: `{pdr}`")
    if ok(zh) and ok(zl):
        lines.append(f"- Rango H4: high `{zh:.5f}` · low `{zl:.5f}` · mid `{zm:.5f}`")
    if ok(olmin):
        lines.append(f"- OTE LONG (62-79% retrace): `{olmin:.5f}` – `{olmax:.5f}`")
    if ok(osmin):
        lines.append(f"- OTE SHORT (62-79% retrace): `{osmin:.5f}` – `{osmax:.5f}`")
    lines.append("")

    # Liquidez
    lines.append("### Liquidez objetivo (BSL/SSL H4)")
    bsl = last_val(f_h4, "bsl_price")
    ssl = last_val(f_h4, "ssl_price")
    price_value = as_float(price)

    bsl_value = as_float(bsl)
    if bsl_value is not None:
        if price_value is not None and abs(bsl_value - price_value) / price_value < 0.03:
            lines.append(f"- BSL (target si short / techo): `{bsl_value:.5f}`")
        else:
            lines.append(f"- BSL: `{bsl_value:.5f}` — **NO FIAR** (fuera de rango del precio actual; dato de origen inconsistente)")

    ssl_value = as_float(ssl)
    if ssl_value is not None:
        if price_value is not None and abs(ssl_value - price_value) / price_value < 0.03:
            lines.append(f"- SSL (target si long / suelo): `{ssl_value:.5f}`")
        else:
            lines.append(f"- SSL: `{ssl_value:.5f}` — **NO FIAR** (fuera de rango del precio actual; dato de origen inconsistente)")

    if bsl_value is None and ssl_value is None:
        lines.append("- sin niveles BSL/SSL calculados")
    lines.append("")

    # PD arrays activos (M15)
    lines.append("### PD arrays activos (M15 — zonas de reacción)")
    for side, lbl in [("bullish", "LONG"), ("bearish", "SHORT")]:
        pa = active_pd_array(f_m15, side)
        if pa and ok(pa["mid"]):
            dist = f" ({pa['dist_atr']:.1f} ATR del precio)" if ok(pa["dist_atr"]) else ""
            tier = f" tier={pa['tier']}" if ok(pa["tier"]) else ""
            lines.append(f"- FVG {lbl}: mid `{pa['mid']:.5f}`{tier} · fill={pa['fill']}{dist}")
    ob_b = last_val(f_m15, "ob_bullish")
    ob_be = last_val(f_m15, "ob_bearish")
    if bool(ob_b) or bool(ob_be):
        obt = last_val(f_m15, "ob_top")
        obb = last_val(f_m15, "ob_bottom")
        if ok(obt):
            lines.append(f"- OB activo: top `{obt:.5f}` · bottom `{obb:.5f}`")
    lines.append("")

    # Sweeps recientes
    lines.append("### Sweeps recientes (M15)")
    sw = recent_sweep(f_m15)
    if sw:
        for name, lvl in sw:
            if ok(lvl):
                lines.append(f"- {name}: nivel `{lvl:.5f}`")
    else:
        lines.append("- sin sweep marcado en las últimas 30 velas")
    lines.append("")

    # Killzones
    lines.append("### Killzones a vigilar (sesión NY)")
    for nm, et, ec in KILLZONES:
        lines.append(f"- **{nm}**: {et}  →  {ec}")
    lines.append("")

    # Setups a BUSCAR (no entrar)
    lines.append("### Setups a VIGILAR (regla dura: entry en retorno a zona, no close del BOS)")
    if bias == "BULLISH":
        if pdr in ("DISCOUNT", "OTE_LONG", "OTE"):
            lines.append("- **PO3 a-favor LONG**: precio en discount/OTE. Buscar en M15: sweep SSL + CHoCH/BOS alcista + retorno a FVG/OB. Invalidación: bajo último swing low / mecha del sweep.")
        elif pdr in ("PREMIUM", "OTE_SHORT"):
            lines.append("- Sesgo alcista pero precio en PREMIUM: NO comprar aquí. Esperar retracción a discount/OTE antes de buscar long.")
        else:
            lines.append("- Sesgo alcista, precio neutro: vigilar reacción en discount para buscar long.")
    elif bias == "BEARISH":
        if pdr in ("PREMIUM", "OTE_SHORT", "OTE"):
            lines.append("- **PO3 a-favor SHORT**: precio en premium/OTE. Buscar en M15: sweep BSL + CHoCH/BOS bajista + retorno a FVG/OB. Invalidación: sobre último swing high / mecha del sweep.")
        elif pdr in ("DISCOUNT", "OTE_LONG"):
            lines.append("- Sesgo bajista pero precio en DISCOUNT: NO vender aquí. Esperar rebote a premium antes de buscar short.")
        else:
            lines.append("- Sesgo bajista, precio neutro: vigilar reacción en premium para buscar short.")
    else:
        lines.append("- Sesgo RANGING: favorecer Turtle Soup (contratendencia tras sweep) solo si el rango es claro. Evitar entradas a-favor.")
    lines.append("")
    lines.append(f"*sección generada en {time.time()-t0:.1f}s*")
    return "\n".join(lines)


def last_date_of(sym, tf):
    p = os.path.join(ROOT, "data", "raw", sym, f"{sym}_{tf}.parquet")
    if not os.path.exists(p):
        return None
    try:
        df = pd.read_parquet(p, columns=["time"])
        return pd.to_datetime(df["time"]).max()
    except (FileNotFoundError, OSError, ValueError, TypeError, KeyError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=SYMS_DEFAULT)
    args = ap.parse_args()

    _TFS = ["D1", "H4", "H1", "M15"]
    # corte dinamico: ultima fecha real entre todos los simbolos/TFs
    cut_dates = []
    for sym in args.symbols:
        for tf in _TFS:
            d = last_date_of(sym, tf)
            if d is not None:
                cut_dates.append(d)
    cut_str = max(cut_dates).strftime("%Y-%m-%d") if cut_dates else "desconocida"

    os.makedirs(os.path.join(ROOT, "docs", "briefs"), exist_ok=True)
    out_md = os.path.join(ROOT, "docs", "briefs", f"brief_{GENERATED:%Y-%m-%d}.md")

    header = []
    header.append(f"# BRIEF DE LECTURA ICT/WYCKOFF — generado {GENERATED.astimezone(dt.timezone(dt.timedelta(hours=-5))):%Y-%m-%d %H:%M} (Ecuador)\n")
    header.append("> **AVISO:** mapa de contexto, NO señal ejecutable. Motor de señales en construcción (v30).")
    header.append(f"> Datos: `data/raw/*.parquet` (corte {cut_str}, actualizado vía MT5 en vivo). El sesgo HTF se infiere de `trend` D1/H4.")
    header.append("> Regla dura de ejecución (libro 18): SL y entry SIEMPRE en el exec TF; HTF/ITF solo sesgo y zona.\n")
    header.append(f"**Símbolos:** {', '.join(args.symbols)}\n")

    t0_all = time.time()
    sections = []
    last_dates_all = {}
    for sym in args.symbols:
        feats, dates, _ = compute(sym)
        last_dates_all.update(dates)
        sections.append(build_symbol_section(sym, feats, dates))
    body = "\n".join(sections)
    total = time.time() - t0_all

    footer = f"\n\n---\n*Generado por scripts/brief_lunes.py en {total:.1f}s. "
    footer += "Para señal ejecutable falta cablear entry retorno-a-zona, TP liquidez cercana, "
    footer += "exec_tf separado y RR 1:3 (docs/ict/CIERRE_FASE2.md).*\n"

    content = "\n".join(header) + "\n" + body + footer
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(content)
    out_txt = out_md.replace(".md", ".txt")
    with open(out_txt, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"[OK] Brief escrito:\n  {out_md}\n  {out_txt}")
    print(f"[OK] Tiempo total: {total:.1f}s para {len(args.symbols)} símbolos.")


if __name__ == "__main__":
    main()
