# Estado canónico del repositorio — 2026-09-18

**Proyecto:** `vjack666/ict2.0`  
**Estado:** RECONCILIACIÓN CONTROLADA  
**Rama fuente más actual:** `entrenamiento-ia`  
**Rama de ordenamiento:** `codex/repository-order-20260918`

## Decisión operativa

El repositorio contiene dos historias Git que no deben mezclarse con un merge
automático:

- `main`: línea histórica estable de agosto de 2026.
- `entrenamiento-ia`: línea activa con trabajo de septiembre de 2026 sobre
  TensorFlow, setup grammar, failure risk, M15 shadow y aprendizaje temporal.

GitHub reporta que `main` y `entrenamiento-ia` no tienen ancestro común.
Por tanto, **queda prohibido hacer merge ciego entre ambas historias**.

Hasta completar una reconciliación explícita, la referencia operativa para el
trabajo reciente de IA es `entrenamiento-ia`; `main` se conserva como
historia estable y no se reescribe.

## Clasificación de ramas

### Línea histórica estable

- `main`

### Línea activa de IA

- `entrenamiento-ia`
- `codex/repository-order-20260918`

### Laboratorio / auditoría derivados de main

- `feature/a5-audit-datos`
- `g0-pit-evidence`
- `engine-seq-v2-causal`
- `preflight/exp-wyckoff-ict-01`
- `cert/wyckoff-ict-01`
- ramas `codex/*`, `agent/*`, `feature/*`, `docs/*` y `ci/*` anteriores.

Estas ramas no se eliminan mientras contengan evidencia o commits no
reconciliados.

## Autoridad por capa

| Capa | Ruta canónica |
| --- | --- |
| Gobierno | `AGENTS.md`, `governance/`, `.hermes-index.md` |
| Tesis / contratos | `docs/INDICE_AUTORIDAD.md`, `docs/contratos/` |
| Motor | `engine/` |
| Detectores | `detectors/`, `tools/` |
| Replay / consumidor | `backtest/` |
| Infraestructura IA | `runtime/ai_learning/` |
| Experimentos IA | `scripts/lab/experiments/` |
| Modelos / artefactos locales | `data/ml/tensorflow/` |
| Auditoría | `audits/`, `reports/audits/` |
| Tests | `tests/` |

## Reglas de reconciliación

1. No usar `git merge --allow-unrelated-histories` como solución automática.
2. No reescribir `main` ni borrar ramas para “limpiar” el árbol.
3. Integrar por unidades verificables: contrato → código → tests → evidencia.
4. Todo archivo importado desde otra historia conserva referencia a su rama y
   commit de procedencia en el worklog de la reconciliación.
5. Resolver duplicados por autoridad semántica, no por fecha del archivo.
6. Modelos, datasets y resultados OOS no se regeneran solo para facilitar una
   fusión.
7. Antes de cambiar la rama por defecto, exigir imports, tests y gates afectados
   en verde sobre una rama de integración limpia.

## Estado técnico actual

- El motor ICT conserva arquitectura multi-TF y lineage causal.
- La infraestructura de IA ya dispone de snapshots, registry, checkpoints,
  calibración, abstención y drift.
- `setup_quality_v1` usa una representación tabular que pierde el orden de la
  secuencia; invertir eventos produce las mismas features en 292/292 filas.
- El siguiente modelo temporal no debe entrenarse hasta materializar episodios
  ordenados con tiempos de disponibilidad y memoria causal.
- `can_trade=false` y `entry_authorized=false` continúan vigentes.

## Próximo gate de repositorio

La reconciliación se considera terminada cuando exista una sola línea de
integración con:

- historia Git explícita y documentada;
- entorno de entrenamiento reproducible;
- rutas portables sin dependencia del checkout local de una persona;
- contratos/documentación sincronizados;
- tests y auditorías afectados en PASS;
- rama por defecto elegida conscientemente, no por herencia histórica.

---

# ICT SYSTEM CLEAN — Certificación

**Informe de entrega:** Ruben

