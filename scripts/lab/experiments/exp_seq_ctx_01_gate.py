"""EXP-SEQ-CTX-01 — GATE CAUSAL (barrera obligatoria, antes de la matriz).

Objetivo: verificar que el motor de navegacion MTF es point-in-time estable
bajo el fix v2 (engine-seq-v2-causal, _build_eq_pools PIT). El experimento
del 2026-08-20 fue INVALIDADO porque navigate(full,t) != navigate(prefix,t)
(1/10 -> fallo, luego 15/15). Aqui reproducimos el gate DEFINITIVO sobre
una muestra amplia y determinista de barras H1 20Y.

Criterio (REGLA AUTORIDAD 2026-08-20):
  - 0 violaciones -> motor ACEPTADO como causal para EXP-SEQ-CTX-01.
  - >=1 violacion -> marcar INVALIDATED, no correr la matriz.

No mide outcome ni PnL. Solo integridad causal del Context State.

Salida: reports/audits/experiments/seq_ctx_01/gate_causal.json
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
from audits.codigo.mtf_seq_funnel import _load_tf
OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "seq_ctx_01"
OUT_JSON = OUT_DIR / "gate_causal.json"

N_SAMPLES = 120          # barras de la muestra causal (determinista, amplia)
SEED_BAR = 2000          # empezar despues de warmup de swings/BOS
STRIDE = 300             # separacion determinista entre barras muestreadas


def _state_fields(st):
    """Extrae los campos PIT-relevantes del MarketState para comparar full vs prefix."""
    layers = {}
    for tf, snap in st.layers.items():
        layers[tf] = {
            "asof_bar": snap.asof_bar,
            "structure_bias": snap.structure_bias.value,
            "regime": snap.regime.value if snap.regime is not None else None,
            "last_bos_direction": snap.last_bos_direction,
            "last_bos_bar": snap.last_bos_bar,
            "displacement_recent": snap.displacement_recent,
            "range_high": snap.range_high,
            "range_low": snap.range_low,
            "n_zones": len(snap.zones),
        }
    c = st.constraints
    cons = None
    if c is not None:
        cons = {
            "direction_hint": c.direction_hint.value if c.direction_hint is not None else None,
            "allow_long": c.allow_long,
            "allow_short": c.allow_short,
            "sequence_required": c.sequence_required,
            "regime_stack": dict(c.regime_stack),
        }
    return {
        "decision_time": str(st.decision_time),
        "status": st.status,
        "layers": layers,
        "constraints": cons,
    }


def _diff_fields(a, b):
    """Devuelve lista de rutas que difieren entre dos dicts de estado."""
    diffs = []

    def walk(x, y, path):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in set(x) | set(y):
                walk(x.get(k), y.get(k), f"{path}.{k}")
        elif isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            if len(x) != len(y):
                diffs.append(f"{path}: len {len(x)} != {len(y)}")
            else:
                for i, (xi, yi) in enumerate(zip(x, y)):
                    walk(xi, yi, f"{path}[{i}]")
        else:
            if x != y:
                diffs.append(f"{path}: {x!r} != {y!r}")
    walk(a, b, "root")
    return diffs


def main() -> None:
    t0 = time.time()
    print("GATE CAUSAL EXP-SEQ-CTX-01 — full-vs-prefix equivalence", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    times = h1["time"]
    n_total = len(h1)
    print(f"H1 barras totales: {n_total}", flush=True)

    # Muestra determinista de barras (warmup + stride)
    sample_bars = list(range(SEED_BAR, n_total - 50, STRIDE))[:N_SAMPLES]
    if len(sample_bars) < N_SAMPLES:
        # si el rango es corto, llenar con paso menor
        sample_bars = list(range(SEED_BAR, n_total - 50, max(1, (n_total - SEED_BAR - 50) // N_SAMPLES)))[:N_SAMPLES]
    print(f"muestra: {len(sample_bars)} barras (primera={sample_bars[0]}, ultima={sample_bars[-1]})", flush=True)

    nav_full = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))

    violations = []
    checked = 0
    for i, bar in enumerate(sample_bars):
        t = times.iloc[bar]
        st_full = nav_full.navigate(t, exec_tf="H1")
        f_full = _state_fields(st_full)

        trunc = {tf: frames[tf].iloc[: bar + 1].copy().reset_index(drop=True) for tf in frames}
        nav_pref = M.MTFNavigator(trunc, M.NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))
        st_pref = nav_pref.navigate(t, exec_tf="H1")
        f_pref = _state_fields(st_pref)

        d = _diff_fields(f_full, f_pref)
        checked += 1
        if d:
            violations.append({"bar": int(bar), "time": str(t), "diffs": d[:20]})
        if i % 20 == 0:
            print(f"  ...bar {i}/{len(sample_bars)} violaciones={len(violations)}", flush=True)

    passed = len(violations) == 0
    report = {
        "experiment": "EXP-SEQ-CTX-01_GATE_CAUSAL",
        "description": "navigate(full,t) == navigate(prefix_through_t,t) on H1 20Y sample",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "motor_lineage": "engine-seq-v2-causal (PIT _build_eq_pools) merged into current checkout",
        "n_samples": len(sample_bars),
        "n_checked": checked,
        "n_violations": len(violations),
        "status": "PASS" if passed else "INVALIDATED",
        "reason": None if passed else "CAUSALITY_CHECK_FAIL",
        "usable_for_inference": passed,
        "violations_sample": violations[:10],
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nGATE: {report['status']}  violaciones={len(violations)}/{checked}", flush=True)
    print(f"JSON -> {OUT_JSON}", flush=True)
    if not passed:
        print("RESULTADO: motor NO causal-estable -> EXP-SEQ-CTX-01 SUSPENDIDO.", flush=True)
        print("No correr la matriz hasta cerrar la raiz del leakage.", flush=True)
    else:
        print("RESULTADO: motor causal-estable -> procede matriz S x Context.", flush=True)


if __name__ == "__main__":
    main()
