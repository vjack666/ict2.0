# Plan operativo — IA de outcomes ICT v1

**Owner:** Codex/CEO operativo
**Departamentos:** D3 IA, D4 Datos, D5 Assurance, D1 Documentación
**Modo:** LOCAL_ONLY
**Contrato:** `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md`
**SDD:** `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md`

## Objetivo

Construir una primera IA que aprenda de eventos históricos ICT y clasifique
`continuation/reversal/failure`, sin confundir aprendizaje con edge ni con una
orden.

## Reglas

1. Dukascopy es el plano de investigación; MT5 solo será la punta operativa y
   Shadow Mode posterior.
2. Reusar `TrainingPipeline`, `ModelRegistry`, calibration, abstention y drift;
   no crear una segunda registry ni una segunda política.
3. Si el gate científico no dice `TRAINING_ELIGIBLE`, bloquear el entrenamiento.
4. TRAIN ajusta; VALIDATION informa; TEST/OOS permanece intocable hasta la
   evaluación final.
5. Si aparece una subtarea necesaria dentro del alcance, ejecutarla y añadirla
   a la bitácora; no relajar gates ni cambiar el target después de ver datos.
6. Cerrar con tests, hashes, worklog, índice, Graphify y commit selectivo.

## Estado de entregas

- A0 contrato/SDD: `PASS`.
- A1 baseline determinista y predicción Shadow: `IMPLEMENTADO`.
- A2 dataset `TRAINING_ELIGIBLE`: `BLOCKED` por evidencia OOS insuficiente del
  experimento vigente.
- A3 entrenamiento real: `WAITING` hasta A2.
- A4 Shadow MT5: `WAITING` hasta modelo congelado y calibrado.
- A5 promoción/órdenes: `FUERA DE ALCANCE`.

## Fuera de alcance

Entrenar con `data/raw/*.parquet`, mezclar MT5 y Dukascopy, modificar datasets
históricos sin contrato, backtest nuevo no preregistrado, trading, broker,
`can_trade=true` y `git push`.
