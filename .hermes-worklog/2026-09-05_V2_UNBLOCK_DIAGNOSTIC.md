# V2 unblock: corpus canónico y entrenamiento diagnóstico

## Estado

`DIAGNOSTIC_ONLY_COMPLETED`; `can_trade=false`; no promoción ni órdenes.

## Evidencia reproducible

- Extractor: `scripts/lab/experiments/v2_extractor_engine.py`.
- Ventana: Q1 2022, datos locales `data/raw/EURUSD`.
- Salida: `data/materialized/v2/v2_engine_2022_q1_current.jsonl`.
- Filas aceptadas: 6.067; rechazadas: 6 (`no_label_window`).
- Clases: continuation, reversal, failure.
- Derivado temporal para el runner: `v2_engine_2022_q1_current_train.jsonl`, con `event_time=decision_time`.
- Artefacto: `runtime/ai_learning/artifacts/unblock_v2_q1_diagnostic.json`.
- Feature health: 15 features, 12 variables, fracción variable 0,80.
- Split: 60% train (3.640), 20% validation (1.213), 20% OOS (1.214).

## Resultado

Accuracy OOS: `0.4818780889621087`.
La clase mayoritaria OOS es continuation (588/1214 = `0.484349...`); la comparación exacta es `0.481878 - 588/1214 = -0.002471`. El resultado es ligeramente inferior a la línea base. Log-loss OOS: `0.8379785287477463`.

El signo se conserva: no se ajustan métricas, etiquetas ni datos para convertir un resultado negativo en positivo. El corpus y el entrenamiento quedan desbloqueados técnicamente, pero la evidencia de edge sigue pendiente.

## Verificación

`python -m pytest tests/test_v2_extractor_engine.py tests/test_feature_health.py -q` → `6 passed`.

## Siguiente acción

Repetir funnel y backtest usando este mismo corpus/snapshot y comparar contra una línea base definida, manteniendo modo diagnóstico y `can_trade=false`.

## Backtest y funnel posteriores

- Backtest canónico Q1 2022: `reports/audits/experiments/ai/v2_unblock_q1_backtest.json`.
- 6.073 velas, 4.898 eventos, 0 señales y 0 trades. El motor observó 123 `SWEEP`, pero 0 `DISPLACE`, 0 `BOS` y 0 `ENTRY`; con `require_displacement=true` no se generaron entradas.
- Bridge del funnel: `BACKTEST_SIGNALS_MISSING`; queda bloqueado correctamente porque no hay señales que enlazar. No se inventaron episodios ni outcomes.
- Por tanto, no hay una comparación económica positiva o negativa en esta corrida: la muestra de trades es cero. El resultado negativo medible sigue siendo el OOS del modelo (`-0.002471` frente a la mayoría).
