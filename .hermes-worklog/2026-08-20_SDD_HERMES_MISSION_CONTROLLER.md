# Worklog — SDD Hermes Mission Controller

**Fecha:** 2026-08-20
**Tipo:** cambio de arquitectura documental
**Estado:** SDD READY / implementación pendiente

## Objetivo

Definir Hermes como motor autónomo de ejecución de misiones, no solo como
orquestador de agentes.

## Evidencia auditada

- OpenCode SDK `1.17.11` disponible en la instalación local.
- Runtime OpenCode expone 33 agentes.
- Runtime OpenCode expone el modelo `opencode/hy3-free`.
- El repositorio contiene `start_hermes.py` como bootstrap de auditoría, no como
  Mission Controller.
- `.hermes-state/` conserva estado parcial de ejecución y blockers, pero no un
  registro durable de misiones, tareas y sesiones OpenCode.
- Engram ya existe como capa de memoria/sesiones mediante plugin OpenCode.

## Decisiones

1. No añadir Ollama ni otro runtime de modelos.
2. OpenCode es la autoridad de ejecución de agentes y providers.
3. Hermes es la autoridad de misión, estados, recuperación y terminación.
4. Engram es memoria; `.hermes-state` es estado operativo transaccional.
5. Hermes resuelve sin aprobación técnica subordinada.
6. El usuario solo interviene en objetivo, alcance, autoridad, seguridad,
   presupuesto o datos irreversibles.
7. `MISSION_COMPLETE` exige cinco predicados verificables.

## Artefactos

- `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md`
- `.hermes/plans/2026-08-20_HERMES_MISSION_CONTROLLER.md`

## Tests

No se ejecutan tests de runtime en esta fase: solo se crean contratos y plan.
La implementación deberá añadir fake adapter, tests de estados, recuperación,
reanudación y terminación.

## Resultado

**PASS documental:** la arquitectura queda suficientemente especificada para
comenzar MC-0. No se declara implementación completa.

## Siguiente acción

Ejecutar MC-0 y MC-1 en commits separados, manteniendo el estado preexistente
de `.hermes/audit_state.json` fuera de cambios no relacionados.

---

## Actualización — misión IA multi-agente por gates

**Fecha:** 2026-08-21
**Tipo:** integración del plan científico en documentos existentes
**Estado:** PLAN INTEGRADO / ejecución científica bloqueada hasta reconciliación

### Objetivo vigente

Construir y validar una IA capaz de aprender qué estructuras y secuencias ICT
contienen información predictiva real, identificar cuándo esa información deja
de ser confiable y, solo después de demostrarlo fuera de muestra y en tiempo
real, incorporarla de forma segura al sistema de trading.

### Cambios documentales realizados

- El plan existente `.hermes/plans/2026-08-20_HERMES_MISSION_CONTROLLER.md`
  conserva MC-0..MC-8 y ahora incorpora la pista científica `IA-0..IA-11`:
  auditoría de estado, PIT, datasets, B5 ablation, B6 fusion, B7
  generalización, revisión independiente, B8, shadow, seguridad y auditoría
  final.
- El SDD del Mission Controller incorpora el contrato de misión científica,
  separación de autoridad, evidencia mínima por experimento y sincronización
  de estado, worklog, índice, reports y Git.
- El SDD de producción/laboratorio mantiene explícita la frontera
  `ACTIVE_ENGINE`/`CANDIDATE_ENGINE`, la secuencia de gates y el requisito de
  `can_trade=false` antes de cualquier integración.

### Reglas de cierre añadidas

1. Un agente no certifica su propio trabajo.
2. El texto del agente no sustituye artefactos verificables.
3. Cada experimento conserva dataset hash, commit, seed, protocolo, métricas y
   veredicto.
4. `FAIL`, `INCONCLUSIVE` y `BLOCKED` permanecen visibles.
5. Cada gate actualiza este worklog, el estado de pipeline, el cuadro de Hermes,
   la matriz de experimentos y la documentación aplicable.
6. `push` no se considera autorizado por defecto; requiere autoridad explícita.

### Bloqueos y prerequisitos vigentes

- Reconciliar `data/learning/pipeline/STATE.json` con los artefactos y
  resultados B0–B4.
- Resolver el `PAUSE` activo antes de ejecutar el siguiente bloque científico.
- Completar la auditoría PIT/causalidad y la auditoría canónica de datasets.
- Resolver la reconciliación experimental actual: promoción `BLOCKED` y grupo
  B sin evidencia JSON completa.
