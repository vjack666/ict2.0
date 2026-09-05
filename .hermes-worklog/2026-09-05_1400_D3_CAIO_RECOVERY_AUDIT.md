# 2026-09-05 — Misión D3 CAIO: RECOVERY AI OUTCOME V2 — AUDITORÍA

## ESTADO GLOBAL: **BLOCKED** (con correcciones R3 aplicadas + R4-R11 detenidas por evidencia)

## AGENTE
- Principal: D3 CAIO (runtime/ai_learning)
- Coordinado con: D2 Ingeniería, D4 Datos, D5 Assurance
- Ejecutor local: Codex/CEO operativo (aprobación: 2026-09-05)

## DEPARTAMENTO
- D3 CAIO (modelos y datos de IA)
- D2 (motor canónico, adapter)
- D4 (inventario datos)
- D5 (gates, pruebas)

## TAREA
Corregir pipeline AI Outcome V2 y realizar entrenamiento reproducible con datos locales guardados. Actualizar funnel/backtest para detectar Context State, zonas, BOS, M5/M1, abstenciones.

## RAMA Y ENTORNO
- Rama: codex/audit-hermes-cert-20260826
- Python: C:/Python314/python.exe (no .venv, roto)
- Local_Only: sí
- can_trade=false: sí
- training_eligible=false: sí
- DIAGNOSTIC_ONLY: sí
- NO PUSH: sí
- NO PROMOTION: sí

## AUDITORÍA DE PARTIDA (R0 / R1)

### Documentos leídos primero (REGLA DE ORO, antes de cualquier modificación)
- `.hermes/plans/2026-09-05_AI_OUTCOME_V2_RECOVERY.md` (plan explícito de recuperación, 8333 bytes)
- `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md` (2817 bytes; dice que entrenamiento v1 reserva Dukascopy histórico y separa MT5)
- `docs/SDD_AI_OUTCOME_V2_FINAL_REPORT.md` (5028 bytes; su propio "Revisión posterior 2026-09-05" declara: "Las declaraciones originales siguientes se conservan como historial. La revisión del código halló materialización auxiliar de una fila, comparación FULL/PREFIX no ejecutada, evaluación OOS sin predicciones, scripts de entrenamiento incompletos. Los tests unitarios no certifican G0-G13 ni las métricas declaradas. Estado: REVIEW/BLOCKED para entrenamiento verificable.")
- `docs/planificacion/SDD_MT5_OPERATIONAL_STATE_BRIDGE_V1.md`

### R1: INVENTARIO REAL (auditado, no inventado)

#### Datos raw (intactos, no modificados)
| Parquet | Bytes | SHA-256 |
|---------|-------|---------|
| EURUSD_D1 | 90347 | dd4939f05ba0a40d48a9c7bf06dc223dcdbf81ab861600b1e7446d1f1aa95f57 |
| EURUSD_H1 | 4290703 | 0fe87f1c4d36c1777f7f6710461051bbf912161aea3dd1bb3489e278a1eff957 |
| EURUSD_H4 | 457400 | 025b0c9cecdefaff09b4e74ac6f31ad1a7327c06ad84c3464f174c1e142fe269 |
| EURUSD_M1 | 91834188 | 5c20148ae3770928fbd4b3410f9f4f36a059a82f35e321a8bff456339934f89f |
| EURUSD_M15 | 2558734 | bd14262c48580855467cf7d7a5ea21171f0989e69e67400045eac7957024f15c |
| EURUSD_M3 | 1758934 | 0e2c2a6977b898edb8238c0e7ee75ad804ff4a016cccdbc21f8113b7ee5eb6a6 |
| EURUSD_M5 | 5593396 | 4c99da4c0aeab9aafdb833667ceff9533bf7a26e1a0789056396e8e6885c0b79 |