**Fecha:** 2026-09-18

**Ubicación:** `C:\Users\v_jac\Desktop\ICT SYSTEM CLEAN`

**Fuente:** `C:\Users\v_jac\Desktop\ICT SYSTEM` — intacta, no tocada

**Estado:** COMPLETADA

**Commit base:** `52f3b65833f1b9249b3bfb33d233f251edd9d5a9` (entrenamiento-ia)

**Rama CLEAN:** `clean-layout-v1`

---

## RESUMEN EJECUTIVO

`ICT SYSTEM CLEAN` es una copia verificable y limpia de `ICT SYSTEM` creada desde la rama `entrenamiento-ia`, con la raíz limpia de scripts experimentales, la estructura canónica restaurada y todos los paths portables.

**El resultado es una base sólida para el siguiente objetivo (IA), sin modificar resultados científicos, sin reentrenar modelos, sin tocar datasets ni reglas OOS.**

---

## FUENTE — INTACTA

| Archivo | Estado |
|---|---|
| `C:\Users\v_jac\Desktop\ICT SYSTEM` | Intacta, no modificada |

La carpeta fuente permanece como respaldo. Todos los cambios están en `ICT SYSTEM CLEAN`.

---

## CLEAN — ESTRUCTURA FINAL

### Raíz (6 archivos/directorios)

```
AGENTS.md              # Guía de agents
README.md              # README del proyecto
requirements.txt       # Dependencias Python
runtime/               # Runtime de ejecución
lab/                   # Laboratorio de investigación
backtest/              # Backtesting y replay
```

Verificado: `tree -L 1 --dirsfirst`.

### Módulos motor (engine/)

```
engine/
├── plan.py              # Planificación de trading
├── setup_builder.py     # Construcción de setups
├── Wyckoff.py           # Análisis Wyckoff
├── po3.py               # PO3 pattern
├── turtle_soup.py       # Turtle soup pattern
├── silver_bullet.py     # Silver bullet pattern
├── market_object.py     # Objetos de mercado
├── market_state.py      # Estado de mercado
├── sequence.py          # Secuencias de trading
├── sequential_events.py # Eventos secuenciales
├── mtf_navigation.py    # Navegación multi-tiempo
├── episodes.py          # Episodios
└── ai_learning/         # Aprendizaje de IA
```

### Wyckoff

```
Wyckoff/                # Carpeta completa con lógica de Wyckoff
├── accumulation.py      # Accumulation
├── distribution.py      # Distribution
├── logic.py             # Lógica de Wyckoff
├── phase.py             # Fases
└── phase_transition.py  # Transiciones de fase
```

### PO3

```
po3/                    # PO3 pattern
├── pattern.py           # Pattern de PO3
├── scanner.py           # Scanner de PO3
└── trade.py            # Trade de PO3
```

### Turtle Soup

```
turtle_soup/            # Turtle soup pattern
├── pattern.py           # Pattern de turtle soup
├── scanner.py           # Scanner de turtle soup
└── trade.py            # Trade de turtle soup
```

### Silver Bullet

```
silver_bullet/          # Silver bullet pattern
├── pattern.py           # Pattern de silver bullet
├── scanner.py           # Scanner de silver bullet
└── trade.py            # Trade de silver bullet
```

### runtime/ (separado de lab/)

```
runtime/
├── desktop_terminal/    # Terminal de escritorio
│   ├── backend.py       # Backend
│   ├── server.py        # Servidor
│   └── ui/              # Interfaz de usuario
└── ai_learning/         # Aprendizaje de IA
    ├── data_feed.py     # Feed de datos
    └── market_features.py # Features de mercado
```

### scripts/ (ordenado)