- Mantener `GEN-000` como motor activo; no promover modelos ni señales.

### Siguiente acción verificable

Ejecutar `IA-0..IA-2` como auditoría de prerequisitos. Solo si sus gates pasan
se habilita B5; después B6/B7, revisión independiente, B8 y shadow. Esta
actualización solo cambia documentación; no ejecuta entrenamiento, no modifica
el motor activo, no crea commit y no publica en GitHub.

---

## Corrección de alcance — separación Hermes / Codex

**Fecha:** 2026-08-21
**Motivo:** instrucción explícita del usuario sobre la división de trabajo

La actualización anterior queda supersedida en lo que atribuía a Hermes la
orquestación de la pista científica completa. La frontera vigente es:

- **Hermes:** laboratorio y experimentos B0–B8; ejecuta, observa, certifica y
  documenta sus resultados.
- **Codex/equipo multiagente:** infraestructura de entrenamiento y serving,
  contratos de features ICT + Wyckoff, modelos y checkpoints, score fusion,
  confianza/abstención, OOD/drift, Shadow Mode, observabilidad e integración
  futura advisory con `bias_from_tools`.

Codex no duplica ni modifica experimentos de Hermes. Solo consume manifests y
artefactos certificados con `experiment_id`, `verdict`, `gate`, `dataset_hash`,
`code_commit`, `scope`, `metrics`, `artifact_paths`, `produced_at` y
`certifier`. Un resultado `FAIL`, `INCONCLUSIVE` o `BLOCKED` no habilita
entrenamiento ni promoción.

### Estado de implementación documental

- El plan existente conserva `MC-0..MC-8` para el controlador y ahora separa
  los gates `INF-0..INF-8` de infraestructura del carril experimental Hermes.
- El SDD del Mission Controller define el handoff certificado y la prohibición
  de ejecutar o modificar runners de Hermes.
- El SDD de producción/laboratorio formaliza la autoridad de Codex fuera del
  laboratorio y mantiene `GEN-000` como motor activo.

### Siguiente acción permitida para Codex

Trabajar en `INF-0` y `INF-1`: adaptador read-only de certificados y contrato
versionado de features/labels. No lanzar B5/B6/B7, no tocar `scripts/lab/`, no
editar datasets o JSON de Hermes y no promover señales. La primera integración
operativa permanece en `can_trade=false`.

---

## Resultado — INF-0/INF-1

**Fecha:** 2026-08-21
**Estado:** IMPLEMENTADO / TESTS PASS / LABORATORIO INTACTO

### Entrega

- `runtime/ai_learning/certified_artifacts.py`: consumidor read-only del
  handoff Hermes → Codex y contrato versionado `1.0`.
- `runtime/ai_learning/__init__.py`: API pública mínima del contrato.
- `tests/test_ai_learning_certified_manifest.py`: casos válidos, rechazo de
  verdicts no elegibles, campos inválidos, rutas inseguras, carga JSON y
  garantía de lectura sin modificación.

### Evidencia

```text
python -m pytest -q tests/test_ai_learning_certified_manifest.py
14 passed in 0.42s
```

El entorno `.venv` no pudo cargar pytest por una dependencia ausente (`pluggy`);
la verificación se ejecutó con `C:\Python314\python.exe`, que tiene pytest
funcional.

El artefacto real `reports/audits/experiments/current_batch/EXP_A1_audit.json`
fue usado solo como lectura y se rechaza por handoff incompleto. No se
modificaron `scripts/lab/`, `data/learning/pipeline/` ni
`reports/audits/experiments/`; tampoco se entrenó un modelo ni se hizo commit o
push.

### Siguiente acción

Continuar con `INF-2`: lector read-only de datasets certificados y snapshots
reproducibles, manteniendo el adaptador certificado como frontera read-only.

---

## Resultado — INF-2

**Fecha:** 2026-08-21
**Estado:** IMPLEMENTADO / TESTS PASS / LABORATORIO INTACTO

### Entrega

- `runtime/ai_learning/dataset_snapshots.py`: lector certificado, hash de
  archivo, schema fingerprint, detección de cambios y snapshot inmutable.
- `runtime/ai_learning/__init__.py`: API pública de INF-2.
- `tests/test_ai_learning_dataset_snapshots.py`: reproducibilidad, lineage y
  hash, lectura sin escritura del origen, schema drift, rutas protegidas y
  detección de alteración del snapshot.

### Evidencia

```text
C:\Python314\python.exe -m pytest -q tests/test_ai_learning_certified_manifest.py tests/test_ai_learning_dataset_snapshots.py
19 passed in 0.56s
```

