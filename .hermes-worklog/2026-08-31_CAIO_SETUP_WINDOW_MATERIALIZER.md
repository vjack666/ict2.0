# CAIO/Datos — materializador causal por ventanas

## AGENTE

Codex / CAIO-Datos

## DEPARTAMENTO

Piso 3 — IA, con límite de datos de investigación del Piso 4.

## TAREA

Crear una utilidad nueva que materialice filas de setups desde artefactos ya
producidos por Funnel y backtest, por ventanas temporales y en lotes, sin
ejecutar replay ni cargar el histórico completo en memoria. MT5 queda fuera del
flujo.

## IMPLEMENTACIÓN

Se añadió `scripts/lab/experiments/ai_setup_window_materializer.py`. El lector
recorre el JSON por streaming y retiene solamente:

- metadatos y procedencia;
- episodios dentro de la ventana solicitada;
- trades cuyo `signal_index` está enlazado por el Funnel;
- timestamps de candles en los índices necesarios para validar entrada, salida
  y horizonte.

La salida es JSONL y el resumen contiene hashes SHA-256 de entradas y salida,
horizonte, split temporal registrado, conteos, diagnósticos y evidencia del
generador. Se pueden repetir ventanas con `--window` y controlar el vaciado
con `--batch-size`.

## CONTROLES

- `decision_time` procede del Episode; no se recalcula.
- El horizonte procede de `backtest.metadata.outcome.horizon_bars` salvo
  override explícito.
- El split es temporal `DESIGN/VALIDATION/HOLDOUT`; no hay split aleatorio.
- Features futuras, dirección inconsistente, índices inválidos y salidas fuera
  del horizonte se rechazan.
- `can_trade=false`, `training_eligible=false` y `promotion_authorized=false`.
- La procedencia se conserva y cualquier `BLOCKED` no se degrada a `PASS`.
- No se leen `data/raw`, no se usan parquets MT5 y no se ejecuta el replay.
- No se sobrescriben entradas ni salidas existentes.

## EVIDENCIA

Tests exclusivos de la utilidad: `5 passed`.

Prueba real con los artefactos mensuales actuales:

- 1 fila materializada;
- split `HOLDOUT`;
- horizonte `200`;
- etiqueta `reversal`;
- 0 filas rechazadas;
- estado de materialización `PASS`;
- estado global `BLOCKED` por procedencia Dukascopy declarada como bloqueada;
- `can_trade=false`.

Artefactos de la prueba:

- `reports/audits/experiments/ai/caio_setup_window_2025_01_rows_v3.jsonl`
- `reports/audits/experiments/ai/caio_setup_window_2025_01_rows_v3.summary.json`

`graphify update .` se ejecutó después del cambio de código.

La suite completa del repositorio terminó con `436 passed, 5 failed`; los cinco
fallos corresponden a otra utilidad/pruebas paralelas no incluidas en este
parche (`ai_outcome_batch_materializer` y `diagnostic_training`). No se
modificaron para respetar el alcance. Los 5 tests focales de esta misión
siguen pasando.

## STATUS

COMPLETED para el alcance de utilidad y materialización técnica.

La salida no es un dataset certificable ni un modelo entrenado: la procedencia
Dukascopy sigue `BLOCKED` y una sola ventana mensual solo sirve como smoke test.

## SIGUIENTE ACCIÓN

Procesar ventanas mensuales adicionales en lotes, acumular suficientes clases y
particiones temporales, y ejecutar el entrenamiento diagnóstico en Shadow Mode
solo después de que el contrato científico correspondiente lo permita.
