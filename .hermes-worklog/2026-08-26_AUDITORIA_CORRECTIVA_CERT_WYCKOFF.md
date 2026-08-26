# Bitácora — Auditoría correctiva de la certificación EXP-WYCKOFF-ICT-01

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo / auditor independiente
**Departamento:** CRO / assurance + CTO / ingeniería
**Tarea:** Revisar y mejorar la certificación independiente entregada por Hermes.
**Status:** `BLOCKED` — conteos reproducidos; procedencia y paquete de auditoría requieren reparación.

## Alcance

Auditoría read-only de los commits `6a653d0` y `8c7cfe3`, sus artefactos de
certificación y el borrador `EXP-004B-01`. No se ejecutó el generador, backtest,
entrenamiento, descarga ni modificación de datasets.

## Hechos verificados

- R1 corregido se ejecutó sobre artefactos existentes: H1 `515` contra `515`,
  conteos idénticos.
- R1 corregido detectó `generator_worktree=DIRTY` en el JSON auditable original;
  la reproducción independiente declara `CLEAN`.
- R2 corregido ejecuta y devuelve `6/6 PASS`.
- R3 corregido ejecuta y devuelve `3/3 PASS`; `H1=515 < 778`.
- pandas `3.0.3` y SciPy `1.18.0` están instalados localmente; SciPy no está
  fijado en `requirements.txt`.
- El archivo `reviewer1_reproduction.log` citado por Hermes no existe en el
  árbol actual.
- Graphify fue reconstruido después de incorporar los revisores: `9,937` nodos,
  `15,898` relaciones y `892` comunidades.
- El checkout contiene artefactos de certificación staged/no relacionados con
  el commit previo de pandas y cambios ajenos de mercado; no se alteraron.

## Correcciones aplicadas

- R1 compara conteos y metadata de identidad, incluidos estados de worktree, y
  distingue `COUNTS_REPRODUCED_PROVENANCE_MISMATCH` de una certificación plena.
- R2/R3 resuelven la raíz mediante `git rev-parse --show-toplevel` y escriben
  salida en su directorio real.
- El veredicto documental ya no afirma `CERTIFIED` mientras la procedencia del
  artefacto auditado sea `DIRTY`.

## Dictamen

La conclusión de insuficiencia de muestra es numéricamente sólida como resultado
reproducido, pero el paquete de certificación no puede declararse plenamente
certificado. La certificación queda bloqueada hasta regenerar el JSON auditable
desde checkout limpio, preservar el log, registrar el entorno y repetir los
revisores.

## Siguiente acción

Reparar la procedencia y ejecutar de nuevo solo la certificación. Mantener
`EXP-004B-01` en estado de borrador/no ejecutar. No entrenar IA ni ejecutar
backtest por este resultado.
