# SETUP_GRAMMAR_SUPERVISION_V1

**Fecha:** 2026-09-15  
**Estado:** `READY_FOR_MATERIALIZATION_DESIGN`  
**Autoridad:** documentacion local + motor causal, `can_trade=false`

## Proposito

Crear una linea de aprendizaje donde las neuronas no solo predicen outcome o
fallo, sino que aprenden la gramatica del setup ICT documentada en la tesis.

La red debe aprender preguntas intermedias:

```text
¿La narrativa HTF existe?
¿La manipulacion/sweep es real?
¿Hay displacement suficiente?
¿La estructura confirma?
¿La zona FVG/OB es usable?
¿El precio retorno a la zona?
¿El POI tiene contexto o es geometria suelta?
¿La entrada/SL/TP pertenecen al exec TF correcto?
¿El candidato debe pasar, esperar, abstenerse o rechazarse?
```

## Fuentes locales de verdad

| Tema | Fuente |
| --- | --- |
| Tesis unificada PO3/AMD | `docs/ict/20_TESIS_ICT.md` |
| Regla HTF/ITF/exec | `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md` |
| POI narrativo y stacking | `docs/ict/21_POI.md` |
| Rulebook operacional ICT | `docs/reglas/ICT_RULEBOOK.md` |
| Espera por eventos | `docs/tesis/SDD_SEQUENCE_EVENT_WAIT.md` |
| Capa LTF/Wyckoff | `docs/tesis/SDD_LTF_ENTRY_LAYER.md` |
| Evidencia M15 ensamblada | `reports/b1/OBJETIVO2_DISENIO_ENSAMBLADOR.json` |

## Gramatica del setup

| Nodo | Pregunta que aprende la red | Evidencia local | Target sugerido |
| --- | --- | --- | --- |
| `htf_narrative` | ¿H4/H1/D1 dan direccion y restricciones coherentes? | `context_state`, `daily_motor`, `h1_alignment`, `h4_location` | `HTF_OK`, `HTF_CONFLICT`, `HTF_UNKNOWN` |
| `po3_phase` | ¿Existe ciclo A→M→D y no solo una pieza aislada? | sweep + displacement + structure + zone + retest | `A_ONLY`, `M_PRESENT`, `D_CONFIRMED`, `CHAIN_COMPLETE` |
| `liquidity_sweep` | ¿El sweep caza liquidez y cierra de vuelta adentro? | `canonical_sweep`, `m15_evidence.sweep` | `SWEEP_VALID`, `NO_SWEEP`, `TRUE_BREAK` |
| `displacement_quality` | ¿El movimiento tiene cuerpo fuerte y deja imbalance? | body/range, displacement object, FVG/OB | `STRONG`, `WEAK`, `NO_DISPLACEMENT` |
| `structure_confirmation` | ¿BOS/CHOCH/MSS confirma despues del sweep? | `m15_evidence.bos_or_choch`, BOS/CHOCH objects | `CONFIRMED`, `WAIT_STRUCTURE`, `CONFLICT` |
| `pd_array_zone` | ¿FVG/OB es zona de retorno usable? | FVG/OB state, fill/mitigation, geometry | `USABLE`, `MITIGATED`, `INVALID`, `NO_ZONE` |
| `retest_entry` | ¿El precio regreso a la zona en vela cerrada? | `m15_evidence.retest`, candle touch | `RETESTED`, `WAIT_RETEST`, `LATE_ENTRY` |
| `poi_quality` | ¿El POI tiene discount/premium correcto, sesgo y respaldo? | `21_POI.md`, market objects, context | `T1`, `T2`, `T3`, `SKIP`, `UNKNOWN` |
| `exec_tf_integrity` | ¿Entry/SL/TP estan en el exec TF correcto? | `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`, replay fields | `EXEC_OK`, `WRONG_TF`, `UNKNOWN` |
| `setup_decision` | ¿Pasar, esperar, abstenerse o rechazar? | Todos los nodos anteriores | `PASS`, `WAIT`, `ABSTAIN`, `REJECT` |

## Cabezas neuronales propuestas

La red `setup_quality_v1` debe ser multi-task:

1. `setup_decision_head`: PASS / WAIT / ABSTAIN / REJECT.
2. `weak_link_head`: pieza mas debil del setup.
3. `failure_risk_head`: probabilidad de fallo.
4. `quality_tier_head`: calidad POI/setup T1/T2/T3/SKIP.
5. `outcome_head`: continuation / reversal / failure.

## Reglas de seguridad

- La tesis guia etiquetas y features, no autoriza trading.
- La IA aprende diagnostico y calidad; no crea ordenes.
- `can_trade=false` y `entry_authorized=false` permanecen.
- Fuentes externas se usan solo cuando un hueco quede marcado como
  `RESEARCH_REQUIRED`.
- Todo conocimiento externo debe convertirse en contrato local antes de
  entrenar.

## Huecos que requieren investigacion o implementacion

| Hueco | Tipo | Estado |
| --- | --- | --- |
| `entry_return_to_zone` materializado como feature causal universal | implementacion | `RESEARCH_NOT_REQUIRED_IMPLEMENTATION_REQUIRED` |
| `closest_opposing_liquidity_tp` como target/feature economico | implementacion | `RESEARCH_NOT_REQUIRED_IMPLEMENTATION_REQUIRED` |
| `poi_tier_stacking` en dataset historico | implementacion | `RESEARCH_NOT_REQUIRED_IMPLEMENTATION_REQUIRED` |
| killzones London/NY con timezone broker/UTC exacta | investigacion + implementacion | `RESEARCH_REQUIRED` |
| M3 exec TF y scalping fino | investigacion + implementacion | `RESEARCH_REQUIRED` |
| Breaker/Mitigation/BPR completos como PD Arrays entrenables | investigacion + implementacion | `RESEARCH_REQUIRED` |

## Siguiente artefacto

`SETUP_GRAMMAR_DATASET_V1`: materializar una tabla causal por `decision_time`
con todos los nodos anteriores, sus fuentes, timestamps y etiquetas.
