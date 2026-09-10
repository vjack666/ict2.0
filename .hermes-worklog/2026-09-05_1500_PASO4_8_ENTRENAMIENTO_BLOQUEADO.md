# 2026-09-05 — PASO 4/5/6/7/8 — MATERIALIZACIÓN V2 + VENTANA + ENTRENAMIENTO

## ESTADO: BLOCKED_INSUFFICIENT_CLASS_SUPPORT / BLOCKED_PENDIENTE_EXTRAER_Datos

## AUTORIZACIÓN USADA (defaults provisionales, no promoción)
- Fuente: Dukascopy histórico local (`datasets/eurusd_dukascopy_intraday_2006_2010/` etc.)
- Target: label_end_6 (contrato V1 vigente)
- Clases: continuation, reversal, failure
- Split: 60/20/20 cronológico
- Modelo seleccionado con VALIDATION; TEST_OOS una vez
- DIAGNOSTIC_ONLY = True; can_trade = False; shadow_mode = True; NO PUSH

## PASO 4 — MATERIALIZACIÓN V2 REAL (intentado; bloqueado por fuente)

Intento de construir `dataset.jsonl` con `features_at_t.engine_v2`:

- El adapter corregido (R3) rechaza cualquier record sin `schema_group="engine_v2"`.
- Los funnels locales (`replay_2006_2010_h200_funnel.json`) traen `features_at_t` con `schema_group=MISSING`. No son V2.
- El dataset Dukascopy (`EURUSD_M15_2006.csv.csv`) es CSV histórico M15, NO JSONL con estructura V2.
- El materializador existente (`materializer_t4.py`) generó 1 fila (`EP-T4-REPEATED`, 121 bytes) con datos auxiliares, no el corpus de 200 samples requeridos.
- **Con resultado**: no se puede producir `dataset.jsonl` real sin primero extraer `context_state`, `zones`, `M5/M1`, `permissions` del CSV Dukascopy con el extractor V2 (no implementado en `engine/` y no autorizado modificar `engine/`).

Artefacto generado (intento, NO promoción):
- `scripts/lab/experiments/v2_extractor_local.py` (extractor con validación tri-state, rechazo de campos prohibidos, fallos cerrados)
- `scripts/lab/experiments/full_prefix_audit.py` (auditoría FULL/PREFIX: confirma hash igual; NO independiente)

**Estado**: materializado V2 REAL = BLOCKED. No invento datos. El archivo `data/materialized/v2/ai_outcome_v2_full.jsonl` NO fue reemplazado ni extendido artificialmente.

## PASO 5 — VENTANA TRES MESES (seleccionada, documentada, NO oculta bloqueos)

Según el inventario R1 (`.hermes/plans/2026-09-05_AI_OUTCOME_V2_RECOVERY.md`, tabla de inventario):

- Cobertura conjunta M1/M5/H4/H1/D1: solo desde **2022-01-02**.
- 2006-2010 (Dukascopy) tiene M15/M1/H1, NO M5/M15/H4/D1 simultáneamente.
- **Ventana autorizada** (primera contigua con cobertura completa): **2022-Q1 (2022-01-01 a 2022-03-31)**.
- Si se quiere incluir 2006-2010, debe documentarse como bloque parcial (falta M5/H4/D1) y no ocultarse.

Artefacto: documento en bitácora `.hermes-worklog/2026-09-05_1400_D3_CAIO_RECOVERY_AUDIT.md` (líneas 42-50).

**Estado**: ventana seleccionada y documentada. El entrenamiento real requiere los datos de 2022-Q1 en formato V2; aún no disponibles.

## PASO 6 — ENTRENAMIENTO REAL (NO ejecutado — bloqueado por paso 4/5)

No se creó `tests/test_train_v2_real.py`, no se generó `data/ml/v2/*.npz` con dataset real, no se usó `C:/Python314/python.exe -m sklearn` con datos reales. El archivo `scripts/lab/learning/train_v2_full_run.py` (stub 9 líneas) NO fue reemplazado por entrenamiento real.

Confirmación: `data/ml/v2/` contiene solo `V2_A_train.npz` (1224 bytes, n_samples=200 declarado, sin datos de respaldo) y `V2_A_summary.json` (métricas declaradas, no verificadas con dataset reemplazado).

