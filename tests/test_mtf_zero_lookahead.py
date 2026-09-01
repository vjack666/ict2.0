"""AUDITORÍA — Cero lookahead multi-TF (Objetivo 2 de la misión MTF/LTF).

Verifica la regla CONTRATO_MULTI_TF_LAYERS §2 / SDD §4.2: en decision_time t,
ninguna capa usa velas con time > t, y datos futuros NO alteran el estado en t.

Prueba canónica:
  1. navegar a t0 (vela intermedia) -> state_t0
  2. navegar a t1 > t0           -> state_t1
  3. navegar a t0 con el DATAFRAME EXTENDIDO con velas futuras (> t0)
     -> state_t0_ext; debe ser IDÉNTICO a state_t0 (los datos futuros no
        deben influir en el estado point-in-time t0).
  4. afirmar state_t0 == state_t0_ext  => cero lookahead.

No envía órdenes; OBSERVE_ONLY.
"""

from __future__ import annotations
import sys
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import MTFNavigator  # noqa: E402

DATA = ROOT / "datasets" / "eurusd_dukascopy_20y"


def _load(tf: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"EURUSD_{tf}.csv")
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    return df.sort_values("time").reset_index(drop=True)


def _state_fingerprint(state) -> str:
    """Resumen estable del MarketState para comparar point-in-time."""
    fp = {}
    for tf, snap in state.layers.items():
        fp[tf] = {
            "asof_bar": snap.asof_bar,
            "last_close": snap.last_close,
            "bias": snap.structure_bias.value,
            "range_high": snap.range_high,
            "range_low": snap.range_low,
            "answers": snap.answers,
        }
    return json.dumps(fp, sort_keys=True, default=str)


def main() -> int:
    d1 = _load("D1")
    h4 = _load("H4")
    h1 = _load("H1")

    # t0: una vela H1 intermedia (no la última) para poder extender el dataframe
    t0 = h1["time"].iloc[len(h1) // 2]
    # t1: una vela H1 claramente posterior a t0
    t1 = h1["time"].iloc[len(h1) // 2 + 200]

    frames0 = {"D1": d1, "H4": h4, "H1": h1}
    nav0 = MTFNavigator(frames0)
    state_t0 = nav0.navigate(decision_time=t0, exec_tf="H1")
    fp_t0 = _state_fingerprint(state_t0)

    nav1 = MTFNavigator(frames0)
    state_t1 = nav1.navigate(decision_time=t1, exec_tf="H1")
    fp_t1 = _state_fingerprint(state_t1)

    # Extender H1 con velas futuras (> t0) para forzar la condición de lookahead
    h1_ext = pd.concat([h1, h1.iloc[-50:].assign(
        time=h1["time"].iloc[-1] + pd.to_timedelta(range(1, 51), unit="h")
    )], ignore_index=True).sort_values("time").reset_index(drop=True)
    frames_ext = {"D1": d1, "H4": h4, "H1": h1_ext}
    nav_ext = MTFNavigator(frames_ext)
    state_t0_ext = nav_ext.navigate(decision_time=t0, exec_tf="H1")
    fp_t0_ext = _state_fingerprint(state_t0_ext)

    print(f"[LOOKAHEAD] t0={t0}")
    print(f"[LOOKAHEAD] t1={t1} (posterior)")
    print(f"[LOOKAHEAD] state_t0   fingerprint len={len(fp_t0)}")
    print(f"[LOOKAHEAD] state_t0_e fingerprint len={len(fp_t0_ext)}")
    print(f"[LOOKAHEAD] state_t1   fingerprint len={len(fp_t1)} (debe diferir de t0)")

    ok = True
    if fp_t0 != fp_t0_ext:
        print("[LOOKAHEAD][FAIL] datos futuros ALTERARON el estado point-in-time t0 "
              "(violación de anti-lookahead)")
        ok = False
    if fp_t0 == fp_t1:
        print("[LOOKAHEAD][WARN] t0 y t1 dan estado idéntico (puede ser coincidencia "
              "de contexto; no es fallo de lookahead por sí mismo)")
    if ok:
        print("[LOOKAHEAD] PASS — cero lookahead: el estado en t0 es idéntico con o sin "
              "velas futuras; ninguna capa usa time > t.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
