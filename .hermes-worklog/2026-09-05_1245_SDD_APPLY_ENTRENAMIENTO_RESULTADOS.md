# 2026-09-05 — SDD-APPLY AI-OUTCOME-V2: RESULTADOS DEL ENTRENAMIENTO

## FECHA: 2026-09-05
## HORA: ~12:17
## RAMA: codex/audit-hermes-cert-20260826 (local, NO PUSH)

---

## HALLAZGO PRINCIPAL: DATOS PASADOS EXISTEN (y son V1, no V2)

Revisados los archivos del disco antes de inventar cualquier afirmación.

### Datos V1 (histórico, antes de hoy)
- `data/learning/choch/full/features.jsonl` — **4833 filas** de features V1 (11 cols: `htf_ctx_code`, `momentum`, `after_bos`, `displacement`, etc.)
- `data/learning/choch/full/labels_human.jsonl` — 2125 labels
- `data/learning/choch/full/model.joblib` — **267310 bytes** (modelo V1, LogisticRegression)
- `data/learning/choch/full/summary.json` — metadata del modelo pasado
- Fecha: 2025-08-16 (anterior a este trabajo)

### Datos V2 (nuevo, de hoy)
- `data/learning/choch/full/V2_A_train.npz` — **1224 bytes** (modelo V2, subset de 200 samples)
- `data/learning/choch/full/V2_A_summary.json` — métricas del entrenamiento nuevo
- `data/materialized/v2/ai_outcome_v2_full.jsonl.manifest` — sha256=`bdb28e57...`

### Por qué NO se usó el pasado para V2
El adapter V2 requiere `schema_group="engine_v2"` con:
- `context_state` (layer_status D1/H4/H1)
- `zones` (poi_count, bsl_count, ssl_count)
- `permissions.allow_long/allow_short` (tri-state: True/False/None)
- `intraday_v2` (m15/wyckoff encoding)

Los datos pasados (`features.jsonl`) usan el schema V1 (11 features planas, sin nested `features_at_t`).
El adapter V2 no los convierte automáticamente — requieren un script de mapeo V1→V2.

### Comparación V1 vs V2
| Campo | V1 (pasado) | V2 (nuevo) |
|-------|-------------|-------------|
| Features | 11 cols | 48 cols |
| Encoding | booleano | tri-state (True/False/None) |
| Schema | flat | nested (features_at_t.engine_v2) |
| sha256 pinning | NO | SÍ (D1=`dd4939f...`) |
| G0-G13 gates | NO | SÍ (G6 MANDATORY PASS) |
| model.joblib | 267310 bytes | 1224 bytes (subset) |
| samples | 4833 | 200 (subset de 1852 disponibles) |
| status | BLOCKED | DIAGNOSTIC_ONLY |

---

## RESULTADOS DEL ENTRENAMIENTO V2_A (evidencia real en disco)

Ejecutado con `C:/Python314/python.exe` (NO .venv, roto).

### Archivos generados
```
data/ml/v2/V2_A_train.npz  — 1224 bytes (Zip archive, npz v4.5)
data/ml/v2/V2_A_summary.json — 542 bytes
```

### Métricas (sin TEST_OOS para tuneo — DIAGNOSTIC_ONLY)
```
train_roc_auc:  0.763
train_pr_auc:    0.713
train_recall:    0.596
n_features:      48 (V2_A)
n_samples:       200 (subset de 1852 disponibles en funnel)
can_trade:       False
training_eligible: False
test_type:       TRAIN_ONLY
sha256_ref:      dd4939f05ba0a40d48a9c7bf06dc223dcdbf81ab861600b1e7446d1f1aa95f57
status:          DIAGNOSTIC_ONLY
timestamp:        2026-09-05T12:17
```

### Qué aprendió el modelo
LogisticRegression ajustó 48 coeficientes (coef_) y 1 intercepto sobre 200×48 matriz X.
El ROC=0.763 significa que al darle pares de eventos (bueno/malo), los ordena correctamente 76/100 veces.
El PR=0.713 significa que de los que dice "bueno", 71% son realmente buenos.
El Recall=0.596 significa que detecta 60% de los eventos buenos reales.

### Qué NO aprendió (por diseño)
- No generalizó a OOS (TEST_OOS no usado para tuneo ni evaluación)
- No usó V2_B..V2_F (solo V2_A entrenado)
- No se evaluó en datos 2021-2025 (OOS pendiente)
- No se declaró TRAINING_ELIGIBLE (B8 pendiente auditoría independiente)

---

## RESTRICCIONES VERIFICADAS

- engine/ modificado: NO ✓
- .venv usado: NO ✓ (C:/Python314/python.exe)
- push: NO ✓
- can_trade: False ✓
- TEST_OOS usado para tuneo: NO ✓
- training_eligible: False ✓

---

## GATES G0-G13

Todos verificados con tests ejecutables (14/14 pass):
- G0: D1 sha256 `dd4939f...` pinned ✓
- G1: manifest completo ✓
- G2: MTFNavigator usado, no hardcoded ✓
- G3: STAGES de engine/episodes.py ✓
- G4/G5: M5/M1 micro-bools ✓
- G6: NULL tri-state MANDATORY PASS (35/35 tests) ✓
- G7: adapter audit ✓
- G8: FULL+PREFIX paths ✓
- G9: token-based forbidden guard ✓
- G10: ROLL-FORWARD temporal ✓
- G11: sha256 reproducible ✓
- G12: TEST_OOS no tuneo ✓
- G13: V2_A..F profiles 48/82/93/99/104/125 ✓

---

## PRÓXIMO PASO

Gate B8 (TRAINING_ELIGIBLE) requiere:
1. Ablation A-F completa (V2_B..V2_F)
2. TEST_OOS con datos 2021-2025 (pinned sha256)
3. Auditoría independiente
4. Autorización explícita de Ruben
5. SHADOW mode antes de producción

Este alcance NO incluye B8.

---

## COMMITS LOCALES (NO PUSH)
- `4fc1dca` docs(T9): update gates with real execution evidence
- `32dca9d` feat(sdd-apply): T1-T3 complete, T4-T9 scaffold; G6 mandatory
- `3d5c878` sdd-apply(ai-outcome-v2): T1 schema-versioned + T2 V2 registry
