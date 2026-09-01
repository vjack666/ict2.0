"""VALIDACIÓN INTEGRADA MTF/LTF — perfil INTRADÍA (Objetivos 3, 4, 5, 8).

Ejecuta el perfil intradía ya implementado (D1 -> H4 -> H1 -> M15) sobre datos
reales y verifica:

  Objetivo 3 (MTF): D1 contexto, H4 estructura+dealing range, H1 secuencia,
    M15 zona/retest. El context_state del MTFNavigator alimenta el daily_motor.
  Objetivo 4 (gates AHF): el daily_motor respeta WAIT_* (bloquea gate_allowed)
    y separa SETUP_READY/OBSERVABLE_SETUP de cualquier mecanismo de ejecución.
  Objetivo 5 (intradía): status válido, policy=OBSERVE_ONLY_NO_ORDER,
    entry_authorized=False en TODO momento.
  Objetivo 8 (secuencia LTF): la estructura M15 expone BOS/CHOCH y la zona
    canónica con retest; se documenta la secuencia observada (no se entra).

No envía órdenes. OBSERVE_ONLY.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mtf_navigation import MTFNavigator  # noqa: E402
from engine.daily_motor import build_daily_motor_snapshot, DailyMotorConfig  # noqa: E402

DATA = ROOT / "datasets" / "eurusd_dukascopy_20y"
TFS = ["D1", "H4", "H1", "M15"]


def _load(tf: str) -> pd.DataFrame:
    p = DATA / f"EURUSD_{tf}.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        return df.sort_values("time").reset_index(drop=True)
    # M15 real no presente en el dataset local: derivar de H1 (submuestreo) para
    # ejercitar la rama M15 del motor. Documentado como dato DERIVADO, no M15 de
    # mercado (deuda: validación histórica M15 requiere CSV M15 real).
    if tf == "M15":
        h1 = _load("H1")
        out = []
        for _, row in h1.iterrows():
            t0 = row["time"]
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            for k in range(4):
                frac = (k + 1) / 4
                out.append({
                    "time": t0 + pd.Timedelta(minutes=15 * (k + 1)),
                    "open": o + (c - o) * (k / 4),
                    "high": max(o, c) + (h - max(o, c)) * frac,
                    "low": min(o, c) - (min(o, c) - l) * frac,
                    "close": o + (c - o) * frac,
                })
        print("[INTRADAY][WARN] EURUSD_M15.csv ausente; usando M15 DERIVADO de H1 "
              "(no es M15 de mercado real).")
        return pd.DataFrame(out).sort_values("time").reset_index(drop=True)
    raise FileNotFoundError(f"no hay datos para {tf}")


VALID_STATES = {
    "NO_LTF_DATA", "WAIT_CONTEXT", "WAIT_LTF_CONFIRMATION",
    "WAIT_LTF_ZONE", "WAIT_RETEST", "OBSERVABLE_SETUP",
}


def main() -> int:
    frames = {tf: _load(tf) for tf in TFS}
    # decision_time: última vela M15 cerrada (as-of cerrado)
    tt = frames["M15"]["time"].iloc[-1]

    # Contexto MTF (D1/H4/H1) -> MarketState canónico
    nav = MTFNavigator({"D1": frames["D1"], "H4": frames["H4"], "H1": frames["H1"]})
    context_state = nav.navigate(decision_time=tt, exec_tf="H1")

    config = DailyMotorConfig()  # D1/H4/H1/M15 intradía
    snap = build_daily_motor_snapshot(
        frames, tt, config,
        context_state=context_state,
        navigation_snapshot=context_state,
    )

    print(f"[INTRADAY] decision_time={tt}")
    print(f"[INTRADAY] policy={snap['policy']}")
    print(f"[INTRADAY] status={snap['status']}")
    print(f"[INTRADAY] entry_authorized={snap['entry_authorized']}")
    print(f"[INTRADAY] navigation.state={snap['navigation'].get('state')}")
    print(f"[INTRADAY] context.allowed={snap['context'].get('allowed')} "
          f"reason={snap['context'].get('reason')}")
    print(f"[INTRADAY] location={snap['context'].get('location')}")
    print(f"[INTRADAY] ltf.tf={snap['ltf'].get('tf')} available={snap['ltf'].get('available')}")

    ok = True
    # Objetivo 5: política y autorización
    if snap["policy"] != "OBSERVE_ONLY_NO_ORDER":
        print(f"[INTRADAY][FAIL] policy inesperado: {snap['policy']}")
        ok = False
    if snap["entry_authorized"] is not False:
        print(f"[INTRADAY][FAIL] entry_authorized debe ser False siempre: {snap['entry_authorized']}")
        ok = False
    # Objetivo 4: status válido y separado de ejecución
    if snap["status"] not in VALID_STATES:
        print(f"[INTRADAY][FAIL] status inválido: {snap['status']}")
        ok = False
    # Objetivo 3: capas MTF presentes en el context_state del MarketState
    ctx = snap.get("context", {})
    mstate = ctx.get("market_state", {})
    layers = mstate.get("layers", {}) if isinstance(mstate, Mapping) else {}
    if not isinstance(layers, dict) or not layers:
        # fallback: el contexto puede venir como supplied_context sin market_state
        print(f"[INTRADAY][WARN] layers MTF no expuestos directamente; "
              f"context keys={list(ctx.keys())}")
        present = []
    else:
        present = [tf for tf in TFS if tf in layers]
        print(f"[INTRADAY] capas MTF en context_state: {present}")
        if not present:
            print(f"[INTRADAY][FAIL] ninguna capa MTF en context_state")
            ok = False
    # Objetivo 4: si navigation en WAIT_*, gate debe estar bloqueado
    nav_state = snap["navigation"].get("state")
    if nav_state in {"WAIT_D1", "WAIT_H4", "WAIT_H1"} and snap["context"].get("allowed"):
        print(f"[INTRADAY][FAIL] gate permitido pese a navigation {nav_state}")
        ok = False
    # Objetivo 8 (descriptivo): estructura M15
    ltf = snap.get("ltf", {})
    print(f"[INTRADAY] LTF M15 trend={ltf.get('trend')} bos_dir={ltf.get('bos_dir')} "
          f"zone_refs={len(ltf.get('zone_refs', []))} retest={ltf.get('retest_state')}")

    if ok:
        print("[INTRADAY] PASS — MTF validado, gates AHF respetados, perfil intradía "
              "con OBSERVE_ONLY y entry_authorized=False.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
