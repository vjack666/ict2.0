# SDD — Frontera entre motor activo y laboratorio

**Estado:** NORMATIVO para la misión de consolidación
**Fecha:** 2026-08-21

## Objetivo

Mantener la lectura diaria de Hermes estable mientras el laboratorio investiga
y prepara candidatos de mejora. Investigar no equivale a promocionar.

## Autoridades

| Componente | Autoridad | Regla |
|---|---|---|
| `ACTIVE_ENGINE` | Lectura diaria MT5 → engine → brief → gráficos | Solo lectura; no entrena, no emite órdenes y no se modifica durante una lectura |
| `CANDIDATE_ENGINE` | Experimentos y propuestas del laboratorio | No puede reemplazar al activo directamente |
| Hermes | Estado, misiones, evidencia, recuperación y gates | No declara éxito por texto de agente |
| Codex / equipo multiagente | Infraestructura IA fuera del laboratorio | Solo consume resultados certificados de Hermes; no ejecuta ni modifica experimentos |
| Usuario | Objetivo, SDD, protocolos y promoción | Aprueba cambios de autoridad o producción |

## Registro vigente

La frontera se declara en `runtime/engine_registry.json` y se valida mediante
`runtime/engine_registry.py`. El runtime diario debe fallar cerrado si la
política deja de ser `OBSERVE_ONLY_NO_ORDER` o si el laboratorio puede sustituir
al motor activo.

El estado actual es deliberadamente `UNPINNED_WORKTREE`: el repositorio tiene
artefactos experimentales locales sin consolidar. No se declara una versión
reproducible de producción hasta congelar código, datos y configuración.

## Reconciliación experimental

`scripts/lab/experiments/reconcile_current_experiments.py` lee exclusivamente
los JSON de auditoría en disco y produce:

- `reports/audits/experiments/current_batch/EXP_MASTER_RECONCILIATION.json`;
- `reports/audits/experiments/current_batch/EXP_MASTER_RECONCILIATION.md`.

La ausencia de un artefacto se marca `BLOCKED`. El informe no promueve señales,
parámetros ni motores.

## Promoción futura

Una promoción requiere, como mínimo, evidencia reproducible, integridad de
datos, pruebas fuera de muestra, revisión de costes, estabilidad temporal,
red-team, SDD/plan de actualización y aprobación del usuario. La versión activa
anterior se conserva y puede restaurarse.

## Misión dividida: Hermes laboratorio / Codex infraestructura

Hermes continúa exclusivamente con B0–B8 y cualquier otro experimento del
laboratorio. Codex/equipo multiagente trabaja fuera de esa pista en la
infraestructura necesaria para consumir certificados y preparar una futura IA
advisory:

```text
certificados Hermes
→ contrato ICT + Wyckoff
→ modelos/checkpoints
→ score fusion
→ probabilidad, confianza y abstención
→ OOD/drift
→ Shadow Mode y observabilidad
→ integración futura reversible
```

El handoff exige `experiment_id`, `verdict`, `gate`, `dataset_hash`,
`code_commit`, `scope`, `metrics`, `artifact_paths`, `produced_at` y
`certifier`. Codex rechaza manifests incompletos, no reescribe artefactos y no
usa `FAIL`, `INCONCLUSIVE` o `BLOCKED` como evidencia de entrenamiento.

La infraestructura no modifica runners, datasets, protocolos, resultados ni la
bitácora operativa de los experimentos de Hermes. Cada componente propio debe
registrar sus tests, configuración, checkpoint, lineage y commit en la
documentación correspondiente. La primera integración es siempre shadow con
`can_trade=false`; GEN-000 conserva la autoridad y `bias_from_tools` solo
recibe una propuesta advisory reversible después de superar todos los gates y
la aprobación del usuario.

La primera entrega de infraestructura `INF-0/INF-1` está implementada en
`runtime/ai_learning/certified_artifacts.py` con tests en
`tests/test_ai_learning_certified_manifest.py`. Su política es fail-closed:
los manifests históricos de Hermes que no cumplan el handoff no se consumen ni
se corrigen automáticamente.

La entrega `INF-2` vive en `runtime/ai_learning/dataset_snapshots.py` y usa
`tests/test_ai_learning_dataset_snapshots.py`. El lector solo acepta un
dataset incluido en `artifact_paths`, verifica que su SHA-256 coincida con el
manifest certificado y deriva un esquema determinista. El snapshot conserva
`experiment_id`, hashes, commits, configuración, timestamp, schema y origen;
su identidad estable excluye el timestamp para permitir reproducibilidad. Las
rutas protegidas del laboratorio se rechazan como destino de snapshots y los
snapshots alterados o con schema incompatible se rechazan.

La entrega `INF-3` añade `runtime/ai_learning/model_registry.py` y
`runtime/ai_learning/checkpoint_store.py`, con pruebas en
`tests/test_ai_learning_model_registry.py` y
`tests/test_ai_learning_checkpoint_store.py`. El Registry exige un snapshot
certificado y valida `model_id`, versión, commit, dataset/schema hash,
features, labels, seed y configuración. Los checkpoints se publican con hash,
metadata completa, identidad única, staging/rename atómico, recuperación y
rollback; ninguna identidad existente se sobrescribe. Las cargas vuelven a
validar integridad y compatibilidad, y las rutas Hermes siguen siendo destinos
prohibidos.

Las fases `INF-4..INF-8` cuentan ahora con contratos puros fuera del
laboratorio: `training_pipeline.py` (split temporal y resume sin entrenamiento
real), `score_fusion.py` (ICT/Wyckoff y baseline OOS), `calibration.py`
(probabilidad, Brier, reliability y confianza), `abstention.py`
(`ACCEPT`/`REVIEW`/`ABSTAIN`) y `drift.py` (dominio conocido, PSI y drift por
segmento). Sus APIs son deterministas y no conceden autoridad a la IA. INF-4
no ejecuta todavía un modelo entrenado; solo materializa el contrato que el
pipeline futuro deberá cumplir.
