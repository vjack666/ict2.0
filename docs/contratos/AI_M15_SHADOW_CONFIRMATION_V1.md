# AI_M15_SHADOW_CONFIRMATION_V1

**Fecha:** 2026-09-15  
**Estado:** `REVIEW_READY_FOR_SHADOW_DATASET`  
**Autoridad:** diagnostico local, `can_trade=false`

## Proposito

Definir como se une la linea de aprendizaje IA (`tf_outcome_v1_003` +
`failure_risk_v1`) con el motor M15 intradia sin cambiar la autoridad del
motor ni habilitar operaciones.

La IA no modifica el motor. La IA observa candidatos producidos por el motor,
aprende patrones de resultado y devuelve etiquetas de diagnostico en sombra:

- `ai_accept_shadow`: el candidato se parece a casos historicos con mejor
  expectativa relativa.
- `ai_reject_shadow`: el candidato se parece a casos historicos con riesgo de
  fallo elevado.
- `ai_abstain_shadow`: la evidencia no alcanza para opinar.

Ninguna etiqueta autoriza trade, orden, lote, entrada, SL o TP.

## Entrada minima

Un registro de entrenamiento o evaluacion debe contener:

1. Contexto HTF cerrado: H4/H1 alineacion, restricciones de lado y direccion
   contextual.
2. Evidencia M15 causal cerrada:
   - `sweep`
   - `displacement`
   - `bos_or_choch`
   - `fvg_or_ob`
   - `retest`
3. Confirmacion operativa opcional POI+Stoch:
   - POI HTF elegible cerca del precio.
   - cruce estocastico M15 cerrado compatible.
   - `cross_id` no reutilizado.
4. Resultado historico etiquetado para entrenamiento/evaluacion.

## Reglas de frontera

- El motor determinista decide si existe `CANDIDATE_SETUP` o `ENTRY_VALID`
  diagnostico.
- La IA solo califica el candidato despues de que el motor lo produce.
- `can_trade=false` y `entry_authorized=false` permanecen obligatorios.
- La fusion con IA es sombra; no se escribe snapshot operable.
- TEST/OOS no se usa para seleccionar thresholds.

## Gates minimos para pasar a dataset sombra

| Gate | Minimo |
| --- | --- |
| Formato M15 | `assess_mechanical_signal` acepta evidencia booleana y evidencia rica `{present,time,source}` |
| POI+Stoch | pruebas focales pasan sin regresion |
| Snapshot actual | no se toma como evidencia live si esta stale |
| IA | shadow fusion ya tiene dictamen diagnostico, no produccion |
| Seguridad | `can_trade=false` intacto |

## Estado actual

`PASS_BRIDGE_MECHANICS`: el evaluador mecanico ya puede leer el formato rico
que produce `engine.m15_evidence_assembler`.

`REVIEW_DATASET_REQUIRED`: falta materializar un dataset sombra que una cada
decision_time con:

```
M15 chain -> POI+Stoch diagnostic -> AI shadow scores -> outcome label
```

## Siguiente contrato

`M15_INTRADAY_SHADOW_DATASET_V1`: materializar y validar la tabla causal
local para medir si la IA mejora la seleccion de candidatos entre Londres y NY.
