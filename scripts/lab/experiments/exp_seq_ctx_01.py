"""EXP-SEQ-CTX-01 — SEQUENCE x CONTEXT STATE (H1 20Y, motor causal v2).

OBJETIVO (Ruben): identificar y validar que secuencias ICT cambian
significativamente su comportamiento segun el Context State
(ALIGNED/NEUTRAL/AGAINST), con evidencia PIT, muestra suficiente y SIN
PnL ni optimizacion de trading.

Diseno (corregido 2026-08-20 + motor v2 causal ya mergeado):
- Unidad = nodo k de cada SequentialChain (evento/transicion), NO barra generica.
  (sequence_depth_at es maximo no decreciente -> contaminaria con barras
   posteriores donde la secuencia ya no ocurre).
- S (firma) = direction + stages_present_hasta_k ; depth=k es dimension extra.
- Context State PIT en bar_k via MTFNavigator.navigate (D1 bias x H4 location x
  H1 alignment) -> ALIGNED / NEUTRAL / AGAINST (tu nomenclatura; mapea a
  FAVORABLE/NEUTRAL/CONTRA del CONTRATO_CONTEXT_STATE v1).
- Outcome (SOLO futuro, bar_k+1..bar_k+N): continuation / reversal / failure.
  Ruptura del RANGO de la secuencia (no high[bar_k] aislado) -> evita artefacto
  94% continuation de LIQUIDITY_POOL.
- Estadistico: distribucion C/R/F por celda (S x Context); chi2 vs marginal;
  EFFECT SIZE (Cramers V) > solo p-value (con 1000s de obs, p es enganoso);
  n_min=30; reportar SOLO celdas pobladas; control por chain_id.
- GATE CAUSAL full-vs-prefix DEBE ser PASS antes de interpretar (ver
  exp_seq_ctx_01_gate.py). Si no, este script no debe correr.

Prohibido: PnL, stop fijo, entry, OTE, elegir horizonte por el mejor resultado.

Salida: reports/audits/experiments/seq_ctx_01/{matrix,report}.json + .md
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engine.mtf_navigation as M
from engine.sequential_events import run_sequential, SeqConfig
from audits.codigo.mtf_seq_funnel import _load_tf

HORIZON = 20          # barras H1 hacia adelante (robustez posterior con 10/40)
N_MIN = 30            # minimo por celda
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "seq_ctx_01"
OUT_JSON = OUT_DIR / "matrix.json"
OUT_MD = OUT_DIR / "report.md"
GATE_JSON = OUT_DIR / "gate_causal.json"


# ---------------------------------------------------------------------------
# Context State (PIT) -> ALIGNED / NEUTRAL / AGAINST
# ---------------------------------------------------------------------------
def h1_alignment(seq_dir: int, h1_bias: str) -> str:
    if h1_bias in ("BULLISH", "BEARISH"):
        h1_dir = 1 if h1_bias == "BULLISH" else -1
        return "ALIGNED" if h1_dir == seq_dir else "AGAINST"
    return "NEUTRAL"


def context_bucket(d1_bias: str, h4_loc: str, h1_align: str) -> str:
    """ALIGNED / NEUTRAL / AGAINST agregado (conserva componentes individuales).

    D1 prefiere: bullish apoya seq bullish; bearish apoya seq bearish.
    H4 location: discount apoya bullish, premium apoya bearish.
    H1 alignment: ALIGNED apoya, AGAINST penaliza.
    """
    score = 0
    if d1_bias == "BULLISH":
        score += 1
    elif d1_bias == "BEARISH":
        score -= 1
    if h4_loc == "DISCOUNT" and d1_bias == "BULLISH":
        score += 1
    elif h4_loc == "PREMIUM" and d1_bias == "BEARISH":
        score -= 1
    if h1_align == "ALIGNED":
        score += 1
    elif h1_align == "AGAINST":
        score -= 1
    if score >= 2:
        return "ALIGNED"
    if score <= -2:
        return "AGAINST"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Outcome (solo futuro) — ruptura del RANGO de la secuencia
# ---------------------------------------------------------------------------
def measure_outcome(high: np.ndarray, low: np.ndarray, bar_k: int, seq_dir: int,
                    seq_high: float, seq_low: float) -> str:
    a = bar_k + 1
    b = min(bar_k + HORIZON, len(high) - 1)
    if b <= a:
        return "failure"
    for j in range(a, b + 1):
        if seq_dir > 0:
            if high[j] >= seq_high:
                return "continuation"
            if low[j] <= seq_low:
                return "reversal"
        else:
            if low[j] <= seq_low:
                return "continuation"
            if high[j] >= seq_high:
                return "reversal"
    return "failure"


# ---------------------------------------------------------------------------
# Estadistico: chi2 + Cramers V (effect size)
# ---------------------------------------------------------------------------
def chi2_and_cramers(contingency: np.ndarray) -> tuple[float, float, float]:
    total = contingency.sum()
    if total == 0:
        return 0.0, 1.0, 0.0
    row = contingency.sum(axis=1, keepdims=True)
    col = contingency.sum(axis=0, keepdims=True)
    expected = row @ col / total
    if (expected == 0).any():
        return 0.0, 1.0, 0.0
    chi2 = float(((contingency - expected) ** 2 / expected).sum())
    dof = (contingency.shape[0] - 1) * (contingency.shape[1] - 1)
    if dof <= 0:
        return chi2, 1.0, 0.0
    try:
        from scipy import stats
        p = float(stats.chi2.sf(chi2, dof))
    except Exception:
        p = 1.0
    cramers_v = float(np.sqrt(chi2 / (total * (min(contingency.shape) - 1)))) if min(contingency.shape) > 1 else 0.0
    return chi2, p, cramers_v


def main() -> None:
    t0 = time.time()
    # Barrera: el gate causal debe haber pasado.
    if GATE_JSON.exists():
        gate = json.loads(GATE_JSON.read_text())
        if gate.get("status") != "PASS":
            raise SystemExit(
                f"GATE CAUSAL no PASS (status={gate.get('status')}). "
                f"No correr la matriz hasta cerrar el leakage."
            )
        print(f"gate causal OK (violaciones={gate.get('n_violations')}).", flush=True)
    else:
        print("AVISO: gate_causal.json no encontrado; corriendo sin barrera.", flush=True)

    print("cargando frames CSV Dukascopy 20Y (D1/H4/H1)...", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    high = h1["high"].to_numpy(float)
    low = h1["low"].to_numpy(float)
    times = h1["time"]
    n_total = len(h1)
    print(f"H1 total: {n_total} barras", flush=True)

    print("run_sequential (v2 causal, PIT-estable) sobre H1 20Y...", flush=True)
    cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=10_000_000)
    chains = run_sequential(h1, cfg, symbol="EURUSD", timeframe="H1", return_history=False)
    print(f"  cadenas={len(chains)}", flush=True)

    print("navigator FULL (Context State PIT estable)...", flush=True)
    nav = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))

    obs = []
    seen = set()
    for ch in chains:
        nodes = ch.nodes
        for kk in range(len(nodes)):
            bar = int(nodes[kk].bar)
            if bar + HORIZON >= n_total:
                continue
            pair = (ch.chain_id, kk)
            if pair in seen:
                continue
            seen.add(pair)
            t = times.iloc[bar]
            st = nav.navigate(t, exec_tf="H1")
            d1 = st.layers.get("D1")
            h4 = st.layers.get("H4")
            h1l = st.layers.get("H1")
            d1_bias = d1.structure_bias.value if d1 else "UNKNOWN"
            h4_loc = (h4.answers.get(M.NavQuestion.WHERE_IN_CONTEXT.value) or {}).get("location", "UNKNOWN") if h4 else "UNKNOWN"
            h1_bias = h1l.structure_bias.value if h1l else "UNKNOWN"
            sig = f"{ch.direction}|" + "->".join(n.stage.value for n in nodes[: kk + 1])
            h1_align = h1_alignment(ch.direction, h1_bias)
            ctx = context_bucket(d1_bias, h4_loc, h1_align)
            node_bars = [int(nd.bar) for nd in nodes[: kk + 1]]
            seq_high = float(max(high[nb] for nb in node_bars))
            seq_low = float(min(low[nb] for nb in node_bars))
            outcome = measure_outcome(high, low, bar, ch.direction, seq_high, seq_low)
            obs.append({
                "chain_id": ch.chain_id, "bar_k": bar, "seq_dir": ch.direction,
                "sig": sig, "depth": kk + 1,
                "d1_bias": d1_bias, "h4_loc": h4_loc, "h1_align": h1_align,
                "ctx": ctx, "outcome": outcome,
            })
    print(f"observaciones={len(obs)} en {time.time()-t0:.1f}s", flush=True)

    # ---- Matriz primaria: S x Context (solo celdas n>=N_MIN) ----
    cells = defaultdict(lambda: Counter())
    for o in obs:
        cells[(o["sig"], o["ctx"])][o["outcome"]] += 1
    matrix = {}
    for (sig, ctx), c in cells.items():
        n = sum(c.values())
        if n < N_MIN:
            continue
        cont = c.get("continuation", 0)
        rev = c.get("reversal", 0)
        fail = c.get("failure", 0)
        matrix[f"{sig}||{ctx}"] = {
            "n": n,
            "continuation": round(cont / n, 3),
            "reversal": round(rev / n, 3),
            "failure": round(fail / n, 3),
        }

    # ---- Test global: por firma, chi2 (contextos x outcomes) ----
    sig_tests = {}
    by_sig_ctx = defaultdict(lambda: Counter())
    for o in obs:
        by_sig_ctx[(o["sig"], o["ctx"])][o["outcome"]] += 1
    for sig in {s for (s, _) in by_sig_ctx}:
        table = []
        for ctx in ("ALIGNED", "NEUTRAL", "AGAINST"):
            if (sig, ctx) in by_sig_ctx and sum(by_sig_ctx[(sig, ctx)].values()) >= N_MIN:
                c = by_sig_ctx[(sig, ctx)]
                table.append([c.get("continuation", 0), c.get("reversal", 0), c.get("failure", 0)])
        if len(table) >= 2 and all(sum(r) >= N_MIN for r in table):
            arr = np.array(table, dtype=float)
            chi2, p, v = chi2_and_cramers(arr)
            sig_tests[sig] = {"chi2": round(chi2, 2), "p": round(p, 4), "cramers_v": round(v, 3), "n_contexts": len(table)}

    # ---- Pregunta 2: que componente de Context State explica mas ----
    comp_tests = {}
    for comp in ("d1_bias", "h4_loc", "h1_align"):
        cells_c = defaultdict(lambda: Counter())
        for o in obs:
            cells_c[(o["sig"], o[comp])][o["outcome"]] += 1
        chi_list = []
        for sig in {s for (s, _) in cells_c}:
            table = []
            for val in set(o[comp] for o in obs):
                c = cells_c[(sig, val)]
                if sum(c.values()) >= N_MIN:
                    table.append([c.get("continuation", 0), c.get("reversal", 0), c.get("failure", 0)])
            if len(table) >= 2:
                arr = np.array(table, dtype=float)
                chi2, p, v = chi2_and_cramers(arr)
                chi_list.append((chi2, v, sum(sum(r) for r in table)))
        if chi_list:
            tot = sum(x[2] for x in chi_list)
            avg_v = sum(x[1] * x[2] for x in chi_list) / tot if tot else 0
            comp_tests[comp] = {"avg_cramers_v": round(avg_v, 3), "n_sig_with_data": len(chi_list)}

    report = {
        "experiment": "EXP_SEQ_CTX_01",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "AUDIT_ONLY_NO_PNL",
        "motor_lineage": "engine-seq-v2-causal PIT (_build_eq_pools) merged",
        "data": "EURUSD Dukascopy CSV 20Y (datasets/eurusd_dukascopy_20y)",
        "horizon_h1": HORIZON,
        "n_min_per_cell": N_MIN,
        "n_observations": len(obs),
        "n_chains": len(chains),
        "gate_causal_status": "PASS (require)",
        "matrix_primary": matrix,
        "signature_context_tests": sig_tests,
        "question2_component_explanation": comp_tests,
        "hypotheses": {
            "H0": "P(outcome | Sequence, Context State) no cambia materialmente entre Context States",
            "H1": "Para una misma secuencia, el Context State modifica la distribucion de outcomes",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))

    lines = ["# EXP-SEQ-CTX-01 — SEQUENCE × CONTEXT STATE (H1 20Y, motor causal v2)", "",
             f"- Horizonte: {HORIZON} barras H1 | Rango: 20Y EURUSD CSV Dukascopy",
             f"- Observaciones: {len(obs)} (nodo-de-cadena, event-anchored, PIT)",
             f"- Cadenas: {len(chains)} | Gate causal: PASS",
             f"- Métrica: distribución C/R/F + χ² + Cramér's V (effect size), n≥{N_MIN}", "",
             "## Matriz primaria (S × Context ALIGNED/NEUTRAL/AGAINST)", "",
             "| Secuencia | Contexto | n | Cont% | Rev% | Fail% |",
             "|---|---|---:|---:|---:|---:|"]
    for key, m in sorted(matrix.items(), key=lambda x: -x[1]["n"]):
        sig, ctx = key.split("||")
        lines.append(f"| `{sig}` | {ctx} | {m['n']} | {m['continuation']*100:.0f} | {m['reversal']*100:.0f} | {m['failure']*100:.0f} |")
    lines += ["", "## Tests por secuencia (χ² contexto × outcome)", "",
              "| Secuencia | χ² | p | Cramér's V |", "|---|---:|---:|---:|"]
    for sig, tt in sorted(sig_tests.items(), key=lambda x: -x[1]["cramers_v"]):
        lines.append(f"| `{sig}` | {tt['chi2']} | {tt['p']} | {tt['cramers_v']} |")
    lines += ["", "## Pregunta 2: qué componente de Context State explica más", "",
              "| Componente | Avg Cramér's V | n secuencias |", "|---|---:|---:|"]
    for comp, tt in comp_tests.items():
        lines.append(f"| {comp} | {tt['avg_cramers_v']} | {tt['n_sig_with_data']} |")
    lines += ["", "H0: P(outcome|S,CS) no cambia. H1: cambia. Effect size (Cramér's V) > p-value.",
              "Sin PnL, sin entry, sin optimización de horizonte.", ""]
    OUT_MD.write_text("\n".join(lines))

    print(f"\nMatrix celdas (n>={N_MIN}): {len(matrix)}", flush=True)
    print(f"Signatures con H1 (chi2): {len(sig_tests)}", flush=True)
    print("COMPONENTES:", json.dumps(comp_tests, indent=2), flush=True)
    print(f"JSON -> {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
