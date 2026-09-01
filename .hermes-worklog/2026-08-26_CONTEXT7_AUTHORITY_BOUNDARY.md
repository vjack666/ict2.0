# Bitácora — Límite de autoridad de Context7

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo
**Departamento:** PMO/conocimiento + CTO/ingeniería
**Tarea:** Incorporar al plan la política de uso de Context7.
**Status:** `COMPLETED`

## Decisión

Context7 queda limitado a verificar documentación de APIs y librerías externas
contra las versiones instaladas. No tiene autoridad sobre teoría Wyckoff,
metodología científica, datos con licencia, etiquetado humano, resultados,
gates PIT/OOS ni decisiones de trading o promoción.

## Cambios

- El plan maestro incorpora la regla como principio rector.
- El SDD del ecosistema MCP incorpora el límite de autoridad y sus ejemplos
  técnicos.
- No se modificaron código, datasets, resultados ni configuración de ejecución.

## Evidencia

- `git diff --check` ejecutado tras los cambios.
- Graphify actualizado sobre el checkout operativo.

## Riesgos

La documentación de Context7 puede estar actualizada y aun así no resolver la
validez científica ni la disponibilidad/licencia de datos CME.

## Siguiente acción

Usar Context7 solo cuando una tarea técnica requiera confirmar una API o una
compatibilidad de versión; mantener las decisiones científicas dentro del SDD,
los contratos y los gates de auditoría.
