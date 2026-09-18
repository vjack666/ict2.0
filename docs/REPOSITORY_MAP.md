# Mapa profesional del repositorio

**Proyecto:** `vjack666/ict2.0`
**Rama de referencia operativa:** `entrenamiento-ia` (reconciliación en `codex/repository-order-20260918`)
**Actualizado:** 2026-09-18
**Propósito:** indicar qué contiene cada carpeta, quién tiene autoridad y qué
capas deben evolucionar juntas.

## Estado de ramas

La topología Git y la política para historias sin ancestro común se definen en
[`REPOSITORY_CANONICAL_STATE.md`](REPOSITORY_CANONICAL_STATE.md). Este mapa
describe capas del árbol activo; no autoriza merges entre historias.

## Regla de lectura

Las carpetas `agents/` y `orchestration/` son capas activas del sistema. No se
clasifican como legacy por ser fachadas o por usar compatibilidad. Los módulos
individuales solo se marcan como históricos cuando existe una implementación
posterior que los sustituye y el cambio está documentado.

## Orden de la raíz

| Orden | Ruta | Rol | Estado | Autoridad |
|---:|---|---|---|---|
| 01 | `.hermes/`, `.hermes-index.md`, `.hermes.md` | Gobierno y estado de trabajo | Activo | Contrato Hermes |
| 02 | `.hermes-worklog/` | Bitácora append-only | Activo | Evidencia de trabajo |
| 03 | `governance/` | Roles y protocolos | Activo | Gobierno operativo |
| 04 | `docs/` | Autoridad documental, contratos y tesis | Activo | [`INDICE_AUTORIDAD.md`](INDICE_AUTORIDAD.md) |
| 05 | `engine/` | Motor canónico de mercado | Activo | Fuente de verdad runtime |
| 06 | `agents/` | API pública de agentes | Activo | Contrato de agentes |
| 07 | `analysis/` | Implementación de agentes | Activo | Contratos de análisis |
| 08 | `orchestration/` | Coordinación de agentes | Activo | Contrato de orquestación |
| 09 | `detectors/` | Features por DataFrame | Activo | Contrato de features |
| 10 | `tools/` | Herramientas aisladas y aprendizaje base | Activo | Contratos de tools |
| 11 | `audits/` | Código ejecutable de auditorías | Activo | Gates científicos |
| 12 | `scripts/` | Entrypoints, laboratorio y wrappers | Activo, clasificado | Cada script declara su función |
| 13 | `backtest/` | Replay/consumidor causal aislado | Activo | Contratos de replay |
| 14 | `tests/` | Tests automatizados | Activo | Pytest local |
| 15 | `reports/` | Evidencia generada legible | Activo | Reportes publicados |
| 16 | `datasets/` | Fixtures o datasets pequeños versionados | Activo | Metadata del dataset |
| 17 | `data/` | Datos/modelos locales y artefactos pesados | Mixto/local | Inventario y manifests |
| 18 | `lab/` | Entrada lógica para experimentos | Activo | Contratos de laboratorio |
| 19 | `runtime/` | Uso diario + infraestructura IA (`runtime/ai_learning/`) | Activo | Contratos runtime/INF |

## Deuda física visible en la raíz

La raíz todavía contiene artefactos operativos/experimentales que no pertenecen
a ella. Se conservan temporalmente para no romper consumidores invisibles hasta
hacer la migración física local con búsqueda de referencias y tests.

Grupos principales:

- auditoría: `audit_*.py`, `validate_blackbox_demo.py`,
  `mc20260914_mt5_clock_verification.py`;
- entrenamiento/experimentos: `pipeline_full_cpu.py`,
  `run_ict_2006_*.py`, `smoke_displacement_cpu.py`, `smoke_single.py`;
- notebook: `kaggle_notebook_displacement.ipynb`;
- evidencias/outputs: `blackbox_demo_validation_evidence.json`,
  `displacement_results*/`;
- contratos auxiliares pendientes de consumo: `B1_DATA_MANIFEST_V1.json`,
  `schema_validate.json`.

El archivo vacío accidental `Executable` fue retirado en la segunda pasada
de ordenamiento del 2026-09-18.

