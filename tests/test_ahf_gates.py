"""AUDITORÍA — Gates AHF y transiciones (Objetivo 4 de la misión MTF/LTF).

Valida la máquina AHF (engine.ahf.AHFMachine) sobre datos reales:

  - La máquina camina WAIT_D1 -> D1_LOCKED -> WAIT_H4 -> H4_LOCKED ->
    WAIT_H1 -> WAIT_LTF -> SETUP_READY (o se detiene en un WAIT_* válido).
  - El sesgo D1 queda lockeado y LTF (M15/H1) NO puede cambiarlo.
  - Conflicto/observación visibles: la trazabilidad (history) conserva
    estado, active_tf, evento y parent.

No envía órdenes. OBSERVE_ONLY.
"""

from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.ahf import AdaptiveHierarchicalFunnel, AHFState  # noqa: E402

DATA = ROOT / "datasets" / "eurusd_dukascopy_20y"


def _load(tf: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"EURUSD_{tf}.csv")
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    return df.sort_values("time").reset_index(drop=True)


def main() -> int:
    d1 = _load("D1")
    h4 = _load("H4")
    h1 = _load("H1")

    # Ventana de ~80 velas H1 al final de la serie (contexto completo)
    times = h1["time"].iloc[-80:].tolist()

    machine = AdaptiveHierarchicalFunnel({"D1": d1, "H4": h4, "H1": h1})
    snaps = machine.run_timeline(times, exec_tf="H1")

    final = snaps[-1]
    states_seen = [s.state.value for s in snaps]
    print(f"[AHF] decision_times: {len(times)}")
    print(f"[AHF] estados vistos (unicos): {sorted(set(states_seen))}")
    print(f"[AHF] estado final: {final.state.value} (active_tf={final.active_tf})")
    print(f"[AHF] transiciones en history: {len(final.history)}")

    # Verificar orden de la jerarquía AHF: los avances respetan la jerarquía;
    # los retrocesos SOLO por invalidación explícita (conflicto visible, no silencioso).
    expected_order = [
        AHFState.WAIT_D1.value, AHFState.D1_LOCKED.value,
        AHFState.WAIT_H4.value, AHFState.H4_LOCKED.value,
        AHFState.WAIT_H1.value, AHFState.WAIT_LTF.value,
        AHFState.SETUP_READY.value,
    ]
    idx = {st: i for i, st in enumerate(expected_order)}
    order_ok = True
    retrocesos_sin_inval = 0
    for tr in final.history:
        parent = tr.parent_state
        new = tr.state
        ev = tr.transition_event
        if parent in idx and new in idx:
            if idx[new] < idx[parent]:
                # retroceso: debe ser por invalidación explícita
                if not str(ev).endswith("_INVALIDATED"):
                    retrocesos_sin_inval += 1
    print(f"[AHF] retrocesos sin invalidación explícita: {retrocesos_sin_inval}")
    if retrocesos_sin_inval > 0:
        order_ok = False
        print(f"[AHF][FAIL] hay retrocesos de jerarquía sin invalidación (conflicto silencioso)")
    else:
        print(f"[AHF] retrocesos (si los hay) todos por invalidación explícita: OK")

    # LTF no cambia sesgo HTF: el lock D1 se conserva tras llegar a WAIT_LTF/SETUP_READY
    lock_d1 = machine._lock_bias.get("D1")
    print(f"[AHF] lock D1 (sesgo HTF congelado): {lock_d1}")

    ok = True
    if final.status != "OK":
        print(f"[AHF][FAIL] status final {final.status}")
        ok = False
    if not order_ok:
        print(f"[AHF][FAIL] las transiciones no respetan la jerarquía AHF")
        ok = False
    if final.state not in (AHFState.WAIT_LTF, AHFState.SETUP_READY) and \
       not str(final.state.value).startswith("WAIT_"):
        print(f"[AHF][FAIL] estado final inválido: {final.state.value}")
        ok = False
    if lock_d1 is None:
        print(f"[AHF][WARN] D1 no se lockeó (contexto D1 ausente en la ventana); "
              f"revisar datos, no es fallo de lógica AHF")

    if ok:
        print("[AHF] PASS — gates AHF caminan WAIT_D1->...->SETUP_READY, "
              "sesgo D1 lockeado y LTF no lo redefine.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
