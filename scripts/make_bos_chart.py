"""Genera grafico interactivo HTML (Plotly.js via CDN) de EURUSD M5 1 mes
con los BOS dibujados como lineas horizontales cartesianas desde el swing
padre (origin_bar) hasta el break (break_bar), al nivel del swing.

Calidad tipo TradingView:
  - tema oscuro pro (#131722), grilla tenue
  - candlestick con relleno + lineas finas
  - BOS unicos (is_unique) en azul brillante con etiqueta de precio
  - BOS no-unicos en gris tenue (contexto, no ruido)
  - zoom suave: tickformat H:M, gridcolor suave, autorange
  - hover detallado (id, parent, razon, idle)

NO requiere pip: Plotly.js por CDN.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")
from detectors.trend import detect_trend
from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.bos_filter import filter_bos_thesis

OUT = Path("docs/charts/bos_cartesiano.html")


def build(month_start: str, month_end: str, symbol: str = "EURUSD",
           max_idle_bars: int = 0, only_unique: bool = True,
           max_bars: int = 8000) -> str:
    df = pd.read_parquet(f"data/raw/{symbol}/{symbol}_M5.parquet")
    df["time"] = pd.to_datetime(df["time"])
    m = df[(df["time"] >= month_start) & (df["time"] <= month_end)].reset_index(drop=True)
    if len(m) > max_bars:
        m = m.iloc[-max_bars:].reset_index(drop=True)

    htf = {}
    for tf in ("D1", "H4", "H1"):
        h = pd.read_parquet(f"data/raw/{symbol}/{symbol}_{tf}.parquet")
        h["time"] = pd.to_datetime(h["time"])
        htf[tf] = detect_trend(h)

    sw = SwingTool(lookback=5)
    sw_evs = sw.run(m, symbol=symbol)
    swing_ids = {e.origin_bar: e.id for e in sw_evs}
    bos = BOSTool(lookback=5)
    bos_evs = bos.run(m, symbol=symbol, context={"swing_ids": swing_ids})
    bos_evs = apply_validation(m, bos_evs)
    bos_evs = filter_bos_thesis(m, bos_evs, htf_frames=htf, confirm_bars=2,
                                max_idle_bars=max_idle_bars, require_htf_alignment=True)

    times = m["time"].astype(str).tolist()
    o = m["open"].round(5).tolist()
    h = m["high"].round(5).tolist()
    l = m["low"].round(5).tolist()
    c = m["close"].round(5).tolist()

    swing_by_id = {e.id: e for e in sw_evs}
    bos_lines = []
    for ev in bos_evs:
        if only_unique and not ev.extra.get("is_unique"):
            continue
        parent = swing_by_id.get(ev.parent_id)
        x0 = parent.origin_bar if parent else ev.break_bar
        price = ev.price
        is_uniq = ev.extra.get("is_unique")
        color = "#2962ff" if is_uniq else "#3a3a3a"
        width = 2.2 if is_uniq else 0.8
        opacity = 0.95 if is_uniq else 0.35
        reason = ev.extra.get("thesis_reason", "")
        label = f"{ev.id} p={ev.parent_id} {ev.status} | {reason}"
        bos_lines.append({
            "x": [x0, ev.break_bar],
            "y": [price, price],
            "color": color, "width": width, "opacity": opacity,
            "label": label,
        })

    from tools.bos_filter import summarize_bos_filter
    s = summarize_bos_filter(bos_evs)
    data = {
        "times": times, "open": o, "high": h, "low": l, "close": c,
        "bos_lines": bos_lines, "symbol": symbol,
        "month": f"{month_start} -> {month_end}",
        "summary": s, "only_unique": only_unique,
    }
    return _render(data)


def _render(d: dict) -> str:
    payload = json.dumps(d, ensure_ascii=False)
    s = d["summary"]
    sub = f"setups unicos={s['unique_setups']} (up {s['unique_up']}/dn {s['unique_down']})" if d["only_unique"] \
          else f"active={s['geometric_active']} valid={s['thesis_valid']} unicos={s['unique_setups']}"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BOS Cartesiano — {d['symbol']} M5</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
body {{ margin:0; background:#131722; color:#d1d4dc; font-family:-apple-system,Segoe UI,Roboto,sans-serif }}
#title {{ padding:10px 16px; font-size:13px; border-bottom:1px solid #2a2e39; background:#1e222d }}
#title b {{ color:#2962ff }}
#chart {{ width:100vw; height:94vh }}
.hint {{ color:#787b86; font-size:12px }}
.c-uni {{ color:#2962ff; font-weight:600 }}
.c-gry {{ color:#3a3a3a }}
</style>
</head>
<body>
<div id="title">BOS Cartesiano — <b>{d['symbol']}</b> M5 &nbsp; {d['month']} &nbsp;|&nbsp; total={s['total_bos']} · active={s['geometric_active']} · <span class="c-uni">{sub}</span><br>
<span class="hint">rueda=zoom · arrastrar=pan · doble-click=reset · azul=setup unico tesis-valido · gris=contexto</span></div>
<div id="chart"></div>
<script>
const D = {payload};
const traceCandles = {{
  type:'candlestick', x:D.times, open:D.open, high:D.high, low:D.low, close:D.close,
  name:'M5',
  increasing:{{line:{{color:'#26a69a'}}, fillcolor:'#26a69a'}},
  decreasing:{{line:{{color:'#ef5350'}}, fillcolor:'#ef5350'}},
  line:{{width:1}}, xaxis:'x', yaxis:'y', hoverlabel:{{font:{{size:11}}}}
}};
const traces = [traceCandles];
for (const ln of D.bos_lines) {{
  traces.push({{
    x: ln.x.map(i => D.times[i]),
    y: ln.y,
    mode:'lines', type:'scatter',
    line:{{color: ln.color, width: ln.width}},
    opacity: ln.opacity, hoverinfo:'text', text: ln.label, showlegend:false,
    hoverlabel:{{font:{{size:11, color:'#d1d4dc'}}, bgcolor:'#1e222d'}}
  }});
}}
const layout = {{
  paper_bgcolor:'#131722', plot_bgcolor:'#131722',
  xaxis:{{ type:'date', rangeslider:{{visible:false}},
    gridcolor:'#2a2e39', zeroline:false, showgrid:true,
    tickfont:{{color:'#787b86', size:11}},
    tickformat:'%d %H:%M' }},
  yaxis:{{ title:'precio', gridcolor:'#2a2e39', zeroline:false,
    tickfont:{{color:'#787b86', size:11}}, side:'right',
    tickformat:'.5f' }},
  dragmode:'pan', showlegend:false,
  margin:{{t:0,l:55,r:55,b:30}},
  hovermode:'x unified'
}};
const config = {{ scrollZoom:true, displaylogo:false, responsive:true,
  modeBarButtonsToAdd:['zoom2d','pan2d','resetScale2d','zoomIn2d','zoomOut2d'],
  modeBarButtonsToRemove:['lasso2d','select2d'], displayModeBar:true }};
Plotly.newPlot('chart', traces, layout, config);
</script>
</body></html>"""


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-07-14")
    ap.add_argument("--end", default="2026-08-14")
    ap.add_argument("--max-idle", type=int, default=0, help="0=sin dormido; 288=1 dia M5")
    ap.add_argument("--all", action="store_true", help="mostrar todos los BOS, no solo unicos")
    a = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = build(a.start, a.end, max_idle_bars=a.max_idle, only_unique=not a.all)
    OUT.write_text(html, encoding="utf-8")
    print(f"HTML: {OUT} ({len(html)} bytes) max_idle={a.max_idle} only_unique={not a.all}")