#### Cobertura cruda (de inventories locales previos; auditables con código)
| TF | Filas aprox. | Desde | Hasta |
|----|------------|------|------|
| D1 | 1.735 | 2020-01-02 | 2026-09-04 |
| H4 | 10.393 | 2020-01-02 | 2026-09-04 |
| H1 | 139.321 | 2006-01-01 | 2026-09-04 |
| M15 | 116.204 | 2022-01-02 | 2026-09-04 |
| M5 | 338.904 | 2022-01-02 | 2026-09-04 |
| M1 | 5.792.171 | 2012-01-11 | 2026-09-04 |
| M3 | (nuevo, no listado en R1 previo) | | |

Solapamiento confirmado: las 6 TF con cobertura simultánea sólo desde 2022-01-02, NO desde 2006. Esto bloquea R7 (corpus trimestral con M1/M5/HTF).

#### Datos materializados V2 (estado real)
- `data/materialized/v2/ai_outcome_v2_full.jsonl`: **120 bytes, 1 línea** (un único registro `EP-T4-REPEATED` con 4 campos auxiliares: `episode_id`, `audit_ref`, `tristate_sum_check`, `v2_profile_ref`). NO es el dataset JSONL de features/lineage que el trainer requiere. El plan RECOVERY.md ya advertía: "El materializado inspeccionado contiene un registro EP-T4-REPEATED con cuatro campos auxiliares, no el corpus de features/labels requerido por el trainer."
- Manifest: `bdb28e57d346242a01f80c930100d75875252d52e32aaba0cab5a3c79cc9e3fd` con `full_path_sha256 == prefix_path_sha256` (FULL y PREFIX son el mismo hash → no se ejecutaron separadamente). El plan RECOVERY.md ya advertía: "materializer_t4 escribe una sola secuencia de filas y copia su hash en los campos FULL y PREFIX. Esto no es una comparación causal independiente."

#### Modelos V2 (estado real)
- `data/ml/v2/V2_A_train.npz`: 1224 bytes, contiene `clf (1, 48)`, `intercept (1,)`, `n_features=48`, `n_samples=200`. **El `n_samples=200` declarado NO tiene dataset correspondiente** (materializado tiene 1 fila). Las "200 muestras" no existen en el JSONL observado. Coeficiente `clf[0,:3] = [-0.25230572, 0.1306115, 0.22784927]`, intercept = -0.30080965. **No es un entrenamiento reproducible**: el dataset subyacente no existe en disco.
- `data/ml/v2/V2_A_summary.json` declara `train_roc_auc=0.763`, `train_pr_auc=0.713`, `train_recall=0.596`, `can_trade=false`, `training_eligible=false`. Estos números son los que se reportaron en mi última respuesta, pero el plan RECOVERY.md indica que "Los valores del JSON V2_A_summary son resultados declarados, no verificados mediante comando/dataset/predicciones reproducibles en esta revisión."

#### Corpus pasados V1 (no se borraron, disponibles)
- `data/learning/choch/full/features.jsonl`: 4833 filas, V1 (11 cols planas, sin `features_at_t.engine_v2`)
- `data/learning/choch/full/labels_human.jsonl`: 2125 filas
- `data/learning/choch/full/model.joblib`: 267310 bytes
- `data/learning/choch/full/summary.json`: `n=2125, mean_human_score=55.16, class_counts={premium:0, useful:5, noise:2120}`

#### Datasets Dukascopy (separados, no MT5)
- `datasets/eurusd_dukascopy_intraday_2006_2010/`
- `datasets/eurusd_dukascopy_intraday_2011_2020/`
- `datasets/eurusd_dukascopy_intraday_2021_2025/`
- Manifiestos: `eurusd_dukascopy_intraday_2006_2020_manifest.json` (42124 bytes), `..._2021_2025_manifest.json` (14278 bytes)
- El contrato v1 reserva entrenamiento al histórico Dukascopy y separa MT5; el v2 menciona parquet operativo. Esta reconciliación está en R0/WAITING.

## R3: ADAPTER CAUSAL — CORRECCIÓN APLICADA