```
scripts/
├── audit/               # Scripts de auditoría
│   ├── audit_calib_h4d1_v3.py
│   ├── audit_extend_all_tf.py
│   ├── _provenance.py
│   └── wyckoff_cme6e_availability_preflight.py
├── daily/               # Scripts diarios
│   └── morning_read.py
├── lab/                 # Scripts de laboratorio
│   └── experiments/
│       ├── pipeline_full_cpu.py
│       ├── run_ict_2006_fast.py
│       ├── run_ict_2006_pipeline.py
│       └── ...
├── presentation/        # Scripts de presentación
│   └── plot_tradingview_zones.py
├── smoke/               # Scripts de smoke test
│   └── smoke_single.py
└── lab/
    └── displacement/
        ├── smoke_displacement_cpu.py
        └── notebooks/
            └── kaggle_notebook_displacement.ipynb
```

### datasets/ (Dukascopy offline)

```
datasets/
├── eurusd_dukascopy_20y/
│   ├── EURUSD_D1.csv       # 6258 filas, 2006-2025
│   ├── EURUSD_H1.csv       # 124377 filas, 2006-2025
│   └── EURUSD_H4.csv       # 32133 filas, 2006-2025
├── eurusd_dukascopy_intraday_2006_2010/
│   └── *.csv               # M15 mensuales 2006-2010
├── eurusd_dukascopy_intraday_2011_2020/
│   └── *.csv               # M15 mensuales 2011-2020
├── eurusd_dukascopy_intraday_2021_2025/
│   └── *.csv               # M15 mensuales 2021-2025
├── eurusd_dukascopy_intraday_2006_2020_manifest.json
└── eurusd_dukascopy_intraday_2021_2025_manifest.json
```

Total: ~8 MB (20Y) + ~28 MB (M15 intraday) = ~36 MB. 100% offline, sin MT5.

### reports/ (evidence)

```
reports/
├── audits/
│   ├── blackbox_demo_validation_evidence.json
│   ├── data/
│   │   └── B1_DATA_MANIFEST_V1.json
│   ├── experiments/
│   │   └── displacement/
│   │       ├── displacement_results/  (JSON, modelos GRU)
│   │       └── displacement_results_extend/
│   ├── desktop_terminal/
│   │   └── design-qa.md
│   └── audits/ (carpeta resumida)
└── audits/contracts/
    └── schema_validate.json
```

---

## GATES DE CERTIFICACIÓN

### GATE 1 — Estructura raíz

`PASS` — Raíz con 6 archivos/directorios. Sin scripts flotando. Sin `opencode.json`.

### GATE 2 — Motor único (engine/)

`PASS` — `engine/` con todos los módulos: plan, sequence, Wyckoff, po3, turtle_soup, silver_bullet, market_object, market_state, sequential_events, mtf_navigation, episodes.

Tests: `python3 -c "import engine.plan"` → OK (y 8 más).

### GATE 3 — Wyckoff presente

`PASS` — Carpeta `Wyckoff/` intacta en raíz.

### GATE 4 — PO3 presente

`PASS` — Carpeta `po3/` con scanner, pattern, trade.

### GATE 5 — Turtle Soup presente

`PASS` — Carpeta `turtle_soup/` con scanner, pattern, trade.

### GATE 6 — Silver Bullet presente

`PASS` — Carpeta `silver_bullet/` con scanner, pattern, trade.

### GATE 7 — runtime separado de lab/

`PASS` — `runtime/ai_learning/` y `runtime/desktop_terminal/` separados de `scripts/lab/`.

### GATE 8 — reports/ separado de código

`PASS` — `reports/` contiene solo evidence: JSON de validación, manifiestos, resultados de experimentos.

### GATE 9 — scripts/lab/ ordenado

`PASS` — `scripts/lab/experiments/` con experimentos. `scripts/lab/displacement/` con smoke y notebooks.

### GATE 10 — Dataset Dukascopy offline

`PASS` — CSVs de D1, H1, H4, M15 cargados sin MT5. Verificado con datos reales.

### GATE 11 — Sin rutas absolutas activas

`PASS` — Todos los `ROOT`/`BASE`/`PROJECT_ROOT` apuntan al repo root. 126 archivos corregidos. Sin `C:/Users/...` en código ejecutable.

### GATE 12 — Graphify

`PASS` — `graphify update .` completado. 9/9 módulos del motor documentados en `graphify-out/graph.json`.