**Estado**: ENTRENAMIENTO = BLOCKED (falta materializado real + dataset 2022-Q1 en V2 + apoyo de clase). No se declara PASS.

## PASO 7 — ABLACIÓN A-F (NO ejecutado — depende del paso 6)

No se ejecutó. No hay `data/ml/v2/V2_B*.npz`, etc. El stub `ablation_t7.py` existe pero no corre con datos reales.

**Estado**: BLOCKED (espera paso 6).

## PASO 8 — EVALUACIÓN OOS (NO ejecutada)

No hay predicciones reales (`predictions.jsonl` no creado). El `test_gates_v2_evidence.py` (14/14 PASS) es test de verificación de código, NO evaluación de modelo.

**Estado**: BLOCKED (espera paso 6 + 7).

## REGLAS CUMPLIDAS (verificadas con código)

- `can_trade=false`: confirmado (adapter mantiene False; `.npz` no modifica; `v2_extractor_local.py` fija `CAN_TRADE = False`)
- `training_eligible=false`: confirmado (no promovido; `summary.json` mantiene False; contrato V1 requiere auditoría independiente + `PASS` de B8)
- `shadow_mode=true`: confirmado (`SHADOW_MODE = True` en extractor)
- `DIAGNOSTIC_ONLY`: confirmado (documento de bitácora declara explícito)
- `LOCAL_ONLY`: confirmado (`C:/Python314/python.exe`, no `.venv`, no descarga)
- `NO PUSH`: confirmado (commit `8bea0f5` es local, no se hizo `git push`)
- `NO PROMOTION`: confirmado (estado `BLOCKED_INSUFFICIENT_CLASS_SUPPORT` / `BLOCKED_PENDIENTE_EXTRAER_Datos`)
- `engine/` NO modificado: confirmado (`git status` no muestra cambios en `engine/`)
- Datos raw preservados: confirmado (SHA-256 de 7 parquets sin cambio)
- No invento labels/features/metrics: confirmado (no se creó `.npz` con datos inventados; no se extendió materializado con filas falsas)

## BLOQUEO EXTERNO / AUTORIDAD REQUERIDA

No hay ausencia de datos locales: los datos Dukascopy locales existen (`datasets/eurusd_dukascopy_intraday_2006_2010/`), y el parquet `EURUSD_M1.parquet` (91MB) está disponible. El bloqueo NO es de archivos faltantes; es de **transformación V1→V2** que requiere:

1. Extraer `features_at_t.engine_v2` del CSV Dukascopy (no implementado en `engine/` y no autorizado modificar `engine/` sin autorización explícita del contrato).
2. Aplicar tri-state (`True/False/None`), zones (`poi_count`, `bsl_count`), M5/M1 y lineage observados en `decision_time`.
3. Documentar la ventana 2022-Q1 como el primer trimestre con cobertura conjunta.

Este bloqueo ES resoluble (el archivo CSV existe, el extractor V2 está creado en `scripts/` con reglas de validación, la ventana está seleccionada), PERO requiere una decisión de autoridad sobre si se construye el extractor usando los datos Dukascopy (como permite `SOURCE_AUTHORIZED`) o si se espera a que el motor canónico (`engine/`) genere los snapshots V2 (que es el diseño, pero toma más tiempo y requiere autorización).

## MEMORIAL (para autor/autoridad)

Generado `docs/briefs/brief_2026-09-05.md` y `.txt` para el cierre parcial.

Archivo creado: `.hermes-worklog/2026-09-05_1400_D3_CAIO_RECOVERY_AUDIT.md` (16.270 bytes) ya cubre R3-R7. Este archivo (PASO 4-8) completa la evidencia de lo que se intentó y por qué se detuvo.

Commit local: `8bea0f5` (5 archivos: adapter + bitácoras + index + extractor + audit FULL/PREFIX).

Estado entregado: `BLOCKED_PENDIENTE_EXTRAER_Datos` (los datos locales existen, pero la transformación al formato V2 requiere paso de extracción que puede ser realizado por el usuario/autoridad con el extractor creado).
