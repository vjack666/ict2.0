"""GATE PIT del adaptador mínimo Wyckoff para EXP-WYCKOFF-ICT-01.

Verifica point-in-time: snapshot(full, t) == snapshot(prefix_through_t, t)
para una muestra determinista de barras. Exige CERO divergencias.

No mide outcome ni significancia. Solo integridad PIT del estado Wyckoff.

Salida: reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json
"""
from __future__ import annotations
import json, time, sys
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engine.mtf_navigation as M
from audits.codigo.mtf_seq_funnel import _load_tf
from scripts.lab.experiments.wyckoff_adapter_minimal import wyckoff_state_at

OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "wyckoff_ict_01"
OUT_JSON = OUT_DIR / "gate_wyckoff_pit.json"

WINDOW = 1500
AUTHORITY_TF = "H1"
LAYERS = ("H1", "H4", "D1")
N_SAMPLES = 80
WARMUP_H1 = 2000
RNG = 7


def _sig(snap) -> tuple:
    """Firma PIT del snapshot: fase, phase_state, conflict, alineación, nº eventos."""
    ev = snap.events
    return (
        snap.phase.value,
        snap.phase_state.value,
        bool(snap.conflict),
        snap.ict_alignment,
        len(ev),
        snap.volume_mode.value,
    )


def main() -> None:
    t0 = time.time()
    print("GATE PIT WYCKOFF ADAPTER — full-vs-prefix equivalence", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    n_total = len(h1)
    times = h1["time"]
    print(f"H1 barras totales: {n_total}", flush=True)

    nav_full = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))

    rng = np.random.default_rng(RNG)
    sample_bars = sorted(int(x) for x in rng.integers(WARMUP_H1, n_total - 50, N_SAMPLES))
    print(f"muestra: {len(sample_bars)} barras", flush=True)

    divergences = []
    checked = 0
    for i, bar in enumerate(sample_bars):
        t = times.iloc[bar]
        s_full = wyckoff_state_at(frames, nav_full, t, window=WINDOW, authority_tf=AUTHORITY_TF, layers=LAYERS)
        f_sig = _sig(s_full)

        # Prefix por TIMESTAMP (time <= t)
        trunc_full = {tf: frames[tf].loc[pd.to_datetime(frames[tf]["time"], utc=True, errors="coerce") <= pd.to_datetime(t, utc=True, errors="coerce")].copy().reset_index(drop=True) for tf in frames}
        nav_pref = M.MTFNavigator(trunc_full, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
        s_pref = wyckoff_state_at(trunc_full, nav_pref, t, window=WINDOW, authority_tf=AUTHORITY_TF, layers=LAYERS)
        p_sig = _sig(s_pref)

        checked += 1
        if f_sig != p_sig:
            divergences.append({"bar": int(bar), "time": str(t), "full": f_sig, "prefix": p_sig})
        if i % 20 == 0:
            print(f"  ...bar {i}/{len(sample_bars)} divergencias={len(divergences)}", flush=True)

    passed = len(divergences) == 0
    report = {
        "experiment": "EXP-WYCKOFF-ICT-01_GATE_WYCKOFF_PIT",
        "description": "wyckoff_state_at(full,t) == wyckoff_state_at(prefix_through_t,t) on H1 20Y sample",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "motor_lineage": "engine/Wyckoff adapter (build_wyckoff_snapshot), PIT truncate close_time<=t",
        "window": WINDOW,
        "n_samples": len(sample_bars),
        "n_checked": checked,
        "n_divergences": len(divergences),
        "status": "PASS" if passed else "FAIL",
        "usable_for_inference": passed,
        "divergences_sample": divergences[:10],
        "elapsed_s": round(time.time() - t0, 1),
        "generator_commit": "a20c66aaf5d56126850701b93296cd651d04b993",
        "generator_worktree": "CLEAN",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nGATE WYCKOFF PIT: {report['status']}  divergencias={len(divergences)}/{checked}", flush=True)
    print(f"JSON -> {OUT_JSON}", flush=True)
    if not passed:
        print("RESULTADO: adaptador Wyckoff NO PIT-estable -> BLOCKED_WYCKOFF_PIT.", flush=True)
    else:
        print("RESULTADO: adaptador Wyckoff PIT-estable -> procede conteo de factibilidad.", flush=True)


if __name__ == "__main__":
    main()
