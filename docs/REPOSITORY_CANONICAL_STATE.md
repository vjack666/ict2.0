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