### Hallazgo previo (R3 READY, no verificado)
El `_prefix_frame` del adapter tenía un fallback que devolvía el frame completo si fallaba la extracción prefijo. Esto es exactamente lo que R3 prohíbe.

### Cambio aplicado
**Archivo**: `scripts/lab/experiments/ai_outcome_v2_adapter.py`

```python
# Antes
def _prefix_frame(frame, decision_time: str) -> Any:
    try:
        from engine.mt5_operational_snapshot import _frame_prefix
        return _frame_prefix(frame, decision_time)
    except Exception:
        # Fallback for testing without full engine
        return frame  # full window as placeholder

# Después
def _prefix_frame(frame, decision_time: str) -> Any:
    try:
        from engine.mt5_operational_snapshot import _frame_prefix
        return _frame_prefix(frame, decision_time)
    except Exception as exc:
        raise AdapterError(f"PREFIX causal failure: cannot build prefix for decision_time={decision_time}: {exc}") from exc
```

Además, `_default_causal_context` antes inyectaba placeholders constantes (zeros, "UNKNOWN", "SETUP") cuando el record no traía un payload V2. Eso es causalidad silenciada y viola la regla "no rellenar ni relajar criterios". Corregido para fallar cerrado:

```python
# Antes: devolvía un dict con valores constantes si faltaba features_at_t
# Después: raise AdapterError si features_at_t no es engine_v2
```

### Validación
- `grep "return frame" scripts/lab/experiments/ai_outcome_v2_adapter.py` → 0 matches (el fallback que devolvía el frame completo ya no existe).
- El adapter ahora FALLA CERRADO si no puede construir `features_at_t` causal. Esto es lo correcto: el resto del pipeline debe resolver la fuente canónica, no el adapter.

## DIAGNÓSTICO: POR QUÉ EL RESTO ESTÁ BLOCKED

Con el adapter corregido, el siguiente paso natural es invocarlo contra los funnels reales. Resultado (verificado):

```
Funnel: replay_2006_2010_h200_funnel.json
  Records: 18
  Primer record tiene features_at_t: True
  schema_group: MISSING    ← no es engine_v2
  Campos faltantes: ['lineage_depth', 'lineage_count']
```

```
Funnel: replay_2006_2010_h200_funnel_ns.json — mismo problema
Funnel: replay_2006_2010_h6_funnel.json — mismo problema
```

Esto significa que los funnels existentes son artefactos parciales de la pipeline V1/h200 (del 2026-08-31), NO de la pipeline V2/engine_v2. Por eso el manifest tiene `full_path_sha256 == prefix_path_sha256` (no son dos ejecuciones, son la misma).

### Estado por tarea (R1-R12) del plan RECOVERY
| ID | Tarea | Estado | Evidencia |
|----|-------|--------|-----------|
| R0 | Reconciliar afirmaciones de cierre V2 | **COMPLETED** (en este plan) | Identificación de materializado de 1 fila, FULL/PREFIX copiado, OOS sin predicciones, scripts de entrenamiento incompletos |
| R1 | Inventariar datos | **WORKING** | Tabla raw completa con SHA-256, cobertura real por TF, identificación del solap |
| R2 | Congelar contrato de experimento | **WAITING** | R1 todavía no entrega fuente autorizada del snapshot V2; el contrato v1 reserva Dukascopy, v2 menciona parquet operativo — pendiente reconciliar |
| R3 | Reparar adapter causal | **COMPLETED** (en este run) | `_prefix_frame` ahora falla cerrado; `_default_causal_context` no usa placeholders |
| R4 | Funnel y backtest de verificación | **WAITING** | Depende de R3 + materializador V2 (R5) + decisión R2 |
| R5 | Reconstruir materialización V2 | **WAITING** | El materializado actual tiene 1 fila auxiliar. Requiere snapshot V2 canónico (R2) antes de producir JSONL real |
| R6 | Sustituir gates superficiales | **WAITING** | FULL y PREFIX actualmente son el mismo hash; R5 los producirá separadamente |
| R7 | Ejecutar funnel/backtest por tres meses | **BLOCKED** | Cobertura simultánea M1/M5/HTF sólo desde 2022, no 2006. Primer trimestre candidato: 2022-Q1 |
| R8 | Congelar corpus y splits | **WAITING** | Depende de R5 + R7 |
| R9 | Entrenar baseline V2_A | **BLOCKED** | El .npz V2_A_train.npz actual declara 200 muestras pero el materializado tiene 1 fila. No es entrenamiento reproducible |
| R10 | Ablation A-F | **WAITING** | Depende de R9 |
| R11 | Evaluar OOS | **WAITING** | Depende de R10 + congelación |
| R12 | Auditoría y cierre | **WAITING** | Depende de R11 |

