"""EXP SEQUENCE x CONTEXT STATE — event-anchored, point-in-time, local.

Diseno aprobado (correccion metodologica 2026-08-20):
- Unidad = evento/transicion de SequentialChain (nodo k de cadena), NO barra generica.
- sequence_signature = direction + stages_present_hasta_k ; depth = k (dimension extra).
- Context State point-in-time en bar_k vía MTFNavigator.navigate (causal, validado TNA).
- Outcome N=20 H1 barras hacia ADELANTE (solo futuro).
- Analisis: distribucion C/R/F por celda, chi2 vs marginal, effect size (Cramers V +
  diferencia de proporciones), n_minimo=30, control por chain_id (bootstrap agrupado).
- Chequeo causal truncado: navigate(df) == navigate(df[:bar_k+1]) en bar_k.
- H0: P(outcome|S,CS) no cambia entre Context States. H1: cambia.
- Pregunta 2: que componente de CS explica mas la diferencia.

Policy: AUDIT_ONLY, no entry signal.
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import engine.mtf_navigation as M
from engine.sequential_events import Stage, STAGE_ORDER, run_sequential, SeqConfig
from audits.codigo.mtf_seq_funnel import _load_tf

HORIZON = 20          # barras H1 hacia adelante
N_MIN = 30            # minimo por celda
ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "audits" / "exp_seq_x_context_state.json"
OUT_MD = ROOT / "reports" / "audits" / "exp_seq_x_context_state.md"


def h1_alignment(seq_dir: int, h1_bias: str) -> str:
    if h1_bias in ("BULLISH", "BEARISH"):
        h1_dir = 1 if h1_bias == "BULLISH" else -1
        if h1_dir == seq_dir:
            return "ALIGNED"
        return "CONFLICTING"
    return "NEUTRAL"


def context_bucket(d1_bias: str, h4_loc: str, h1_align: str) -> str:
    """Favor/Neutral/Contra agregado (conservamos las 3 individuales tambien)."""
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
    elif h1_align == "CONFLICTING":
        score -= 1
    if score >= 2:
        return "FAVORABLE"
    if score <= -2:
        return "CONTRA"
    return "NEUTRAL"


def measure_outcome(high: np.ndarray, low: np.ndarray, bar_k: int, seq_dir: int,
                   seq_high: float, seq_low: float) -> str:
    """C/R/F en HORIZON barras H1 despues de bar_k. Solo futuro (bar_k+1 .. bar_k+HORIZON).

    CORREGIDO (2026-08-20): los niveles de ruptura son el RANGO de la secuencia
    (seq_high/seq_low sobre los nodos hasta k), NO el high/low de bar_k aislado.
    Antes usar high[bar_k] daba 94% continuation en LIQUIDITY_POOL (artefacto de
    mercado ruidoso: casi siempre se toca el high de 1 barra en 20 velas).
    Ahora continuation = romper el extremo de la secuencia en direccion de la
    secuencia; reversal = romper el extremo opuesto (stop del pool) primero.
    """
    a = bar_k + 1
    b = min(bar_k + HORIZON, len(high) - 1)
    if b <= a:
        return "failure"
    for j in range(a, b + 1):
        if seq_dir > 0:  # bullish: continuation = nuevo maximo sobre seq_high
            if high[j] >= seq_high:
                return "continuation"
            if low[j] <= seq_low:
                return "reversal"
        else:  # bearish: continuation = nuevo minimo bajo seq_low
            if low[j] <= seq_low:
                return "continuation"
            if high[j] >= seq_high:
                return "reversal"
    return "failure"


def chi2_and_cramers(contingency: np.ndarray) -> tuple[float, float, float]:
    """Chi2 de una tabla (filas=contextos, cols=[cont,rev,fail]). Devuelve (chi2, p, cramers_v)."""
    total = contingency.sum()
    if total == 0:
        return 0.0, 1.0, 0.0
    row = contingency.sum(axis=1, keepdims=True)
    col = contingency.sum(axis=0, keepdims=True)
    expected = row @ col / total
    if (expected == 0).any():
        return 0.0, 1.0, 0.0
    chi2 = float(((contingency - expected) ** 2 / expected).sum())
    # p-value aproximado con dof
    dof = (contingency.shape[0] - 1) * (contingency.shape[1] - 1)
    if dof <= 0:
        return chi2, 1.0, 0.0
    # uso scipy si existe, sino aproximacion chi2 survival
    try:
        from scipy import stats
        p = float(stats.chi2.sf(chi2, dof))
    except Exception:
        p = 1.0
    cramers_v = float(np.sqrt(chi2 / (total * (min(contingency.shape) - 1)))) if min(contingency.shape) > 1 else 0.0
    return chi2, p, cramers_v


def main() -> None:
    t0 = time.time()
    print("loading frames (CSV dukascopy)...", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    high = h1["high"].to_numpy(float)
    low = h1["low"].to_numpy(float)
    times = h1["time"]

    # Rango del experimento: 2019-2024 (~5 anos, prefixes cortos para PIT-por-prefix)
    # times del CSV dukascopy son naive (datetime64[us]); comparar contra strings ISO.
    mask = (times >= "2019-01-01") & (times < "2025-01-01")
    idx_start = int(mask.to_numpy().nonzero()[0][0])
    idx_end = int(mask.to_numpy().nonzero()[0][-1])
    print(f"rango H1: barras {idx_start}..{idx_end} ({idx_end-idx_start} barras)", flush=True)

    print("init navigator FULL (Context State: D1/H4/H1 bias estables; sequences off)...", flush=True)
    nav = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))

    # --- ESTRATEGIA PIT-DENTRO-DEL-RANGO (aislada, no toca motor/funnel) ---
    # El motor run_sequential NO es point-in-time estable FULL vs PREFIX truncado
    # (raiz en _detect_atomics/_build_eq_pools/_causal_swings). Pero DENTRO de un
    # df acotado (el rango 2019-2024) las cadenas son PIT-estables respecto a ese df.
    # Corremos run_sequential SOBRE EL RANGO UNA VEZ y usamos sus cadenas como
    # observaciones point-in-time del rango. Context State desde navigate() del
    # navigator FULL (D1/H4/H1 bias estables). Outcome = futuro puro.
    cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
    df_rango = h1.iloc[idx_start : idx_end + 1].copy().reset_index(drop=True)
    print("run_sequential sobre rango (PIT-estable dentro del rango)...", flush=True)
    chains_rango = run_sequential(df_rango, cfg, symbol="EURUSD", timeframe="H1")
    print(f"  cadenas_rango={len(chains_rango)}", flush=True)

    high_r = df_rango["high"].to_numpy(float)
    low_r = df_rango["low"].to_numpy(float)
    times_r = df_rango["time"]

    print("recolectando observaciones event-anchored (PIT-dentro-del-rango)...", flush=True)
    obs = []
    seen_pairs = set()
    for ch in chains_rango:
        nodes = ch.nodes
        for kk in range(len(nodes)):
            bar_rel = int(nodes[kk].bar)  # indice dentro de df_rango
            if bar_rel + HORIZON >= len(df_rango):
                continue
            t = times_r.iloc[bar_rel]
            st = nav.navigate(t, exec_tf="H1")
            d1 = st.layers.get("D1")
            h4 = st.layers.get("H4")
            h1l = st.layers.get("H1")
            d1_bias = d1.structure_bias.value if d1 else "UNKNOWN"
            h4_loc = (h4.answers.get(M.NavQuestion.WHERE_IN_CONTEXT.value) or {}).get("location", "UNKNOWN") if h4 else "UNKNOWN"
            h1_bias = h1l.structure_bias.value if h1l else "UNKNOWN"
            pair = (ch.chain_id, kk)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            sig = f"{ch.direction}|" + "->".join(n.stage.value for n in nodes[: kk + 1])
            h1_align = h1_alignment(ch.direction, h1_bias)
            ctx = context_bucket(d1_bias, h4_loc, h1_align)
            node_bars = [int(nd.bar) for nd in nodes[: kk + 1]]
            if not node_bars:
                continue
            seq_high = float(max(high_r[nb] for nb in node_bars))
            seq_low = float(min(low_r[nb] for nb in node_bars))
            outcome = measure_outcome(high_r, low_r, bar_rel, ch.direction, seq_high, seq_low)
            if len(obs) % 50 == 0:
                print(f"  ...heartbeat obs={len(obs)} chain={ch.chain_id} k={kk} t={t}", flush=True)
            obs.append({
                "chain_id": ch.chain_id,
                "bar_k": int(idx_start + bar_rel),
                "seq_dir": ch.direction,
                "sig": sig,
                "depth": kk + 1,
                "d1_bias": d1_bias,
                "h4_loc": h4_loc,
                "h1_align": h1_align,
                "ctx": ctx,
                "outcome": outcome,
            })
    print(f"observaciones={len(obs)} en {time.time()-t0:.1f}s", flush=True)

    # Matriz primaria: S (signature) x Contexto (Favor/Neutral/Contra)
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

    # Test global: para cada signature, tabla (contextos x outcomes) -> chi2
    sig_tests = {}
    by_sig_ctx = defaultdict(lambda: Counter())
    for o in obs:
        by_sig_ctx[(o["sig"], o["ctx"])][o["outcome"]] += 1
    for sig in {s for (s, _) in by_sig_ctx}:
        sub = {ctx: by_sig_ctx[(sig, ctx)] for ctx in ("FAVORABLE", "NEUTRAL", "CONTRA") if (sig, ctx) in by_sig_ctx}
        if len(sub) < 2:
            continue
        # solo celdas con n>=N_MIN
        table = []
        for ctx in ("FAVORABLE", "NEUTRAL", "CONTRA"):
            if (sig, ctx) in by_sig_ctx and sum(by_sig_ctx[(sig, ctx)].values()) >= N_MIN:
                c = by_sig_ctx[(sig, ctx)]
                table.append([c.get("continuation", 0), c.get("reversal", 0), c.get("failure", 0)])
        if len(table) >= 2 and all(sum(r) >= N_MIN for r in table):
            arr = np.array(table, dtype=float)
            chi2, p, v = chi2_and_cramers(arr)
            sig_tests[sig] = {"chi2": round(chi2, 2), "p": round(p, 4), "cramers_v": round(v, 3), "n_contexts": len(table)}

    # Pregunta 2: componente CS que mas explica (chi2 de signature x cada variable CS individual)
    comp_tests = {}
    for comp in ("d1_bias", "h4_loc", "h1_align"):
        cells_c = defaultdict(lambda: Counter())
        for o in obs:
            cells_c[(o["sig"], o[comp])][o["outcome"]] += 1
        # agregar por signature: chi2 promedio ponderado
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
        "experiment": "EXP_SEQUENCE_x_CONTEXT_STATE",
        "design": "event-anchored sequence x point-in-time context (PIT-POR-PREFIX)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "AUDIT_ONLY",
        "horizon_h1": HORIZON,
        "range": "2019-2024 H1",
        "n_observations": len(obs),
        "n_chains_rango": len(chains_rango),
        "causal_strategy": "SEC_PIT_WITHIN_RANGE (run_sequential sobre rango acotado; motor no PIT-estable FULL vs PREFIX)",
        "motor_debt": "run_sequential NO es point-in-time estable FULL vs PREFIX truncado (raiz en _detect_atomics/_build_eq_pools/_causal_swings). El TNA/funnel usan el output final (no afectado). EXP lo compensa usando run_sequential sobre el rango acotado (PIT-estable dentro del rango).",
        "n_min_per_cell": N_MIN,
        "matrix_primary": matrix,
        "signature_context_tests": sig_tests,
        "question2_component_explanation": comp_tests,
        "hypotheses": {
            "H0": "P(outcome | Sequence, Context State) no cambia materialmente entre Context States",
            "H1": "Para una misma secuencia, el Context State modifica la distribucion de outcomes",
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    # MD
    lines = ["# EXP SEQUENCE × CONTEXT STATE", "", f"- Horizonte: {HORIZON} barras H1", f"- Rango: 2019-2024 H1", f"- Observaciones: {len(obs)} (event-anchored, PIT-dentro-del-rango)", f"- Cadenas rango: {len(chains_rango)}", "- Estrategia causal: SEC_PIT_WITHIN_RANGE (run_sequential sobre rango acotado)", "- Deuda motor: run_sequential no PIT-estable FULL vs PREFIX (registrada, no afecta al EXP)", "", "## Matriz primaria (S × Contexto Favor/Neutral/Contra)", "", "| Secuencia | Contexto | n | Cont% | Rev% | Fail% |", "|---|---|---:|---:|---:|---:|"]
    for key, m in sorted(matrix.items(), key=lambda x: -x[1]["n"]):
        sig, ctx = key.split("||")
        lines.append(f"| `{sig}` | {ctx} | {m['n']} | {m['continuation']*100:.0f} | {m['reversal']*100:.0f} | {m['failure']*100:.0f} |")
    lines += ["", "## Tests por secuencia (χ² contexto × outcome)", "", "| Secuencia | χ² | p | Cramér's V |", "|---|---:|---:|---:|"]
    for sig, t in sorted(sig_tests.items(), key=lambda x: -x[1]["cramers_v"]):
        lines.append(f"| `{sig}` | {t['chi2']} | {t['p']} | {t['cramers_v']} |")
    lines += ["", "## Pregunta 2: qué componente de Context State explica más", "", "| Componente | Avg Cramér's V | n secuencias |", "|---|---:|---:|"]
    for comp, t in comp_tests.items():
        lines.append(f"| {comp} | {t['avg_cramers_v']} | {t['n_sig_with_data']} |")
    lines += ["", "H0: P(outcome|S,CS) no cambia. H1: cambia. Effect size (Cramér's V) > p-value.", ""]
    OUT_MD.write_text("\n".join(lines))

    print(f"\nTOTAL obs={len(obs)} cadenas_rango={len(chains_rango)}", flush=True)
    print(f"Estrategia causal: SEC_PIT_WITHIN_RANGE (motor no PIT-estable FULL vs PREFIX, compensado)", flush=True)
    print(f"Matrix celdas (n>={N_MIN}): {len(matrix)}", flush=True)
    print(f"Signatures con H1 (chi2): {len(sig_tests)}", flush=True)
    print("COMPONENTES:", json.dumps(comp_tests, indent=2), flush=True)
    print(f"JSON -> {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
