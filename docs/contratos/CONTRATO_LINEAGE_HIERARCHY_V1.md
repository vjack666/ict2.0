# Contrato — Lineage jerarquico causal v1

**Estado:** NORMATIVO PARA IMPLEMENTACION LOCAL  
**Fecha:** 2026-09-21  
**Commit de instalacion local:** `117c8f31`  
**Alcance:** validacion y publicacion observacional del linaje jerarquico causal; no ejecucion, no MT5, no entrenamiento, no trading.

## 1. Objetivo

El motor debe poder representar un grafo causal jerarquico de objetos ICT sin depender de proximidad temporal ni de campos sueltos. El lineage valido debe estar basado en identidad explicita:

```text
MarketObject.parent_object / related_objects -> CausalLink -> HierarchicalLineage -> daily_motor snapshot
```

Este contrato conecta el lineage ya existente en `engine/lineage.py` con el consumo observacional del motor diario mediante `engine/lineage_hierarchy.py`.

## 2. Temporalidades

La cobertura completa de esta version reconoce exactamente seis capas:

```text
D1 -> H4 -> H1 -> M15 -> M5 -> M1
```

Cuando `require_all_six_tfs=True`, un lineage basado solo en H4/M15 queda clasificado como `LINEAGE_LEGACY_UNVALIDATED`. Ese estado preserva la evidencia historica, pero no equivale a lineage jerarquico completo.

## 3. Estados normativos

`HierarchicalLineage.status` debe usar uno de estos estados:

| Estado | Significado |
|---|---|
| `LINEAGE_VALID` | Grafo resoluble, sin futuro, sin ciclos, sin huerfanos y con links validos |
| `LINEAGE_INCOMPLETE` | No hay suficiente grafo para validar |
| `LINEAGE_INVALID` | Contrato roto o cobertura insuficiente no legacy |
| `LINEAGE_ORPHAN` | Nodo no alcanzable desde raices |
| `LINEAGE_FUTURE` | Parent posterior al child por barra o timestamp |
| `LINEAGE_CYCLE` | Ciclo causal detectado |
| `LINEAGE_UNRESOLVED` | Parent o child no resoluble en la proyeccion |
| `LINEAGE_LEGACY_UNVALIDATED` | Lineage antiguo compatible, pero no jerarquico completo |

Todo estado distinto de `LINEAGE_VALID` es fail-closed para validacion de candidato.

## 4. Reglas obligatorias

1. Parent y child deben ser objetos distintos.
2. `parent_bar <= child_bar` en la misma temporalidad.
3. En cruces TF se compara timestamp causal, no indice de barra entre capas distintas.
4. No se permiten enlaces duplicados.
5. Un link solo es valido si parent y child existen en la proyeccion point-in-time.
6. Los ciclos, huerfanos, referencias no resueltas y futuros invalidan el lineage.
7. El resumen publicado debe conservar raices, hojas, profundidad, breaks, ids problematicos, conteos de relaciones y provenance por TF.
8. Ausencia de lineage no se serializa como `None`; se publica como `LINEAGE_NOT_PROVIDED`.
9. El motor diario no debe promover un candidato observable si recibe lineage explicito no validado.

## 5. Fronteras de autoridad

| Componente | Autoridad |
|---|---|
| Contrato base de link causal | `engine/lineage.py` |
| Identidad y campos padre/hijo | `engine/market_object.py` |
| Relaciones FVG/OB | `engine/relations.py` |
| Adaptador jerarquico | `engine/lineage_hierarchy.py` |
| Publicacion observacional | `engine/daily_motor.py` |
| Pruebas contractuales | `tests/test_lineage_hierarchy.py`, `tests/test_daily_motor.py` |

`engine/daily_motor.py` consume un `HierarchicalLineage` ya construido. No debe recalcular detectores ni fabricar padres faltantes.

## 6. Contrato del snapshot diario

El snapshot diario debe incluir:

```text
lineage.status
lineage.lineage_validated
lineage.roots
lineage.leaves
lineage.depth
lineage.breaks
lineage.orphan_ids
lineage.cycle_ids
lineage.future_links
lineage.unresolved_ids
lineage.temporal_violations
lineage.relation_counts
lineage.provenance_by_tf
lineage.tfs_present
lineage.six_tfs_complete
lineage_validated
candidate_status
```

Si no se entrega lineage, el snapshot publica:

```text
lineage.available=false
lineage.status=LINEAGE_NOT_PROVIDED
lineage_validated=false
```

Si se entrega lineage y `lineage_validated=false`, el candidato queda en:

```text
status=WAIT_LINEAGE_VALIDATION
candidate_status=WAIT_LINEAGE_VALIDATION
```

## 7. Evidencia de cierre

Evidencia local del commit `117c8f31`:

| Verificacion | Resultado |
|---|---|
| `python -m pytest -q tests/test_daily_motor.py tests/test_lineage_hierarchy.py` | `13 passed` |
| Grupo lineage/causalidad | `53 passed` |
| `python -m pytest -q` | `865 passed, 8 warnings` |
| `python -m py_compile engine/lineage_hierarchy.py engine/daily_motor.py tests/test_lineage_hierarchy.py tests/test_daily_motor.py` | PASS |
| `git diff --check` en archivos tocados | PASS |
| `graphify update .` | PASS; `17023 nodes`, `28497 edges`, `1406 communities` |

## 8. Fuera de alcance

- No declara edge.
- No autoriza `can_trade=true`.
- No ejecuta ordenes.
- No conecta MT5.
- No entrena GRU ni modelos.
- No fabrica cobertura M1 posterior a los datos existentes.
- No convierte H4/M15 legacy en seis TF por inferencia.

## 9. Dictamen

`LINEAGE_HIERARCHY_V1 = INSTALLED / TESTED / OBSERVE_ONLY`.

El motor ya tiene contrato y adaptador para publicar lineage jerarquico causal de seis temporalidades cuando el productor entregue los objetos y links correspondientes. La ausencia o invalidez del lineage queda visible y falla cerrado.
