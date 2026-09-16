# Execution Calibration Preflight V2

## Dictamen

Estado: **REVIEW**. El artefacto verifica cobertura de fuente y prueba real de `fine_execution()` de forma diagnostica. No autoriza ejecucion, entradas ni trading.

## Cobertura de fuentes

| Split | Filas | Fuente y tiempo validos | Errores de fuente |
| --- | ---: | ---: | ---: |
| TRAIN | 120 | 120 | 0 |
| VALIDATION | 96 | 96 | 0 |
| TEST_OOS | 76 | 76 | 0 |

## Frecuencia

- PASS como filas de label: `6`.
- PASS deduplicados por evento economico: `5`.
- Semanas calendario: `1036`; semanas con decision points: `67`.
- Frecuencia relevante contra calendario: `0.004826` setups/semana.
- Frecuencia interna por semanas con decision points: `0.074627` setups/semana.

## Ejecucion M15 reconstruida

| Split | Ventana | Probadas | OK | Fail | Causalidad | Motivo principal |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| TRAIN | 4 | 120 | 0 | 120 | 0 | not_enough_bars |
| TRAIN | 30 | 120 | 119 | 1 | 0 | not_enough_source_history |
| TRAIN | 50 | 120 | 118 | 2 | 0 | not_enough_source_history |
| TRAIN | 100 | 120 | 118 | 2 | 0 | not_enough_source_history |
| VALIDATION | 4 | 96 | 0 | 96 | 0 | not_enough_bars |
| VALIDATION | 30 | 96 | 96 | 0 | 0 | - |
| VALIDATION | 50 | 96 | 96 | 0 | 0 | - |
| VALIDATION | 100 | 96 | 90 | 6 | 0 | not_enough_source_history |
| TEST_OOS | 4 | 76 | 0 | 76 | 0 | not_enough_bars |
| TEST_OOS | 30 | 76 | 76 | 0 | 0 | - |
| TEST_OOS | 50 | 76 | 76 | 0 | 0 | - |
| TEST_OOS | 100 | 76 | 76 | 0 | 0 | - |

## Gates y limites

- `can_trade=false` y `entry_authorized=false` se mantienen en todo el dataset inspeccionado.
- `sweep_ts` no esta materializado como ancla de SL; esta prueba usa el fallback estructural de `fine_execution()`.
- Las ventanas se recortan estrictamente a `time <= decision_time`; toda violacion se registra como fallo causal.
- El resultado no mide fills, costes, PnL ni edge. Es previo al contrato `PASS_EDGE_INTRADIA`.

## Siguiente accion

Construir el `FREQ_GATE_2_3_WEEKLY` y el generador determinista multimodelo antes de cualquier dataset de IA condicionado por estrategia.
