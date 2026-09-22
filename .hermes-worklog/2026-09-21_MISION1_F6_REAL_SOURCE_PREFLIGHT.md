# Bitacora — Mision 1 F6 real-source preflight

**Fecha:** 2026-09-21  
**Agente:** Codex / CEO operativo  
**Departamento:** D2 ingenieria, D4 datos, D5 assurance  
**Estado:** `PARTIAL_PASS / PRODUCER_SIXTF_PENDING`

## Solicitud

Ruben pidio continuar con la fase siguiente y buscar en los SDD ya escritos y
tareas pendientes.

## Hallazgo documental

La fase siguiente ya estaba escrita en:

- `.hermes/plans/2026-09-21_MISION1_SIXTF_FUNNEL_BACKTEST_IA.md`
- `docs/planificacion/SDD_MISION1_SIXTF_FUNNEL_BACKTEST_IA_V1.md`
- `.hermes-worklog/2026-09-21_MISION1_F2_F5_COMPLETED.md`
- `governance/ORGANIGRAMA_ICT_2_0.md`
- `.hermes-worklog/2026-09-20_GPT_CAUSAL_REPLAY_PILOT_H4_M15.md`

La tarea pendiente exacta es reemplazar la fixture contractual de F2 por un
productor historico real sobre fuente original, conservando los gates seis-TF,
FULL/PREFIX, future injection y Episodes/Funnel.

## Verificacion real ejecutada

### Gate seis-TF de contexto real

Comando:

```text
python scripts/audit/verify_sixtf_causal_sequence_phase1.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip" --manifest benchmark\eurusd_multitf\BENCHMARK_DATA_MANIFEST.json --output reports\audits\experiments\mission1\mission1_next_real_source_sixtf_context.json
```

Resultado:

```text
all_pass=true
zip_hash_pass=true
source_hashes_pass=true
all_six_layers_available=true
all_six_layers_closed_only=true
future_invariance=true
htf_provenance_future_invariance=true
at_least_one_real_htf_parent=true
control_a_m1_coverage=false
```

`control_a_m1_coverage=false` es esperado: la fuente M1 termina el
2026-08-24T20:38Z y no cubre el control A de 2026-09-17.

### Gate productor/replay historico real existente

Comando:

```text
python scripts/audit/verify_causal_replay_ab.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip" --manifest benchmark\eurusd_multitf\BENCHMARK_DATA_MANIFEST.json --output reports\audits\experiments\mission1\mission1_next_real_source_h4_m15_replay.json
```

Resultado:

```text
all_pass=true
control A = PASS_H4_M15_PIT_PILOT, 28 MarketObjects
control B = PASS_H4_M15_PIT_PILOT, 26 MarketObjects
```

## Dictamen

La fuente real y el replay causal existente pasan sus gates. Sin embargo, el
productor historico real en `engine/historical_event_objects.py` sigue teniendo
alcance H4/M15. Por eso esta fase no puede declararse full funnel seis-TF real.

## Siguiente implementacion

Extender el productor historico para emitir objetos y relaciones completas:

```text
D1 context -> H4 POI -> H1 context/refinement -> M15 refinement/structure
-> M5 confirmation -> M1 trigger/retest
```

Luego debe alimentar `build_episodes` real y repetir FULL/PREFIX/future
injection. Hasta entonces:

```text
REAL_SOURCE_PREFLIGHT=PASS
REAL_SIXTF_PRODUCER=PENDING
REAL_FUNNEL_EPISODES=PENDING
can_trade=false
```

