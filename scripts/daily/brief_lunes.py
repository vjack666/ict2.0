"""
BRIEF DE LECTURA ICT/WYCKOFF — preparado para revisar ANTES de la sesión NY.

ESTADO HONESTO (leer antes de usar):
  - Este script NO emite señales ejecutables. Es un MAPA DE CONTEXTO: sesgo HTF,
    zona EQ50/premium/discount, liquidez BSL/SSL, PD arrays activos (FVG/OB con
    tier), sweeps recientes, killzones a vigilar y estado LTF de observación.
  - El motor diario ahora expone el estado LTF/EXEC y la espera de retest, pero
    sigue siendo `OBSERVE_ONLY_NO_ORDER`; entry, SL y TP están fuera del alcance
    de este motor de lectura.
  - Usa data/raw/*.parquet, cuyo origen y timestamp se imprimen en el brief.
  - El Context State normativo proviene de `engine.mtf_navigation.MTFNavigator`;
    las columnas `trend` de DataFrame quedan como diagnóstico, no como autoridad.

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
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = str(Path(__file__).resolve().parents[2])  # scripts/daily -> raíz del repositorio
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


def current_week_summary(frame):
    """OHLC de la semana calendario en curso, closed-only hasta el feed."""
    if frame is None or frame.empty or "time" not in frame.columns:
        return None
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    valid = frame.loc[times.notna()].copy()
    if valid.empty:
        return None
    times = pd.to_datetime(valid["time"], utc=True, errors="coerce")
    asof = times.max()
    week_start = asof.normalize() - pd.Timedelta(days=int(asof.weekday()))
    sub = valid.loc[(times >= week_start) & (times <= asof)]
    if sub.empty:
        return None
    return {
        "start": week_start.isoformat(),
        "asof": asof.isoformat(),
        "bars": int(len(sub)),
        "open": as_float(sub.iloc[0].get("open")),
        "high": as_float(sub["high"].max()),
        "low": as_float(sub["low"].min()),
        "close": as_float(sub.iloc[-1].get("close")),
    }


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
    bias, src, per_tf = htf_bias(f_d1, f_h4, f_h1)  # diagnóstico legacy, no autoridad

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
    lines.append(f"- **Datos hasta:** D1 {ld['D1']} · H4 {ld['H4']} · H1 {ld['H1']} · M15 {ld['M15']}")
    lines.append("")

    # Un único Context State closed-only para la cadena D1→H4→H1→M15.
    # precompute_sequences=False evita que esta lectura cree una segunda
    # ejecución pesada; Sequence se entrega por su interfaz canónica cuando
    # el caller disponga de ese snapshot.
    from engine.daily_motor import build_daily_motor_snapshot
    from engine.ltf_canonical_feed import build_ltf_canonical_feed
    from engine.mtf_navigation import MTFNavigator, NavigatorConfig
    from engine.Wyckoff import build_wyckoff_snapshot
    decision_time = last_dates.get("M15")
    nav_frames = {tf: frame for tf, frame in feats.items() if frame is not None}
    market_state = None
    if decision_time is not None and nav_frames:
        market_state = MTFNavigator(
            nav_frames,
            NavigatorConfig(precompute_sequences=False, sequence_tf="H1"),
        ).navigate(decision_time=decision_time, exec_tf="M15")
    canonical_feed = build_ltf_canonical_feed(
        feats,
        decision_time=decision_time,
        exec_tf="M15",
        sequence_tf="H1",
        symbol=sym,
        include_sequence=True,
    ) if decision_time is not None else {"zones": {"M15": []}, "sequence": {"available": False, "refs": [], "depth": 0}}
    wyckoff_read = build_wyckoff_snapshot(
        nav_frames,
        decision_time=decision_time,
        context_state=market_state,
        authority_tf="D1",
        layers=("D1", "H4", "H1", "M15"),
    ) if decision_time is not None else None
    ltf_read = build_daily_motor_snapshot(
        feats,
        decision_time=decision_time,
        context_state=market_state,
        canonical_zones=canonical_feed.get("zones"),
        sequence_snapshot=canonical_feed.get("sequence"),
        wyckoff_snapshot=wyckoff_read,
    )
    ltf = ltf_read.get("ltf", {})
    ctx = ltf_read.get("context", {})
    direction_label = ltf_read.get("direction_label", "RANGING")
    context_location = ctx.get("location", "UNKNOWN")
    lines.append(
        f"- **Context State:** `{direction_label}` · location=`{context_location}` · "
        f"fuente=`{ctx.get('source', 'n/a')}`"
    )
    lines.append(f"- **Sesgo diagnóstico legacy:** `{bias}` (fuente {src}) · D1={per_tf['D1']} H4={per_tf['H4']} H1={per_tf['H1']}")
    wyckoff = ltf_read.get("wyckoff", {})
    lines.append(
        f"- **Wyckoff:** fase=`{wyckoff.get('phase', 'UNKNOWN')}` · "
        f"estado=`{wyckoff.get('phase_state', 'NEUTRAL')}` · "
        f"authority_tf=`{wyckoff.get('authority_tf', '—')}` · "
        f"alignment=`{wyckoff.get('ict_alignment', 'UNRESOLVED')}`"
    )
    lines.append(f"- Wyckoff conflicto: `{wyckoff.get('conflict', False)}` · `{wyckoff.get('explanation', 'n/a')}`")
    week = current_week_summary(f_m15)
    if week:
        lines.append("### Semana en curso (OHLC del mismo feed MT5)")
        lines.append(
            f"- Ventana: `{week['start']}` → `{week['asof']}` · barras M15=`{week['bars']}`"
        )
        lines.append(
            f"- Open `{week['open']:.5f}` · High `{week['high']:.5f}` · "
            f"Low `{week['low']:.5f}` · Close `{week['close']:.5f}`"
        )
        lines.append("- Lectura: rango y posición semanal; no es PnL ni una instrucción de entrada.")
    lines.append("### LTF / exec M15 (motor diario)")
    lines.append(f"- Estado: `{ltf_read.get('status', 'NO_LTF_DATA')}`")
    lines.append(f"- Dirección heredada del contexto: `{ltf_read.get('direction_label', 'RANGING')}`")
    lines.append(f"- Contexto permitido: `{ctx.get('allowed', False)}` · razón: `{ctx.get('reason', 'n/a')}`")
    lines.append(
        f"- Sequence canónica: disponible=`{ltf_read.get('sequence', {}).get('available', False)}` · "
        f"refs=`{len(ltf_read.get('sequence', {}).get('refs', []))}` · "
        f"depth=`{ltf_read.get('sequence', {}).get('depth', 0)}`"
    )
    lines.append(
        f"- Estructura a favor: `{ltf.get('structure_confirmed', False)}` · "
        f"zonas canónicas: `{len(ltf.get('zone_refs', []))}` · "
        f"retest: `{ltf.get('retest_state', 'NO_ZONE')}`"
    )
    lines.append(
        f"- Marcadores legacy de DataFrame (no promocionan estado): "
        f"zona=`{ltf.get('legacy_zone_marker', False)}` · "
        f"retest=`{ltf.get('legacy_retest_marker', False)}`"
    )
    lines.append("- Política: `OBSERVE_ONLY_NO_ORDER` — no es entry ni autorización de operación.")
    lines.append("")

    # Dealing range (H4)
    lines.append("### Zona (dealing range H4)")
    pdr = context_location if context_location in {"DISCOUNT", "PREMIUM", "MID"} else last_val(f_h4, "premium_discount_zone")
    zh = last_val(f_h4, "zone_high"); zl = last_val(f_h4, "zone_low"); zm = last_val(f_h4, "zone_mid")
    lines.append(f"- Zona premium/discount: `{pdr}`")
    if ok(zh) and ok(zl):
        lines.append(f"- Rango H4: high `{zh:.5f}` · low `{zl:.5f}` · mid `{zm:.5f}`")
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
    if direction_label == "BULLISH":
        if pdr == "DISCOUNT":
            lines.append("- **PO3 a-favor LONG**: precio en DISCOUNT. Buscar en M15: sweep SSL + CHoCH/BOS alcista + retorno a FVG/OB. Invalidación: bajo último swing low / mecha del sweep.")
        elif pdr == "PREMIUM":
            lines.append("- Sesgo alcista pero precio en PREMIUM: NO comprar aquí. Esperar retracción a DISCOUNT antes de buscar long.")
        else:
            lines.append("- Sesgo alcista, precio neutro: vigilar reacción en discount para buscar long.")
    elif direction_label == "BEARISH":
        if pdr == "PREMIUM":
            lines.append("- **PO3 a-favor SHORT**: precio en PREMIUM. Buscar en M15: sweep BSL + CHoCH/BOS bajista + retorno a FVG/OB. Invalidación: sobre último swing high / mecha del sweep.")
        elif pdr == "DISCOUNT":
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

    # Fail closed if the production/laboratory boundary is invalid. The daily
    # brief must never silently consume a research candidate.
    from runtime.engine_registry import assert_daily_engine_safe
    active_engine = assert_daily_engine_safe()

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
    header.append(f"> **Motor activo:** `{active_engine['id']}` · perfil `{active_engine['profile_id']}` · estado `{active_engine['deployment_state']}`")
    header.append("> **AVISO:** mapa de contexto, NO señal ejecutable. Motor de señales en construcción (v30).")
    header.append(f"> Datos: `data/raw/*.parquet` (corte {cut_str}, actualizado vía MT5 en vivo). El Context State normativo proviene de `MTFNavigator`; `trend` es diagnóstico legacy.")
    header.append("> Regla informativa (libro 18): HTF/ITF aportan sesgo y zona; este brief solo lee mercado y no calcula ejecución.\n")
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
    footer += "La capa de ejecución (entry/SL/TP) está fuera del alcance de esta lectura; "
    footer += "ver docs/tesis/PLAN_LTF_ENTRY_LAYER.md para el límite de responsabilidad.*\n"

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
