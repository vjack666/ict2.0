# Bitácora — Engram como contexto obligatorio de inicio y cierre

**Fecha:** 2026-08-25
**Agente:** Codex, CEO operativo
**Departamento:** Dirección / Gobernanza Hermes
**Tarea:** Integrar Engram en el protocolo obligatorio de inicio y cierre de toda misión.
**Status:** `COMPLETED` — commit local de esta misión; push no realizado.

## Regla adoptada

Antes de comenzar una tarea, Hermes/Codex debe leer el contexto relevante de Engram y Graphify, además de la bitácora, el índice y los contratos aplicables. Al finalizar, debe actualizar Engram con el resultado verificado, decisiones, hallazgos, riesgos y siguiente acción.

## Evidencia de aplicación

- Engram consultado antes de modificar documentación: proyecto `ict2.0`, memorias de TNA, ejecución local-only y cierre con lineage.
- La regla quedó incorporada en `AGENTS.md`, `.hermes.md`, `governance/PROTOCOLO_AGENTE.md` y `docs/00_HERMES_START_HERE.md`.
- Graphify y Engram deben formar parte del cierre junto con bitácora, commit local y verificación Git.
- No se ejecutaron experimentos, backtests, descargas ni cambios de datasets.

## Control de publicación

El commit local es obligatorio; `git push` continúa bloqueado hasta auditoría independiente y autorización explícita.
