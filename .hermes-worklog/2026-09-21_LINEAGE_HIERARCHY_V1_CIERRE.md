# Bitacora — Lineage jerarquico causal v1

**Fecha:** 2026-09-21  
**Commit local:** `117c8f31 feat(lineage): enforce hierarchical lineage snapshot contract`  
**Estado:** `COMPLETED / INSTALLED / TESTED / OBSERVE_ONLY`  
**Branch:** `preservation/before-lineage-hierarchical-integration-20260921`

## Objetivo

Cerrar el trabajo iniciado por Hermes sobre la conexion de lineage jerarquico y
dejar el motor con contrato funcional, pruebas y documentacion. La mision no
autoriza trading, no conecta MT5, no entrena modelos y no declara el funnel
completo como listo para produccion.

## Cambios instalados

- `engine/lineage_hierarchy.py`: adaptador unico `HierarchicalLineage`.
- `engine/daily_motor.py`: snapshot con `lineage`, `lineage_validated` y
  `candidate_status`.
- `tests/test_lineage_hierarchy.py`: pruebas del contrato jerarquico.
- `tests/test_daily_motor.py`: pruebas de publicacion y bloqueo fail-closed.

## Contrato efectivo

La ruta nueva valida:

- parent/child distintos;
- orden causal por barra o timestamp;
- duplicados;
- ciclos;
- huerfanos;
- futuros;
- ids no resueltos;
- profundidad, raices y hojas;
- provenance por TF;
- cobertura D1/H4/H1/M15/M5/M1 cuando `require_all_six_tfs=True`.

La ausencia de lineage ya no queda como `None`: se publica
`LINEAGE_NOT_PROVIDED`. Si el motor diario recibe un lineage explicito no
validado, bloquea el candidato en `WAIT_LINEAGE_VALIDATION`.

## Evidencia

| Verificacion | Resultado |
|---|---|
| `python -m pytest -q tests/test_daily_motor.py tests/test_lineage_hierarchy.py` | `13 passed` |
| Grupo lineage/causalidad | `53 passed` |
| `python -m pytest -q` | `865 passed, 8 warnings` |
| `python -m py_compile ...` | PASS |
| `git diff --check` | PASS |
| `graphify update .` | PASS; `17023 nodes`, `28497 edges`, `1406 communities` |

Warnings observados: 8 warnings de pandas en `backtest/mechanical_bot_monthly.py`
por formato de fecha deprecated. No pertenecen a esta mision.

## Documentacion actualizada

- `docs/contratos/CONTRATO_LINEAGE_HIERARCHY_V1.md`
- `docs/FASE_D_RELACION_CAUSAL.md`
- `docs/planificacion/SDD_FVG_OB_ARCHITECTURE_MAP.md`
- `docs/contratos/CONTRATO_MT5_OPERATIONAL_SNAPSHOT_V1.md`
- `.hermes-index.md`

## Riesgos y limites

- El contrato/adaptador esta instalado, pero productores externos aun deben
  entregar objetos y links completos para que seis TF sea `LINEAGE_VALID` en
  datos reales.
- H4/M15 legacy queda preservado como evidencia historica, no promocionado.
- `can_trade=false` sigue vigente.
- No se hizo `git push`.

## Siguiente accion

Revision de Ruben/ChatGPT del commit local y de este cierre documental antes de
integrar a otra rama o abrir la fase productora de lineage completo.
