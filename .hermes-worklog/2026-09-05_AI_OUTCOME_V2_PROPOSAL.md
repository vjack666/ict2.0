# Propuesta AI Outcome Classifier v2 — engine-connected retraining

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** sdd-propose (big-pickle), fase propose de la misión `ai-outcome-v2`.
- **DEPARTAMENTO:** Dirección y gobierno (D0) + PMO.
- **TAREA:** redactar la propuesta SDD para reentrenar el Outcome Classifier sobre el funnel canónico del motor, sin suplantar el baseline.

## STATUS

`COMPLETED` — propuesta creada, reruteada a la convención del repo y persistida en Engram.

## Propuesta

- **Cambio:** `ai-outcome-v2` — "Repetir el entrenamiento IA del Outcome Classifier sobre la arquitectura mejorada del motor, sin suplantar el baseline".
- **Baseline intacto:** `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_train.json` + `.jsonl` (53,761 filas, label_end_12, sha 7a6109…, accuracy 0.403, log_loss 1.090).
- **Versión nueva:** conector engine→funnel→dataset→IA con feature sets incrementales A→F y ablación.
- **Hipótesis:** H1 = las variables nuevas del motor aportan información predictiva OOS real, reproducible y causal; H0 = no aportan. Ambas falsables.
- **Métricas:** log-loss, Brier, precision/recall/F1, ROC/PR-AUC, matriz de confusión, calibration+ECE, desempeño por segmento, sample size por celda.
- **Gates:** G0–G13 definidos (provenance, snapshot, context state, lifecycle, M5/M1 causal, NULL tercer estado, funnel reproduce, FULL-vs-PREFIX, sin leakage, splits válidos, reproducible, OOS, ablation, comparación).
- **Resultados posibles:** CERTIFIED_IMPROVEMENT / NO_MEASURABLE_IMPROVEMENT / INSUFFICIENT_EVIDENCE / FAILED_CAUSALITY / FAILED_PROVENANCE / FAILED_REPRODUCIBILITY.
- **Restricciones:** can_trade=false, IA no modifica el motor, sin optimización circular, sin MT5, sin push.

## Localización

- Propuesta canónica: `.hermes/plans/2026-09-05_AI_OUTCOME_V2_PROPOSAL.md`.
- Engram: observación #712 (`sdd/ai-outcome-v2/proposal`, project ict2.0, type decision), verificada por `engram search "ai-outcome-v2"`.

## Corrección de ruteo (gatekeeper)

- La propuesta se escribió inicialmente en `openspec/changes/ai-outcome-v2/proposal.md` (ruta genérica hybrid).
- Convención del repo (sdd-init): los planes viven en `.hermes/plans/2026-*.md`; `openspec/` no se crea.
- Se copió el contenido completo a `.hermes/plans/2026-09-05_AI_OUTCOME_V2_PROPOSAL.md` y se eliminó el árbol `openspec/`.

## Evidencia

- Archivo: `.hermes/plans/2026-09-05_AI_OUTCOME_V2_PROPOSAL.md` (177 líneas).
- Engram: `#712` visible vía `engram search "ai-outcome-v2" --project ict2.0`.
- `git status`: árbol `openspec/` removido; sin push.

## RIESGOS

- Sample size de segmentos finos (celdas con <30 filas se reportan y se marcan).
- El funnel canónico del motor puede producir menos filas que el backtest (más estricto); calidad sobre cantidad.
- Provenance Dukascopy BLOCKED → DIAGNOSTIC_ONLY; no se declarará TRAINING_ELIGIBLE ni edge.
- Tri-state NULL→False: trampas conocidas en `outcome_classifier.py:139`, `wyckoff_intraday_diagnostic_train.py:112-117` y `plan.py:68`; el consumidor correcto es `daily_motor.py:410-411`.

## SIGUIENTE ACCIÓN

- Fase `spec` (sdd-spec): formalizar gates G0–G13 y criterios de aceptación como spec; luego design y apply.