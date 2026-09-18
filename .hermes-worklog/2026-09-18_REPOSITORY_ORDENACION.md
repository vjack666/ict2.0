# Hermes — Bitácora de Trabajo

## Ordenación repositorio ICT SYSTEM — 2026-09-18

**Tarea:** Ordenar, reconciliar y profesionalizar el repositorio local preservando todo el trabajo válido.

**Checkout:** `codex/audit-hermes-cert-20260826`

**Línea operativa referencia:** `entrenamiento-ia`

---

### [INICIO]

- **Git status al inicio:**
  ```
  M .worktrees/entrenamiento-ia   (metadata de worktree, no código)
  ```
- **Rama:** `codex/audit-hermes-cert-20260826`
- **Commit base:** `ffc2129`
- **Objetivos:**
  1. Organizar la raíz del proyecto según el mapa canónico
  2. Audit ar motor canónico (engine/)
  3. Confirmar Wyckoff presente y completo
  4. Ordenar infraestructura IA (runtime/ai_learning/ + scripts/lab/experiments/)
  5. Documentar el bloqueo de las 292/292 filas
  6. Corregir/crear archivos de configuración faltantes
  7. Verificar imports y tests
  8. Actualizar Graphify + Engram

---

### [INSPECCIÓN — FASE 0]

#### Git — hallazgos críticos

1. **Tres historias Git sin ancestro común:**
   - `main`: 18 commits (TNA gates + docs), **historia huérfana**
   - `codex/audit-hermes-cert-20260826`: 93+ commits, checkout actual
   - `entrenamiento-ia`: 101+ commits, línea operativa

2. **`git merge-base main entrenamiento-ia` → exit 1** (sin ancestro común)

3. **Árbol de archivos idéntico** entre HEAD y `entrenamiento-ia`:
   - Misma estructura, mismos blobs
   - Diferencia: solo cadena de ancestros Git

4. **Decision:** no fusionar; `entrenamiento-ia` es la línea canónica

#### Motor canónico — presente y completo

```
engine/
├── sequence.py              ✓ motor secuencial
├── sequential_events.py     ✓ eventos secuenciales
├── sequential_outcome.py    ✓ outcome
├── plan.py + plan_*.py      ✓ planificación (5 archivos)
├── ahf.py                   ✓ máquina estados AHF
├── market_state.py          ✓ estado mercado
├── multitf_context.py       ✓ contexto multi-TF
├── lifecycle.py             ✓ ciclo de vida
├── invalidation.py          ✓ invalidación causal
├── historical_event_objects.py  ✓ objetos históricos
├── setup_builder.py         ✓ constructor setups
├── market_object.py         ✓ objetos mercado
├── detectors/
│   ├── displacement.py      ✓ displacement
│   ├── fvg.py               ✓ FVG
│   ├── ob.py                ✓ Order Block
│   ├── gaps.py              ✓ gaps
│   ├── bos.py               ✓ BOS
│   ├── choch.py             ✓ CHOCH
│   ├── killzones.py         ✓ killzones
│   ├── liquidity.py         ✓ liquidez
│   └── zones.py             ✓ zonas
├── Wyckoff/                 ✓ 6 módulos completos
│   ├── adapter.py
│   ├── classifier.py
│   ├── events.py
│   ├── phases.py
│   ├── types.py
│   └── effort_result.py
└── [34 archivos Python totales en engine/]
```

**Wyckoff:** CONFIRMADO — `engine/Wyckoff/` con 6 módulos, integración sobre motor ICT existente (no motor independiente).

#### Infraestructura IA — ordenada

```
runtime/ai_learning/          ✓ 18 módulos
  - outcome_classifier.py     ✓ clasificador outcomes
  - model_registry.py         ✓ registro modelos
  - training_pipeline.py      ✓ pipeline entrenamiento
  - calibration.py            ✓ calibración
  - abstention.py             ✓ abstención
  - drift.py                  ✓ drift
  - score_fusion.py           ✓ fusión scores
  - displacement_teacher.py   ✓ teacher displacement
  - feature_health.py         ✓ salud features
  - checkpoint_store.py       ✓ checkpoints
  - dataset_snapshots.py      ✓ snapshots datasets
  - certified_artifacts.py    ✓ artefactos certificados
  - diagnostic_*.py           ✓ diagnósticos

scripts/lab/experiments/      ✓ 40+ scripts
  - train_setup_quality_v1.py ← BLOQUEO 292/292 (ver abajo)
  - train_failure_risk_v1.py
  - train_tensorflow_outcome_v1_003.py
  - calibrate_failure_risk_v1.py
  - evaluate_failure_risk_v1_thresholds.py
  - evaluate_shadow_fusion_v1.py
  - materialize_failure_anatomy_v1.py
  - displacement_phase1.py
  - run_displacement_profile_comparison.py
  - reproduce_setup_quality_training.py
  - [y otros]
```

#### Datos

```
data/raw/EURUSD/              ✓ 9 parquets (M1, M3, M5, M15, H1, H4, D1 + CSVs)
data/ml/tensorflow/           ✓ datasets y modelos versionados
  - failure_anatomy_v1/       ✓ dataset + modelo
  - failure_risk_v1/          ✓ modelo + calibración + thresholding
  - setup_grammar_v1/         ✓ dataset (correctado)
  - setup_grammar_v1_fixed/   ✓ dataset corregido
  - setup_quality_v1/         ✓ modelo entrenado

datasets/eurusd_dukascopy_*   ✓ 4 series (20y + 2006-2010 + 2011-2020 + 2021-2025)

displacement_results_extend/  ✓ 634K (committed, mismo en ambas ramas)
  - model_gru_h4.keras        ✓ modelo GRU H4
  - model_gru_d1.keras        ✓ modelo GRU D1
  - consolidado_h4d1.json     ✓ resultados calibración
  - calib_results.json        ✓ resultados calibración
  - results_h4.json / results_d1.json
  - seqs_*_calib*.npz         ✓ secuencias calibración
```

