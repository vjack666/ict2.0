# Repository canonical state — ICT SYSTEM
# Autoridad: rama `entrenamiento-ia` (checkout local: codex/audit-hermes-cert-20260826)
# Actualizado: 2026-09-18

## Rama canónica

- **Operativa:** `entrenamiento-ia`
- **Checkout local:** `codex/audit-hermes-cert-20260826`
- **Historia:** 101+ commits, sin ancestro común con `main`

## Rama main

- **Estado:** historia huérfana de 18 commits (TNA gates + docs Wyckoff + orden repo)
- **Uso:** registro histórico, NO línea operativa
- **Nota:** no contiene el 99% del trabajo del proyecto

## Checkout actual vs entrenamiento-ia

- El árbol de archivos es idéntico: mismos tree hashes en contenido
- Diferencia: solo la cadena de ancestros Git
- `codex/audit-hermes-cert-20260826` comparte commit final `ffc2129` con `entrenamiento-ia`
- No hay código duplicado ni faltante entre ambas

## Estructuras creadas/recuperadas

### Configuración
- `.python-version` → Python 3.11.15
- `requirements-ai.txt` → TensorFlow 2.21.0 + deps de entrenamiento

### Directorios existentes
- `engine/Wyckoff/` — 6 módulos completos (adapter, classifier, events, phases, types, effort_result)
- `runtime/ai_learning/` — 18 módulos IA (outcome_classifier, failure_risk, setup_quality, displacement, etc.)
- `scripts/lab/experiments/` — 40+ scripts de entrenamiento y auditoría
- `datasets/` — 4 series Dukascopy (20y + 2006-2010 + 2011-2020 + 2021-2025)

### Datos de entrenamiento (no versionados)
- `displacement_results_extend/` — 634K, modelos GRU + resultados calibración H4/D1
- `data/raw/EURUSD/*.parquet` — datos MT5 operativos
- `data/ml/tensorflow/` — datasets y modelos versionados por Git

### Worktree
- `.worktrees/entrenamiento-ia/` — directorio residual de worktree (existente, ignorado por Git)

## Bloqueos documentados

### 292/292 filas — features invariantes a orden inverso
- Archivo: `scripts/lab/experiments/train_setup_quality_v1.py:113`
- Hallazgo: `sequence = {str(item).upper() for item in raw_features.get("sequence") or []}`
- Efecto: convertir la secuencia a SET destruye el orden temporal
- Consecuencia: invertir la secuencia produce features idénticas en 292/292 filas
- Estado: **PRESENT_UNGRADED** — no prueba aprendizaje temporal
- Referencia: `.hermes-index.md` sección "Aprendizaje de entradas (2026-09-17)"
- Acción requerida: separar TABULAR STATIC FEATURES vs TEMPORAL SEQUENCE FEATURES
- No hay GRU entrenado para cubrir esto todavía

## Ramas clasificadas

| Rrama | Clasificación | Estado |
|---|---|---|
| `entrenamiento-ia` | CANÓNICA | Activa, línea operativa |
| `codex/audit-hermes-cert-20260826` | CERTIFICACIÓN | Checkout actual, compatible con canónica |
| `main` | HISTÓRICA | Huérfana, 18 commits, registro |
| `preflight/exp-wyckoff-ict-01` | EXPERIMENTAL | Preflight v2, FEASIBILITY_FAIL_INSUFFICIENT_N |
| `feature/*` (varias) | HISTÓRICAS | Trabajo previo, no fusionado |
| `agent/*` (varias) | HISTÓRICAS | Trabajo previo, no fusionado |
| `cert/*` | AUDITORÍA | Certificaciones previas |
| `reconcile/tna-canonical-sci` | EXPERIMENTAL | Reconciliación TNA |
| `backup-before-filter-20260915` | HISTÓRICA | Backup pre-filtro |
| `codex/pandas3-exp-seq-ctx-20260826` | EXPERIMENTAL | Pandas 3 compatibilidad |
| `codex/tna-*` | EVIDENCIA | Gates TNA |
| `codex/visual-replay-wyckoff-v1-1-20260826` | COMPATIBILIDAD | Visor worktree, no autoridad engine |

## Próximo paso

Ejecutar inventario del motor canónico (`engine/sequence`, `engine/sequential_events`, `engine/plan`, `engine/context`, `engine/ahf`, `engine/mtf_*`) y verificar imports + tests focales.
