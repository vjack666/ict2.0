# Optimización controlada intradía Wyckoff + ICT

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex / CAIO con auditoría CRO.
- **DEPARTAMENTO:** D3 IA, D4 Datos y D5 Assurance.
- **TAREA:** buscar de forma acotada mejores perfiles e hiperparámetros sin
  utilizar TEST/OOS ni HOLDOUT para seleccionar.
- **MODO:** `LOCAL_ONLY`.

## STATUS

`DIAGNOSTIC_OPTIMIZATION_COMPLETED` — se evaluaron 12 candidatos. El candidato
`C10` fue elegido técnicamente por menor `validation.log_loss`; no es una
certificación, no demuestra edge y no autoriza trading.

## Contrato ejecutado

- Corpus fijo: `reports/audits/experiments/ai/wyckoff_intraday_2006_2010.jsonl`.
- Hash de entrada:
  `7a610960d3035282db7a0e620b66c4312c66137c1b5f52ff3badab7237da9922`.
- Rejilla congelada: 3 perfiles × 2 learning rates × 2 valores de `l2`;
  `iterations=500`, semilla `20260831`.
- TRAIN ajusta; VALIDATION selecciona; TEST/OOS solo se reporta.
- HOLDOUT 2021–2025 no fue leído.
- Commit del código: `18bb22e60bd37708e55c9e4b3014fa5750432860`.

## Candidato técnico seleccionado

- ID: `C10`.
- Perfil: `WYCKOFF_ICT_COMBINED`.
- `learning_rate=0.02`.
- `l2=0.001`.
- Validation accuracy: `0.398810`.
- Validation log-loss: `1.087424`.
- TEST/OOS diagnóstico accuracy: `0.402492`.
- TEST/OOS diagnóstico log-loss: `1.089695`.

El baseline combinado anterior tenía validation log-loss `1.087645` y TEST/OOS
log-loss `1.090112`. La mejora es marginal; el modelo no se considera con edge
ni materialmente superior hasta pasar una evaluación fuera de muestra.

## Evidencia

- Reporte JSON:
  `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_optimization_postcommit_18bb22e/optimization.json`.
- Resumen Markdown:
  `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_optimization_postcommit_18bb22e/optimization.md`.
- Hash interno del reporte:
  `0ec1bced4fc309297c1bfb1280934e56872b66d6a00cfa30b3e6c02af8545cce`.
- Artefacto C10:
  `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_optimization_postcommit_18bb22e/candidate_10_wyckoff_ict_combined_lr0.02_l20.001.json`.
- Hash interno C10:
  `a2789a4f2b8db4dc97af53e6fe4907abe77743a98a887165bc4285b8e0bd58c3`.
- Tests nuevos/focales: `10 passed`.

## Dictamen y siguiente acción

- Técnico: `PASS` para la búsqueda registrada y reproducible.
- Científico: `REVIEW`; la mejora no es material y el resultado sigue cerca
  del baseline de clase mayoritaria.
- Seguridad: `shadow_mode=true`, `can_trade=false`, sin MT5 ni órdenes.
- Provenance: `REVIEW/BLOCKED` para certificación histórica por licencia,
  adquisición y estado del worktree.

Siguiente acción: congelar C10 como candidato técnico, preparar el HOLDOUT
2021–2025 histórico separado y evaluarlo sin reajuste. Si no supera ese examen,
no se optimizan SL/TP ni se promueve el modelo.
