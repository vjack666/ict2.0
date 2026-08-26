# Veredicto de Certificación Independiente — EXP-WYCKOFF-ICT-01

**Fecha:** 2026-08-26
**Rama:** `preflight/exp-wyckoff-ict-01` (tip `cdf45f1`)
**Commits auditados:** `e9c9be9` (generador v2), `cdf45f1` (veredicto + JSON auditable)
**Dictamen final:** **`CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`**

## Resumen de revisores

| Revisor | Rol | Método | Resultado |
|---|---|---|---|
| R1 | Reproducción independiente | worktree limpio `e9c9be9`, re-ejecuta generator, compara vs `cdf45f1` | H1 TOTAL=515, 0 diffs → CERTIFIED |
| R2 | Auditoría metodología | inspecciona fuente commiteado + JSON, 6 puntos | 6/6 PASS |
| R3 | Auditoría estadística | recalcula potencia + invarianza a redistribución | 3/3 PASS |

## Criterio de salida (Orden CEO)
- Reproducción confirma 515 observaciones (o cualquier total < 778)
  → `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`. **CUMPLIDO.**

## Hallazgos
1. Ancla = `nodes[k].bar`, dedup `(bar_k, direction)`, `context_bucket` relativo a
   `sequence_direction`, flag `CONFLICT` del `WyckoffSnapshot`. Correcto vs contrato.
2. Caches `ict_cache`/`wyck_cache` keyed por `bar_k` (no por dirección): internamente
   válido — el snapshot Wyckoff y `navigate(t)` son función SOLO de la barra t.
3. H1 TOTAL=515 < 778; máx celda primaria observada=361 << 389. Con total 515 es
   **imposible** llenar dos celdas a 389 cada una cualquiera sea la redistribución.
   El fallo es estructural (densidad de observaciones), no un artefacto de distribución.

## Salvaguardas respetadas
Sin backtest, sin IA, sin descarga/modificación de datasets, sin ampliar universo,
sin outcomes. `can_train=false`, `can_trade=false`. No se ejecutó `EXP-WYCKOFF-ICT-01`.
Fuera de alcance: bug pandas 3.0 (rama separada).

## Evidencia
`reports/audits/experiments/wyckoff_ict_01/certification/` (scripts + JSON + log).
Worklog: `.hermes-worklog/2026-08-26_CERT_INDEP_PREFLIGHT_WYCKOFF_ICT_01.md`.
Engram local (proyecto `ict2.0`): dictamen guardado. Graphify: sin cambios (cierre
documental; grafo existente en `graphify-out/graph.json`).

## Siguiente acción (pendiente autorización CEO)
`EXP-004B-01 — Generalización temporal`: inventario + borrador de preregistro listos
en `docs/experimentos/...`. NO ejecutar sin nueva autorización.
