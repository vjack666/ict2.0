# Ejecución 2026-08-31 — primer entrenamiento IA desde Funnel + backtest

## AGENTE / DEPARTAMENTO / TAREA

- AGENTE: Codex, coordinando trabajadores CAIO/Datos, CAIO/Training y CRO/Research.
- DEPARTAMENTO: CAIO / IA, con D4 Data Lineage y D5 Assurance.
- TAREA: obtener el primer resultado de entrenamiento local usando únicamente
  episodios Funnel enlazados al backtest histórico, sin usar MT5.

## STATUS

`DIAGNOSTIC_ONLY_COMPLETED` — ajuste ejecutado y verificado; no es
`TRAINING_ELIGIBLE`, certificación científica ni autorización de trading.

## Cadena ejecutada

1. Replay histórico actual h200 en tres ventanas: 2006–2010, 2011–2015 y
   2016–2020. Cada ventana conserva margen posterior para resolver outcomes.
2. Bridge Funnel/backtest con namespaces deterministas por partición para evitar
   colisiones de `episode_id`.
3. Materializador por lotes con índices temporales y SQLite temporal, sin cargar
   arrays completos en memoria.
4. Corpus ordenado por `event_time`, validado por el loader causal y entregado al
   `OutcomeClassifier` real mediante la ruta `DIAGNOSTIC_ONLY`.

## Evidencia

- Filas: 86 episodios/trades actuales, IDs únicos 86/86.
- Clases: `continuation=11`, `reversal=54`, `failure=21`.
- Split diagnóstico cronológico: TRAIN 51, VALIDATION 17, TEST/OOS 18.
- Soporte TRAIN: continuation 6, failure 15, reversal 30.
- Modelo: `deterministic_multinomial_softmax`, 3 clases, 24 features, 500 iteraciones.
- Métricas TRAIN: accuracy 0.5882, log-loss 0.9161.
- Métricas VALIDATION: accuracy 0.7647, log-loss 0.6492.
- Métricas TEST/OOS diagnóstico: accuracy 0.6111, log-loss 1.0907.
- Artefacto: `diagnostic_train_2006_2020_h200_ns.json`.
- Hash del artefacto verificado: `cfae26b24f09b389a700caaf17abb96cc73be46b2b0eb44f4c8268ff63417557`.
- `fit_executed=true`, `model_training_executed=true`, `shadow_mode=true`,
  `can_trade=false`, `certified_snapshot=false`.
- Suite completa posterior a las correcciones: `443 passed`.

## Decisiones y límites

- El resultado demuestra que la cadena Funnel → backtest → labels →
  OutcomeClassifier funciona con datos reales actuales.
- El split usado es diagnóstico 60/20/20; no es todavía el split científico
  registrado DESIGN/VALIDATION/HOLDOUT completo porque falta 2021–2025.
- Los bridges y lotes conservan `BLOCKED` cuando no hay prueba FULL/PREFIX local
  para cada ventana; la ruta diagnóstica no convierte ese bloqueo en PASS.
- Dukascopy sigue con provenance/licencia/adquisición no certificadas. Los hashes
  no se usan como sustituto legal.
- No se creó snapshot certificado, checkpoint productivo, registro de promoción ni
  orden MT5.

## Siguiente acción

Generar la partición 2021–2025 y después decidir si se puede construir un
snapshot científico completo con gates explícitos. Antes de cualquier Shadow Mode
operativo se requiere auditoría independiente y autorización del cliente.