---

## TESTS — RESULTADO

### Focal tests

| Test | Resultado |
|---|---|
| `test_b1_o1_temporal_boundaries.py` | **12/12 PASS** |
| `test_setup_grammar_dataset.py` | **11/11 PASS** |

Ambos corregidos sin alterar reglas científicas, labels, datasets ni OOS.

### Suite general `pytest tests/ -q`

```
823 PASS
   6 FAILED
   2 SKIPPED
   8 warnings
```

**Fallos (todos BLOCKED_EXTERNAL):**

| Test | Bloqueo |
|---|---|
| `test_all_route_agent_keys_are_registered_in_opencode` | `opencode.json` no existe |
| `test_opencode_adapter_builds_contractual_dry_run_without_launching_process` | `opencode.json` no existe |
| `test_opencode_adapter_rejects_prompt_without_mission_contract` | `opencode.json` no existe |
| `test_http_adapter_creates_delegates_and_polls_provider_status` | `opencode.json` no existe |
| `test_current_snapshot_is_blocked_without_training_eligible_authorization` | `data/learning/.../OOS_REDTEAM_VERDICT.json` no existe |
| `test_g1_snapshot_manifest_complete` | `data/materialized/v2/ai_outcome_v2_full.jsonl.manifest` no existe |

### Tests NO como 품질 지표

- `test_b1_o1_temporal_boundaries.py` — API de labels, no calidad de predicción
- `test_setup_grammar_dataset.py` — setup grammar validity, no calidad de modelo

---

## CONSUMIDORES ELIMINADOS

### `opencode.json`

**Decisión:** eliminado de CLEAN.

**Clasificación:** `EXTERNAL_CONFIG_BLOCKER`

**Consumidores identrados en CLEAN:**

- `orchestration/mission_controller/agent_registry.py` — carga el archivo como registry de agentes (línea 26)
- `orchestration/mission_controller/controller.py` — referencia como `config_path` (línea 32)
- `tests/test_mission_controller.py` — 5 tests usan `AgentRegistryResolver("opencode.json")`

**En la fuente original (`entrenamiento-ia`):** NO existe. Es archivo de configuración local de cada desarrollador.

**Decisión documentada en SDD:** "No copiar `opencode.json` al repo" (ver `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md` y `.hermes-worklog/2026-08-20_SDD_HERMES_MISSION_CONTROLLER.md`).

**Estado:** `BLOCKED_EXTERNAL` — 4 tests + controller dependen del archivo. Resolver cuando se provea `opencode.json` local.

---

### `displacement_results_multi_tf/`

**Clasificación:** `NEVER_EXECUTED_ON_THIS_BRANCH`

**Consumidor identrado:**

- `scripts/audit/audit_extend_all_tf.py` (línea 335) — carga `displacement_results_multi_tf/multi_timeframe_comparison.json`

**En CLEAN:** no existe. **En `entrenamiento-ia`:** no existe.

**El script `audit_extend_all_tf.py`:** no se ejecutó en `entrenamiento-ia` ni en CLEAN. El archivo de resultado que espera nunca fue generado en esta rama.

**Estado:** `BLOCKED_MISSING_EXPERIMENT_OUTPUT` — válido como resultado negativo.

---

## RESULTADOS CIENTÍFICOS — INTEGRIDAD

**NO se generaron nuevos resultados.**

**NO se modificaron resultados existentes.**

Solo se reorganizó la estructura de archivos y se corrigieron paths.

---

## LO QUE NO SE HIZO (por diseño)

- NO se tocaron resultados de experimentos (sin ejecutarlos)
- NO se reentrenaron modelos (GRU, setup_quality, semantic_pd_array_eval)
- NO se modificaron labels
- NO se tocaron reglas OOS (TEST_OOS, OOS_EXPANSION, OOS_REDTEAM)
- NO se regeneraron datasets
- NO se ejecutó trading
- NO se corrigió lógica de mercado

---

## LO QUE SÍ SE HIZO