Los destinos y el protocolo de migración están en
[`REPOSITORY_ORDER.md`](REPOSITORY_ORDER.md#fase-3a--higiene-física-de-la-raíz).

## Capas activas de agentes

```text
engine/ CanonicalSnapshot
    ↓
agents/ API pública estable
    ↓
analysis/ agentes ICT, Structure, Wyckoff, Decision
    ↓
orchestration/ coordinación y evidencia agregada
    ↓
daily_motor.py / briefs / laboratorio
```

`agents/` conserva imports estables como `agents.ict_agent` y
`agents.orchestrator`. `analysis/` contiene la implementación y
`orchestration/` coordina el análisis; ninguna de estas capas puede crear una
segunda autoridad de Context State o AHF.

## Documentación

| Ruta | Contenido |
|---|---|
| `docs/ict/` | Tesis ICT y libros fuente |
| `docs/reglas/` | Rulebooks machine-readable |
| `docs/contratos/` | Contratos normativos de runtime |
| `docs/planificacion/` | SDDs y arquitectura |
| `docs/tesis/` | Planes y SDD LTF/Wyckoff |
| `docs/auditoria/` | Auditorías explicativas |
| `docs/experimentos/` | Interpretación de experimentos |
| `docs/wyckoff/` | Biblioteca teórica Wyckoff |
| `docs/briefs/` | Lecturas publicadas |
| `docs/historical/` | Documentos retirados o de compatibilidad, sin autoridad normativa |

Los documentos retirados se conservan bajo `docs/historical/` con fecha y
motivo. No reciben nuevas reglas; la autoridad se declara en
`docs/INDICE_AUTORIDAD.md`.

## Laboratorio y uso diario

La separación de uso diario y laboratorio se expresa en `runtime/` y `lab/`.
Los scripts físicos siguen agrupados por función bajo `scripts/`; las rutas
antiguas se conservan solo mediante wrappers cuando un consumidor existente lo
requiere. La separación vigente es:

```text
Uso diario: engine/ → runtime/ → scripts/daily/ y scripts/presentation/
Laboratorio: lab/ → scripts/lab/ → data/learning/
```

La siguiente migración puede crear `lab/` con wrappers compatibles; no se deben
mover scripts sin actualizar imports y documentación.

## Datos y outputs

- `data/` no forma parte del árbol versionado normal; se reproduce con scripts
  de adquisición y se documenta con hashes.
- `reports/` contiene evidencia publicada y liviana.
- `graphify-out/` y `graphify-tmp/` son outputs locales ignorados.
- `.venv/` y `.pytest_cache/` son estado local y no son parte del producto.

## Inventario completo de duplicaciones y compatibilidades

Esta sección forma parte de la lista total del repositorio. Una duplicación no
se elimina por nombre: primero se determina si representa una API distinta,
una copia histórica o un output generado.

### Duplicaciones documentales no canónicas

| Elementos | Clasificación | Ruta canónica | Acción actual |
|---|---|---|---|
| `docs/historical/compatibility/CONTRATO_CONTEXT_STATE_legacy_2026-08-20.md` / `docs/contratos/CONTRATO_CONTEXT_STATE.md` | Copia histórica no normativa | `docs/contratos/CONTRATO_CONTEXT_STATE.md` | Retirada de la ruta normativa |
| `docs/historical/compatibility/DATA_INVENTARIO_legacy_2026-08-20.md` / `docs/DATA_INVENTARIO.md` | Inventarios de fases distintas | `docs/DATA_INVENTARIO.md` | Histórico fechado |
| `docs/briefs/*.md` / `docs/briefs/*.txt` | Mismo brief en dos formatos | `.md` para documentación; `.txt` para consumo plano | Mantener hasta definir consumidor único |
| Referencias a `CONTRATO_CONTEXT_STATE.md` en scripts y SDDs | Rutas históricas o relativas | `docs/contratos/...` | Las referencias activas ya fueron actualizadas |

### Duplicaciones de código intencionales

| Elementos | Por qué existen | Decisión |
|---|---|---|
| `agents/` → `analysis/` | API pública estable y reexportaciones | Mantener y actualizar |
| `agents/orchestrator.py` → `orchestration/` | Fachada pública del orquestador | Mantener y actualizar |
| `detectors/` / `engine/detectors/` | DataFrame por vela frente a `MarketObject` causal | Mantener; interfaces diferentes |
| `engine/market_structure.py` / `engine/bos/structure.py` | Fachada de compatibilidad frente a implementación estructural | Mantener hasta migración completa |
| `scripts/smoke_*` / tests | Smoke tests operativos frente a tests formales | Mantener; documentar alcance |
| `docs/wyckoff/compras/**` / `docs/wyckoff/ventas/**` | Mismo nombre para compra y venta, contenido distinto | Mantener separados por dominio |

### Código histórico o pendiente de cuarentena

| Elementos | Motivo | Estado |
|---|---|---|
| `engine/ote.py` | OTE fue eliminado de la política vigente | Retirado de ICT; copia exacta conservada en `SMC-SYSTEMS` |
| `detectors/fib.py` | Fibonacci residual | Retirado de ICT; copia exacta conservada en `SMC-SYSTEMS` |
| `engine/rr_by_setup.py` | RR legacy con referencia OTE | Retirado de ICT; copia exacta conservada en `SMC-SYSTEMS` |
| `engine/compat/htf_narrative.py` + wrapper `engine/htf_narrative.py` | Implementación narrativa anterior con consumidores activos | Compatibilidad explícita; autoridad actual en `engine/daily_motor.py` y `engine/mtf_navigation.py` |
| briefs del 15 y 19 de agosto | Generados antes de la eliminación normativa de OTE | Históricos, no autoridad actual |
| `analysis/wyckoff_agent.py` | Implementación de agente anterior al `engine/Wyckoff/` | Activo como adaptador; migración progresiva |

### Estado local fuera del árbol versionado

| Ruta | Motivo |
|---|---|
| `data/` | Parquet, JSONL y modelos grandes; ignorado por Git |
| `data/learning/` | Datasets y experimentos locales |
| `.venv/` | Entorno Python local |
| `.pytest_cache/` | Cache de tests |
| `graphify-out/` | Imágenes/HTML generados |
| `graphify-tmp/` | Temporales de visualización |

### Ramas e historial

Las ramas remotas existentes se conservan porque pueden contener trabajo no fusionado;
no son hosts de ejecución ni disparan jobs:

```text
agent/fase-a-fundaciones
agent/fase-b-domain
agent/fase-c-domain
agent/fase-c-v2
agent/fase-d-domain
docs/ltf-autonomous-spec-2026-08-20
docs/sync-plans-sdd-2026-08-20
docs/wyckoff-engine-integration-2026-08-20
main
```

No se consideran duplicaciones hasta comparar cada rama contra `main` y
confirmar que no contiene trabajo único. Su eliminación requiere una decisión
explícita, no limpieza automática.

## Regla de promoción

```text
engine → snapshot canónico → agents → orchestration → lectura/experimento
```

Un agente experimental puede producir evidencia, pero no puede sustituir el
motor canónico, modificar AHF/Context State ni autorizar ejecución.
