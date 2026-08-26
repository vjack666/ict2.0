# Auditoría independiente — EXP-WYCKOFF-ICT-01

**Fecha:** 2026-08-26
**Rama:** `preflight/exp-wyckoff-ict-01` (tip `cdf45f1`)
**Commits auditados:** `e9c9be9` (generador v2), `cdf45f1` (veredicto + JSON auditable)
**Dictamen final:** **`COUNTS_REPRODUCED_PROVENANCE_MISMATCH`**

## Resumen de revisores

| Revisor | Rol | Método | Resultado |
|---|---|---|---|
| R1 | Reproducción independiente | compara la reproducción limpia con el artefacto auditable | H1 TOTAL=515, conteos idénticos; procedencia `DIRTY` → BLOCKED |
| R2 | Auditoría metodología | inspecciona fuente commiteado + JSON, 6 puntos | 6/6 PASS |
| R3 | Auditoría estadística | recalcula potencia + invarianza a redistribución | 3/3 PASS |

## Criterio de salida (Orden CEO)
- La reproducción confirma H1=515 y la insuficiencia matemática (`515 < 778`).
- La procedencia del JSON auditado no es limpia (`generator_worktree=DIRTY`).
- Resultado: el conteo queda reproducido, pero la certificación final queda
  bloqueada hasta regenerar y fijar el artefacto auditable desde un checkout limpio.

## Hallazgos
1. Ancla = `nodes[k].bar`, dedup `(bar_k, direction)`, `context_bucket` relativo a
   `sequence_direction`, flag `CONFLICT` del `WyckoffSnapshot`. Correcto vs contrato.
2. Caches `ict_cache`/`wyck_cache` keyed por `bar_k` (no por dirección): internamente
   válido — el snapshot Wyckoff y `navigate(t)` son función SOLO de la barra t.
3. H1 TOTAL=515 < 778; máx celda primaria observada=361 << 389. Con total 515 es
   **imposible** llenar dos celdas a 389 cada una cualquiera sea la redistribución.
   El fallo es estructural (densidad de observaciones), no un artefacto de distribución.

## Limitaciones corregidas y pendientes

- Los revisores 2 y 3 ahora resuelven la raíz mediante `git rev-parse` y escriben
  sus resultados junto a los scripts, por lo que son ejecutables desde su ruta real.
- R1 ahora compara metadata de identidad y reporta la diferencia de procedencia;
  ya no confunde igualdad de conteos con certificación completa.
- El log `reviewer1_reproduction.log` citado por la bitácora original no está
  presente; no se trata como evidencia existente.
- Los scripts estadísticos dependen de SciPy, pero la dependencia no está fijada
  en el contrato de entorno; debe registrarse antes de cerrar la certificación.

## Salvaguardas respetadas
Sin backtest, sin IA, sin descarga/modificación de datasets, sin ampliar universo,
sin outcomes. `can_train=false`, `can_trade=false`. No se ejecutó `EXP-WYCKOFF-ICT-01`.
Fuera de alcance: bug pandas 3.0 (rama separada).

## Evidencia
`reports/audits/experiments/wyckoff_ict_01/certification/` (scripts + JSON; sin el
log de reproducción citado).
Worklog: `.hermes-worklog/2026-08-26_CERT_INDEP_PREFLIGHT_WYCKOFF_ICT_01.md`.
Engram local (proyecto `ict2.0`): dictamen guardado. Graphify fue reconstruido
después de incorporar los scripts de revisión (`9.937` nodos, `15.898`
relaciones, `892` comunidades); esto no elimina la reserva de procedencia.

## Siguiente acción (pendiente autorización CEO)
Regenerar el JSON auditable desde un checkout limpio, conservar el log y repetir
R1/R2/R3. Mantener `EXP-004B-01` como borrador: NO ejecutar sin nueva
autorización ni cálculo de potencia completo.