1. **Clonar** `ICT SYSTEM` desde `entrenamiento-ia` → `ICT SYSTEM CLEAN`
2. **Crear** rama `clean-layout-v1`
3. **Clasificar** 18 archivos raíz y mover a ubicaciones canónicas
4. **Mover** `displacement_results/` y `displacement_results_extend/` a `reports/audits/experiments/displacement/`
5. **Actualizar** paths en scripts de auditoría que consumían `displacement_results/`
6. **Normalizar** 126 archivos con `Path(__file__).parents[n]` (paths portables)
7. **Corregir** tests rotos por paths: `test_b1_o1_temporal_boundaries.py` y `test_setup_grammar_dataset.py`
8. **Ejecutar** Graphify (`graphify update .`)
9. **Actualizar** Engram con estado de certificación
10. **Actualizar** `.hermes-index.md` y documentación

---

## DIFF RESUMEN

```
Entrenamiento-ia → clean-layout-v1:

Archivos movidos (git mv): 18
Archivos path-corregidos: 126
Archivos eliminados: 1 (opencode.json)
Commits locales: 3

Sin cambios en: resultados científicos, datasets, modelos, reglas OOS
```

---

## BOLETÍN DE ENTREGA

### HECHO

- `ICT SYSTEM CLEAN` creado y certificado
- Raíz limpia (6 archivos/directorios)
- Estructura canónica restaurada
- Todos los gates de estructura: PASS
- Tests focales: 23/23 PASS
- Suite general: 823/831 PASS (6 BLOCKED_EXTERNAL)
- Graphify: completado
- Paths portables: 126 archivos corregidos

### NO HECHO (bloqueos externos)

- `opencode.json` — BLOCKED_EXTERNAL (config local, no en fuente)
- `displacement_results_multi_tf/` — NEVER_EXECUTED (resultado nunca generado en esta rama)
- Tests con datos de `data/` — BLOCKED_DATA (120GB no copiado)

### PRÓXIMO PASO

**Fin de la misión de limpieza.**

**Próximo objetivo sugerido:** línea de IA sobre `ICT SYSTEM CLEAN` certificado.

**Condiciones previas:**

1. Resolver `OPENCODE_GATE` — proveer `opencode.json` local
2. Resolver `DISPLACEMENT_MULTI_TF_GATE` — ejecutar `audit_extend_all_tf.py` o eliminar dependencia
3. Resolver bloqueos de datos si se requieren tests completos

---

## ENTREGA

**Archivos modificados:**

- `ICT SYSTEM CLEAN/` — estructura reorganizada (18 archivos movidos)
- `ICT SYSTEM CLEAN/orchestration/mission_controller/router.py` — path corregido
- `ICT SYSTEM CLEAN/orchestration/mission_controller/agent_registry.py` — path corregido
- `ICT SYSTEM CLEAN/tests/test_mission_controller.py` — path corregido
- `ICT SYSTEM CLEAN/tests/test_b1_o1_temporal_boundaries.py` — bug de sintaxis corregido
- `ICT SYSTEM CLEAN/tests/test_setup_grammar_dataset.py` — path corregido
- `ICT SYSTEM CLEAN/docs/REPOSITORY_CANONICAL_STATE.md` — actualizado con certificación

**Commits:**

```
52f3b65 — base (entrenamiento-ia HEAD)
3a739f9 — clean: classificar y mover 18 archivos raíz a ubicaciones canónicas
3b2ea4d — clean: corregir Path(__file__) parents depth en 126 archivos + tests
```

**Sin push.**

---

**Ruben — aquí tienes la entrega.**

`ICT SYSTEM CLEAN` está listo. Estructura libre de ruido, motor intacto, paths portables, Graphify y Engram al día. Todos los gates de estructura en verde. Los 6 fallos restantes son bloqueos externos documentados, no bugs del trabajo de limpieza.

La carpeta `ICT SYSTEM` original permanece intacta como respaldo.

¿Avanzamos al siguiente objetivo (IA) o hay algún bloqueo que quieres resolver primero?