## ARCHIVOS MODIFICADOS EN ESTE RUN
- `scripts/lab/experiments/ai_outcome_v2_adapter.py`: R3 (falla cerrado en PREFIX, no usa placeholders en causal context)
- `.hermes-worklog/2026-09-05_1245_SDD_APPLY_ENTRENAMIENTO_RESULTADOS.md`: escrito en este run, ahora con la sección "HALLAZGO PRINCIPAL: DATOS PASADOS EXISTEN (y son V1, no V2)"
- `.hermes-worklog/2026-09-05_1400_D3_CAIO_RECOVERY_AUDIT.md`: este archivo

## ARCHIVOS NO MODIFICADOS (preservados)
- `data/raw/EURUSD/*.parquet`: intactos, SHA-256 verificado
- `data/learning/choch/full/`: intacto (V1 pasado)
- `datasets/eurusd_dukascopy_*`: intactos
- `engine/`: no modificado
- `.venv`: no usado
- `reports/audits/experiments/ai/*.jsonl` y `*.json`: intactos
- `.gitignore` y `.atl/*`: intactos

## RIESGOS

1. **Falsa atribución de entrenamiento**: el `.npz` V2_A tiene `n_samples=200` declarado pero el materializado tiene 1 fila. Las métricas declaradas (`ROC=0.763`, etc.) no son reproducibles porque no existe el dataset. **Esto contradice lo que reporté en mi última respuesta antes de leer el RECOVERY plan.** Corrijo aquí con evidencia.

2. **FULL==PREFIX**: el manifest actual tiene hashes idénticos para FULL y PREFIX. Esto no es una verificación causal independiente. El plan RECOVERY.md ya advertía esto.

3. **Cobertura 2006**: 2006 no tiene M5/M15/D1/H4 disponibles en el parquet local. El primer trimestre con cobertura simultánea de M1/M5/HTF es 2022-Q1. Cualquier experimento con datos 2006-2010 sólo puede usar el corpus Dukascopy histórico (v1), no la pipeline V2.

4. **Sin snapshot V2 canónico**: el motor canónico `engine/` no emite `features_at_t.engine_v2`; los funnels existentes sólo traen `features_at_t` con `schema_group=MISSING`. Construir el materializado V2 real requiere:
   - Decidir el split: Dukascopy histórico (v1) vs parquet operativo (v2 mencionado pero no implementado)
   - Crear el extractor causal en `engine/` (R3 adapter sólo lee, no escribe)
   - Resolver el target/horizonte (referencias H6, H200, label_end_12 — el plan RECOVERY.md dice: "existen referencias H6, H200 y label_end_12. No escoger después de ver métricas. Respetar el experimento aplicable.")
   - Esta decisión es de autoridad, no técnica.

5. **Tests superficiales**: el plan RECOVERY.md indica "Buscar nombres de funciones, contar dimensiones o hashear dos veces el mismo archivo no certifica G0–G13. Los 35 PASS anteriores conservan alcance unitario." Esto aplica a la suite de tests previa. No reescribo los tests en este run, pero sí marco el alcance limitado.

## SIGUIENTE ACCIÓN (a decisión de autoridad, no automática)

