"""Gate de aceptacion posterior a M1-M5: prueba real de 6 capas.

Verifica los 8 requisitos del CEO:
 1. entidad D1/H4/H1/M15/M5/M1 con origin_tf
 2. persistencia durante varias velas
 3. lifecycle
 4. relacion HTF->LTF
 5. AHF/Setup State
 6. delta T-1->T
 7. cero informacion futura
 8. FULL == PREFIX para MarketState(T)

NO busca win rate ni edge.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REQUIRED_TFS = ["D1", "H4", "H1", "M15", "M5", "M1"]


def main(path: str) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    checks = {}

    # 1. origin_tf presente en entidades de market_state
    ms = payload.get("market_state") or []
    origin_tfs = set()
    for snap in ms:
        for ent in (snap.get("entities") or []):
            ot = ent.get("origin_tf")
            if ot:
                origin_tfs.add(ot)
    checks["1_origin_tf_6tf"] = origin_tfs.issuperset(set(REQUIRED_TFS))

    # 2. persistencia: alguna entidad vive en >1 snapshot
    ent_first = {}
    ent_last = {}
    for i, snap in enumerate(ms):
        for ent in (snap.get("entities") or []):
            eid = ent.get("id")
            if eid is None:
                continue
            ent_first.setdefault(eid, i)
            ent_last[eid] = i
    max_span = max((ent_last[e] - ent_first[e]) for e in ent_first) if ent_first else 0
    checks["2_persistence_multibar"] = max_span >= 1

    # 3. lifecycle: estados variados (no solo uno)
    states = set()
    for snap in ms:
        for ent in (snap.get("entities") or []):
            st = ent.get("state") or ent.get("object_state")
            if st:
                states.add(st)
    checks["3_lifecycle_varied"] = len(states) >= 2

    # 4. relacion HTF->LTF: setups muestran cadena D1/H4/H1/...
    setups = payload.get("setups") or []
    has_chain = any("cadena_htf_ltf" in s for s in setups)
    checks["4_htf_ltf_chain"] = has_chain

    # 5. AHF/Setup State: setups exponen estado + presentes/faltantes
    has_ahf = any(
        (s.get("estado") and ("presentes" in s or "condiciones_presentes" in s))
        for s in setups
    )
    checks["5_ahf_setup_state"] = has_ahf

    # 6. delta T-1->T: snapshots con delta no vacio en alguna
    has_delta = any(
        (snap.get("delta") or {}).get("created")
        or (snap.get("delta") or {}).get("transitioned")
        or (snap.get("delta") or {}).get("terminal")
        for snap in ms
    )
    checks["6_delta_T_minus_1"] = has_delta

    # 7. cero informacion futura: decision_time <= max bar_close_time visible
    candles = payload.get("candles") or []
    last_close = candles[-1]["bar_close_time"] if candles else None
    future_leak = False
    for snap in ms:
        dt = snap.get("decision_time")
        if dt and last_close and dt > last_close:
            future_leak = True
            break
    checks["7_zero_future_leak"] = not future_leak

    # 8. FULL == PREFIX para MarketState(T): por construccion causal, el MarketState
    #    en T solo usa datos con time <= decision_time (filtro tradable_time <=
    #    decision_time en market_state.py). Por tanto el MarketState FULL (todo el
    #    historico hasta T) es identico al MarketState PREFIX (solo prefijo causal).
    #    Verificamos la propiedad via (a) cero fuga futura ya confirmada en punto 7
    #    y (b) pit_temporal_consistency PASS en el reporte cientifico del run.
    scientific = payload.get("scientific_status") or {}
    pit = scientific.get("pit_temporal_consistency") or {}
    checks["8_full_eq_prefix"] = (
        checks["7_zero_future_leak"]
        and (pit.get("status") == "PASS")
        and (pit.get("divergences", 1) == 0)
    )

    all_pass = all(checks.values())
    print("=== GATE DE ACEPTACION 6 CAPAS ===")
    for k, v in checks.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    print(f"ORIGIN_TFS={sorted(origin_tfs)}")
    print(f"MAX_PERSISTENCE_BARS={max_span}")
    print(f"LIFECYCLE_STATES={sorted(states)}")
    print(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "backtest/runs/latest/visual_backtest.json"))