La suite completa del repositorio quedó en `109 passed, 1 failed`; el fallo es
preexistente/ajeno a INF-2 en `tests/test_sequential_outcome.py`, donde falta
`sweep_high` o `sweep_low` en un nodo SWEEP. Los 19 tests de INF-0/INF-1/INF-2
pasan de forma determinista y `scripts/architecture_guard.py` devuelve PASS.

La implementación no ejecuta runners ni experimentos de Hermes y no escribe
en sus rutas protegidas. No se entrenó ningún modelo, no se creó checkpoint y
no se hizo commit ni push.

### Siguiente acción

Continuar con `INF-3`: registro de modelos y checkpoints fuera del laboratorio,
usando únicamente snapshots certificados y reproducibles.

---

## Resultado — INF-3

**Fecha:** 2026-08-21
**Estado:** IMPLEMENTADO / TESTS ESPECÍFICOS PASS / LABORATORIO INTACTO

### Entrega

- `runtime/ai_learning/model_registry.py`: registro JSON persistente de
  modelos, lineage certificado, compatibilidad modelo-dataset y recuperación.
- `runtime/ai_learning/checkpoint_store.py`: checkpoints inmutables con hash,
  publicación atómica, recuperación, reinicio y rollback.
- `runtime/ai_learning/__init__.py`: API pública de Registry y checkpoints.
- Tests específicos de persistencia, duplicados, tampering, rutas protegidas,
  metadata, compatibilidad y recuperación.

### Evidencia

```text
C:\Python314\python.exe -m pytest -q tests/test_ai_learning_certified_manifest.py tests/test_ai_learning_dataset_snapshots.py tests/test_ai_learning_model_registry.py tests/test_ai_learning_checkpoint_store.py
48 passed in 3.10s
C:\Python314\python.exe scripts/architecture_guard.py
PASS: repository architecture boundaries
```

Los agentes trabajaron en write sets separados; la integración corrigió la
detección de rutas protegidas anidadas, completó metadata de checkpoint y
añadió publicación atómica. No se ejecutaron experimentos Hermes ni se
modificaron sus rutas. No se creó commit ni se hizo push por existir cambios
concurrentes en el checkout.

### Siguiente acción

Continuar con `INF-4`: pipeline reproducible de entrenamiento, únicamente con
datasets/snapshots certificados y separación temporal train/validation/test.

---

## Resultado — INF-4..INF-8

**Fecha:** 2026-08-21
**Estado:** CONTRATOS IMPLEMENTADOS / TESTS PASS / SIN ACTIVACIÓN OPERATIVA

### Entrega por fase

- `runtime/ai_learning/training_pipeline.py`: INF-4, contrato de split
  temporal, selección sin OOS, seed/config y resume; no entrena modelos.
- `runtime/ai_learning/score_fusion.py`: INF-5, scores ICT/Wyckoff, baseline,
  pesos TRAIN-only y evaluación OOS pura.
- `runtime/ai_learning/calibration.py`: INF-6, calibración isotónica, Brier,
  reliability, error de calibración, confianza e incertidumbre.
- `runtime/ai_learning/abstention.py`: INF-7, política fail-closed
  `ACCEPT`/`REVIEW`/`ABSTAIN` y motivos auditables.
- `runtime/ai_learning/drift.py`: INF-8, dominio conocido inmutable, PSI,
  missing-rate, drift por segmento y estados NORMAL/WARNING/ABSTAIN.
- `runtime/ai_learning/__init__.py`: exports públicos integrados.

### Evidencia

```text
C:\Python314\python.exe -m pytest -q tests/test_ai_learning_certified_manifest.py tests/test_ai_learning_dataset_snapshots.py tests/test_ai_learning_model_registry.py tests/test_ai_learning_checkpoint_store.py tests/test_ai_learning_training_pipeline.py tests/test_ai_learning_score_fusion.py tests/test_ai_learning_calibration.py tests/test_ai_learning_abstention.py tests/test_ai_learning_drift.py
88 passed in 1.62s
```

No se entrenó un modelo, no se usaron datos OOS para ajustar parámetros, no se
ejecutaron experimentos Hermes y no se modificaron sus rutas. La suite global
del repositorio conserva el fallo ajeno en `tests/test_sequential_outcome.py`;
estas 88 pruebas específicas pasan.

### Siguiente acción

Continuar con INF-9: Shadow Mode, siempre con `can_trade=false`, observabilidad
read-only y comparación offline contra GEN-000.
