# Plan: Pipeline Científico de Aprendizaje (8 bloques + gates)

**Fecha:** 2026-08-16
**Autor:** Hermes (bajo directiva de Ruben)
**Base:** propuesta del usuario (revisión del plan original) — pipeline científico,
NO runner de tareas. Cada bloque produce RESULT -> GATE -> PASS/FAIL/INCONCLUSIVE.
Ningún bloque promociona automáticamente.

**Regla de oro:** todo lo que afirme debe contrastarse con código/evidencia del repo.
Los números de calidad se reportan tal cual, sin maquillar.

**Verificado previo (real en disco):**
- `SYM="EURUSD"` hardcode en gen_choch_dataset:38, gen_bos_dataset:33, gen_swing:20
- `train_test_split` aleatorio en train_choch_full:22 (NO walk-forward)
- nature head existe (P5, 712048b), test_bce? no: test_bce 0.559, 90% reclaim
- encoder MSE plano 0.00799
- 8 pares en data/raw/: AUDUSD EURUSD GBPUSD NZDUSD USDCAD USDCHF USDJPY XAUUSD
- NO existe data/learning/experiments/ ni pipeline/ ni manifests ni baseline

---

## ESTRUCTURA DE CARPETAS (nueva)
```
data/learning/pipeline/
├── STATE.json          # pipeline_id, current_block, current_step, status, git_commit, timestamps
├── PAUSE               # existe => detener limpio al inicio del siguiente bloque
├── RUN.lock            # pid del runner activo
├── manifests/          # dataset_id -> schema/rows/sha256/generator_commit
├── checkpoints/        # por bloque/fold: progreso parcial
├── experiments/        # BASELINE-001/, EXP-002/... con manifest+metrics+stats
└── reports/            # status/explain/why outputs
```

## BLACK BOX (3 comandos)
- `learning_pipeline.py status`  -> bloque/step/symbol/tf/model/dataset/commit/Δ vs baseline
- `learning_pipeline.py explain` -> arquitectura y componentes activos
- `learning_pipeline.py why`     -> por qué la calidad no subió (evidencia, no excusas)

---

## BLOQUE 0 — BASELINE INMUTABLE 🧊
Ejecutar EXACTAMENTE el pipeline actual (sin modificar). Guardar:
- commit, hash de código (git rev-parse), hash de datasets (sha256 de features_all)
- símbolos, TF, n muestras, distribución de labels (nature/teacher_class/label_ep)
- features usadas, train/val/test actual (split aleatorio de train_choch_full)
- ROC-AUC, PR-AUC, Brier/calibración, matriz de confusión
- métricas por período / símbolo / régimen (cuando existan)
Genera data/learning/experiments/BASELINE-001/{manifest,metrics,dataset_stats,environment}.json
**GATE 0:** baseline reproducible grabado. NO se toca el pipeline hasta aquí.

## BLOQUE 1 — AUDITORÍA DE DATASET Y LABEL 🔬
Auditar label_ep y nature (reclaim/bos_confirm/range):
- ¿qué representa? ¿usa información futura (leakage)? ¿cuánto futuro mira?
- ¿distribución cambia por símbolo / TF / año?
- stability report: N, class dist, positive rate, duplicate rate, temporal coverage
por (símbolo x año).
**GATE 1:** si label tiene leakage / inestabilidad extrema / definición incorrecta ->
NO se entrena, se corrige primero.

## BLOQUE 2 — DATASET FACTORY MULTI-PAR 🏭
8 símbolos x TF x períodos. Cada dataset = manifest inmutable:
{dataset_id, symbol, tf, period, generator_commit, feature_schema, label_schema, rows, sha256}
Reemplaza el "features_all.jsonl plano" por datasets versionados y trazables.
Multi-TF ANTES que multi-símbolo? Usuario decidió: EURUSD multi-TF + walk-forward
PRIMERO, luego expansión a 8 símbolos (aislar variables).

## BLOQUE 3 — WALK-FORWARD REAL 📈
Eliminar train_test_split para el experimento. Folds temporales:
TRAIN<=2018 VAL 2019 TEST 2020 ... hasta TEST 2026 (roll-forward anual).
Métricas prioridad: PR-AUC > ROC-AUC > Recall > Precision > F1 > Brier > base rate >
estabilidad entre folds. Guardar por fold.

## BLOQUE 4 — NATURE HEAD 🧠
Entrenar nature (confirm vs reclaim). Primero baselines: Majority / Random /
LogisticRegression / current model / nature head. Si el sofisticado no supera
baselines consistentemente -> NO se promociona. Investigar el 90% reclaim
(89-90% accuracy puede significar nada).

## BLOQUE 5 — ABLATION LAB 🧪
A=teacher, B=nature, C=context; combinaciones A/B/C/A+B/A+C/B+C/A+B+C.
Medir ΔPR-AUC, Δcalibration, Δprecision, Δrecall, ΔOOS stability.
Pregunta clave: ¿nature agrega información o repite lo que teacher ya sabía?

## BLOQUE 6 — SCORE FINAL ⚖️
NO pesos arbitrarios 0.50/0.35/0.15. Pesos seleccionados SOLO en TRAIN, congelados,
evaluados OOS. Nunca optimizar pesos mirando test.
teacher only / nature only / teacher+nature / +context.

## BLOQUE 7 — GENERALIZACIÓN Y REGÍMENES 🌎
FX majors / crosses / Gold x {Bull,Bear,Range,HighVol,LowVol}.
¿Qué tipo de mercado entiende realmente el modelo?

## BLOQUE 8 — GATE DE PRODUCCIÓN 🚦
Solo si bloques previos PASS. Nature -> Validated Score -> Bias -> Engine,
pero SHADOW MODE primero (predice, no modifica; se compara vs motor actual).
Si demuestra valor incremental: SHADOW -> CANDIDATE -> CONTRACTED -> bias_from_tools.

---

## CONTROL DE PAUSA / REANUDACIÓN
- STATE.json: current_block, current_step, last_completed_step, dataset_id,
  experiment_id, git_commit, started_at, updated_at.
- PAUSE: si existe, runner se detiene limpio al inicio del siguiente bloque
  (guarda checkpoint del bloque/fold actual).
- resume: continúa desde last_completed_step (no desde Bloque 0).
- Cada bloque corre como proceso background con notify_on_complete.

## ORDEN DE EJECUCIÓN
B0 -> G0 -> B1 -> G1 -> B2 -> B3 -> B4 -> G4 -> B5 -> B6 -> B7 -> B8(GATE prod).
Sin saltar etapas. Sin promoción automática.