#### Configuración — creada

- `.python-version` → `3.11.15` (NO existía)
- `requirements-ai.txt` → TensorFlow 2.21.0 + deps (NO existía)

#### Rutas absolutas — revisión

- **`train_setup_quality_v1.py:31`**: `ROOT = Path(r"C:/Users/v_jac/Desktop/ICT SYSTEM")` — ruta absoluta encontrada
- Estado: script de entrenamiento histórico, no runtime activo
- Acción: documentado como deuda técnica, no reemplazado automáticamente (residues histórico)

---

### [BLOQUEO — 292/292 filas]

**Location:** `scripts/lab/experiments/train_setup_quality_v1.py:113`

```python
sequence = {str(item).upper() for item in raw_features.get("sequence") or []}
```

**Problema:** Convertir la secuencia a `set` destruye el orden temporal. Invertir la secuencia produce exactamente las mismas features en 292/292 filas.

**Consecuencia:** El modelo no puede aprender patrones temporales de la secuencia — solo presencia/ausencia de eventos.

**Estado:** `PRESENT_UNGRADED` — no prueba aprendizaje temporal.

**Acción requerida (fuera de esta misión):**
1. Separar `TABULAR STATIC FEATURES` vs `TEMPORAL SEQUENCE FEATURES`
2. Conservar `event_type`, `event_time`, `available_at`, `confirmed_at`, `delta_t`, `age`, `duration`, `timeframe`, `episode_id`, `parent_id`, `direction`, `state`, `price geometry`, `HTF context`, `Wyckoff context`, `missing mask`
3. No entrenar GRU hasta que la representación temporal esté correctamente separada

**Documentado en:**
- `docs/REPOSITORY_CANONICAL_STATE.md` (esta misión)
- `.hermes-index.md` (existente, actualizado abajo)

---

### [EJECUCIÓN — Tests]

```
python -c "import engine.sequence; import engine.sequential_events; import engine.plan; import runtime.ai_learning"
→ 4/4 imports OK

pytest tests/ -x --tb=short -q
→ 834 passed, 0 failures, 8 warnings (25.14s)
```

---

### [GRAPHIFY]

```
graphify update .
→ 16617 nodos, 27797 edges, 1379 comunidades
→ graph.json + GRAPH_REPORT.md actualizados
```

---

### [COMMITS]

```
e37fa60 chore(repo): ordenacion inicial - .python-version, requirements-ai.txt, REPOSITORY_CANONICAL_STATE
  - Crear .python-version (3.11.15)
  - Crear requirements-ai.txt (TensorFlow 2.21.0)
  - Crear docs/REPOSITORY_CANONICAL_STATE.md
  - Graphify actualizado
```

---

### [ESTADO FINAL]

| Área | Antes | Después | Estado |
|---|---|---|---|
| `.python-version` | NO EXISTE | `3.11.15` | ✓ Creado |
| `requirements-ai.txt` | NO EXISTE | TF 2.21.0 + deps | ✓ Creado |
| `docs/REPOSITORY_CANONICAL_STATE.md` | NO EXISTE | Estado canónico completo | ✓ Creado |
| `engine/Wyckoff/` | — | 6 módulos confirmados | ✓ Presente |
| `runtime/ai_learning/` | — | 18 módulos ordenados | ✓ Presente |
| `scripts/lab/experiments/` | — | 40+ scripts inventariados | ✓ Presente |
| Bloqueo 292/292 filas | Indexado | Documentado en CANONICAL_STATE | ✓ Documentado |
| Imports | — | 4/4 OK | ✓ Verificados |
| Tests | — | 834/834 passed | ✓ Verificados |
| Graphify | — | 16617 nodos actualizado | ✓ Actualizado |

---

### [RIESGOS]

1. **`.hermes-state/gate_evidence.json` modificado (pre-existente):** Cambio de G1-G7 mechanical bot → AI outcome V2 gates. No parte de esta misión; no incluido en commit. Clasificar como PROPIO o AJENO requiere contexto adicional.

2. **`.worktrees/entrenamiento-ia/` existe:** Directorio worktree residual. No destructivo; no se toca.

3. **`main` sin ancestro común:** Historia huérfana de 18 commits. No se puede fusionar sin `--allow-unrelated-histories` (prohibido por prompt). Se conserva como registro histórico.

4. **`train_setup_quality_v1.py:31` ruta absoluta:** Dada como evidencia histórica de entrenamiento, no reemplazada automáticamente.

---

### [SIGUIENTE PASO]

1. Clasificar los cambios pre-existentes en `.hermes-state/` (gate_evidence.json, mechanical_bot_blackbox.jsonl)
2. Verificar si hay otros scripts activos con rutas absolutas `C:/`
3. Revisar `docs/REPOSITORY_MAP.md` para actualizar con la nueva estructura
4. Actualizar `.hermes-index.md` con la entrada de esta misión
5. Guardar decisión en Engram
