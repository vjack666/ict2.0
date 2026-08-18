# Worklog — Fase D: relación causal y lineage

**Fecha:** 2026-08-18  
**Fase:** D — Relación causal  
**Estado:** `IN_PROGRESS / GATE_PENDING`

## Objetivo

Hacer explícito el lineage entre objetos del motor y demostrar por tests que ninguna relación causal puede apuntar al futuro.

## Hallazgo inicial

`engine/lineage.py` ya existía en `main` como consumidor de trazabilidad del motor. La inspección mostró que faltaba un contrato ejecutable independiente con pruebas dedicadas de temporalidad, duplicados y referencias causales.

## Trabajo realizado

Se añadió:

- `CausalLink` inmutable;
- constructor `link(parent, child, relation)`;
- `validate_links()` contra enlaces duplicados;
- validación de parent/child y tiempos;
- tests de parent futuro, timestamp futuro, `bar_index` ausente, duplicados e inmutabilidad;
- `docs/FASE_D_RELACION_CAUSAL.md` con Gate D.

## Decisión

No se modifica ejecución, scoring, aprendizaje ni obtención de M5. Fase D se limita a relación causal y seguridad temporal.

## Gate

Pendiente de GitHub Actions. No declarar PASS hasta que la suite completa pase en verde.
