# CAIO — Primer entrenamiento DIAGNOSTIC_ONLY

**Fecha:** 2026-08-31
**Agente:** Codex / CAIO Training Engineering
**Departamento:** D3 IA
**Tarea:** Probar la ruta `JSONL causal materializado -> split temporal -> OutcomeClassifier` sin snapshot certificado ni promoción.
**Modo:** `LOCAL_ONLY`

## Resultado

`BLOCKED / INSUFFICIENT_DATA` de forma intencional y fail-closed.

El JSONL causal enlazado al Funnel y al backtest contiene 1 fila:

- `continuation`: 0
- `reversal`: 1
- `failure`: 0

El clasificador real exige 30 filas en TRAIN, 10 en VALIDATION y 10 en
TEST/OOS. Con el split diagnóstico 60/20/20, el mínimo mecánico es 50 filas;
además TRAIN necesita al menos 5 observaciones de cada clase. Faltan al menos
49 filas y todavía no existe una ventana temporal calificable. No se duplicó,
rellenó ni sintetizó ninguna observación.

## Implementación

Se crearon únicamente archivos nuevos:

- `runtime/ai_learning/diagnostic_training.py`: lector/validador JSONL causal,
  cálculo de ventana mínima, split temporal y adaptador en memoria que invoca
  el `train_outcome_classifier` real sólo cuando se cumplen los mínimos.
- `scripts/lab/experiments/ai_outcome_diagnostic_train.py`: runner local,
  salida inmutable y código de retorno fail-closed.
- `tests/test_ai_outcome_diagnostic_train.py`: seis pruebas nuevas.
- `reports/audits/experiments/ai/visual_backtest_2025_01_diagnostic_only_h200.json`:
  evidencia de la ejecución real.

Cuando haya suficientes filas, la misma ruta producirá métricas TRAIN,
VALIDATION y TEST/OOS y el artefacto del `OutcomeClassifier` real. Ese resultado
seguirá marcado `DIAGNOSTIC_ONLY_COMPLETED`, `certified_snapshot=false`,
`scientific_training_eligible=false`, `promotion_authorized=false` y
`can_trade=false`.

## Evidencia

- Tests focales: `30 passed`.
- Suite completa: `439 passed`, 2 fallos preexistentes en
  `tests/test_ai_outcome_batch_materializer.py`, ambos por
  `JSON_FIELD_MISSING:gates`; no pertenecen a esta ruta y no fueron alterados.
- Artefacto diagnóstico: `artifact_hash=978fa4373443915e16be09f0cb2ce3e503df1116530db6f186fde4a0758cfc05`.
- El artefacto confirma `fit_executed=false`, `can_trade=false`, sin modelo,
  sin snapshot y sin promoción.

## Riesgos y siguiente acción

La fuente Dukascopy continúa siendo investigación histórica y mantiene su
limitación de procedencia documentada; MT5 no se mezcló. La siguiente acción es
materializar una ventana histórica más amplia desde el Funnel/backtest real,
sin cambiar el target ni fabricar clases, hasta alcanzar 50 filas y el soporte
de tres clases en TRAIN. Sólo después se podrá obtener un resultado diagnóstico
de ajuste; no implica certificación científica ni trading.
