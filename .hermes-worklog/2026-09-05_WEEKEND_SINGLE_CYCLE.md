# Ciclo único de entrenamiento del fin de semana

## Alcance

Una sola corrida diagnóstica sobre el corpus V2 canónico de seis temporalidades (`data/materialized/v2/v2_engine_2022_q1_current_train.jsonl`). No se mezcló con Dukascopy M15 y no se ejecutaron reintentos, loops, funnel ni backtest adicionales.

## Resultado

- Artefacto: `runtime/ai_learning/artifacts/weekend_v2_single_cycle.json`.
- Estado: `DIAGNOSTIC_ONLY_COMPLETED`.
- Filas: 6.067; train 3.640, validation 1.213, OOS 1.214.
- Feature health: 0,80 de variación (12/15 features).
- Accuracy OOS: `0.4818780889621087`.
- Base mayoritaria OOS: `0.4843492586490939`.
- Delta: `-0.0024711696869851862`.
- Log-loss OOS: `0.8379720801536794`.
- `can_trade=false`.

El resultado se conserva tal como salió. No se ajustó el signo ni se alteraron etiquetas, features o métricas. El ciclo termina aquí para evitar ejecución sin sentido.
