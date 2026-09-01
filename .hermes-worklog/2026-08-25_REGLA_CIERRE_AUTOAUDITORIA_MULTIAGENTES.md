# Bitácora — Regla de cierre, autoauditoría y dirección de misión

**Fecha:** 2026-08-25
**Agente:** Codex, CEO operativo
**Departamento:** Dirección / Gobernanza Hermes
**Tarea:** Convertir en regla permanente el cierre con bitácora, Graphify y commit local; bloquear push hasta auditoría independiente; exigir autoauditoría, autocorrección y coordinación multiagente.
**Status:** `COMPLETED` — commit local de esta misión; push no realizado.

## Decisión operativa

El encargado de cada misión actúa como director del departamento asignado. Debe coordinar el alcance, usar multiagentes en paralelo cuando las tareas sean independientes y mantener dependencias en orden lógico. Antes de declarar `COMPLETED`, debe autoauditar objetivo, contrato, SDD, gates, artefactos, documentación y estado Git; todo faltante corregible debe resolverse o complementarse en la misma misión.

## Cierre obligatorio

Al terminar una tarea autorizada se actualizan la bitácora y la documentación afectada, se reconstruye Graphify, se crea un commit local selectivo y se verifica `git status`. `git push` queda bloqueado hasta una auditoría independiente de Codex u otro auditor autorizado y una instrucción explícita de publicación.

## Archivos de autoridad actualizados

- `AGENTS.md`
- `.hermes.md`
- `governance/PROTOCOLO_AGENTE.md`
- `docs/00_HERMES_START_HERE.md`

## Evidencia

- Graphify actualizado localmente: `5.756` nodos, `9.889` relaciones y `487` comunidades.
- `graphify-out/` permanece ignorado por Git según `.gitignore`; su actualización local no se fuerza al commit.
- Se preservaron cambios previos ajenos en el checkout; solo se preparan para commit los hunks de esta regla y esta bitácora.
- No se ejecutaron experimentos, backtests, descargas ni cambios de datasets.

## Riesgos y siguiente acción

- El checkout ya contenía cambios de otras tareas; no deben incluirse en este commit.
- Auditoría independiente debe revisar este commit antes de cualquier push.