1. Decisión de split de datos: ¿entrenar con Dukascopy histórico (v1, disponible) o con parquet operativo MT5 (v2, no implementado)? El contrato v1 dice "El parquet operativo de MT5 no se usa para entrenar este modelo". El diseño v2 dice "parquet operativo". El plan RECOVERY.md requiere reconciliar antes de elegir.

2. Decisión de target/horizonte: ¿H6, H200, label_end_12, o label_end_6 (contrato v1)? El plan RECOVERY.md requiere congelar antes de entrenar.

3. Si se elige Dukascopy + H6 o H200: el materializado `replay_2006_2010_h6_funnel.json` y `_h200_funnel.json` ya existen como base; habría que pasarlos por el adapter corregido (R3) y documentar abstenciones.

4. Si se elige MT5: requiere construir el extractor causal en `engine/` para producir `features_at_t.engine_v2`. R3-R5 deben rehacerse desde cero.

5. Auditar las métricas declaradas en `V2_A_summary.json` con predicciones reproducibles en un test RED→GREEN. El .npz no es la verdad; los IDs de las 200 muestras y su correspondencia con el materializado son lo que falta.

## ENTREGABLE FINAL

### Estado global
**BLOCKED** (R3 aplicado, R4-R11 detenidos por evidencia objetiva)

### Tareas realizadas
- R0: Reconciliación de afirmaciones de cierre (identifiqué materializado de 1 fila, FULL==PREFIX, OOS sin predicciones, scripts incompletos)
- R1 (parcial): Inventario real de datos raw, materializados, modelos V2, funnels pasados, datasets Dukascopy
- R3: Adapter causal corregido (fallo cerrado, sin placeholders)
- Autoauditoría contra contrato v1 (no se introdujeron OTE, PnL, outcome futuro en features)
- Lectura de RECOVERY plan y alineación con él

### Comandos exactos ejecutados
- `git status --short` (mostró worktree con cambios ajenos, no tocados)
- `git branch --show-current` → `codex/audit-hermes-cert-20260826`
- `graphify query "AI Outcome V2 training funnel backtest materializer provenance"` (702 nodos)
- `sha256sum data/raw/EURUSD/*.parquet` (7 hashes)
- `wc -l data/materialized/v2/ai_outcome_v2_full.jsonl` (1 línea, 120 bytes)
- `numpy.load("data/ml/v2/V2_A_train.npz")` (clf shape (1,48), n_samples=200 declarado)
- `C:/Python314/python.exe` (interpretación del JSON de funnels: 18 records, `schema_group=MISSING`)

### Tests ejecutados
- (No se ejecutaron tests nuevos. Los 35 PASS anteriores son unitarios, no certifican G0-G13 según el plan RECOVERY.md.)

### Diferencias FULL/PREFIX
- Manifest actual: `full_path_sha256 == prefix_path_sha256` (mismo hash). NO son dos ejecuciones independientes. El plan RECOVERY.md lo documentaba y la inspección directa lo confirmó.

### Evidencia de reload del modelo
- El `.npz` V2_A es recargable (numpy lo carga), pero las "200 muestras" declaradas no existen en el materializado. El modelo no se puede reentrenar con el JSONL actual. El reload es técnicamente posible; la reproducibilidad no.

### Confirmaciones explícitas
- `can_trade=false`: confirmado (adapter mantiene False en todo AdaptedEvent, summary.json declara False)
- `training_eligible=false`: confirmado (summary.json declara False)
- `DIAGNOSTIC_ONLY`: confirmado
- `NO PUSH`: confirmado (no se ejecutó `git push`)
- `NO PROMOTION`: confirmado (B8 no promovido; RECOVERY.md marca el gate concreto como BLOCKED)

### Recomendación de autoridad
Dada la evidencia, este run NO debe cerrar con COMPLETED ni REVIEW. Cierra con **BLOCKED** hasta que la autoridad (Ruben) decida el split de datos (Dukascopy histórico vs MT5 operativo) y el target/horizonte, y hasta que se construya el extractor causal V2 en `engine/` o se reutilice el materializado Dukascopy con el adapter corregido.
