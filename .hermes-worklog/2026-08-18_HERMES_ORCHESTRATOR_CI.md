# Worklog — Hermes Orchestrator CI

**Fecha:** 2026-08-18  
**Evento:** Implementación del arranque Audit-First en GitHub Actions

## Objetivo
Trasladar al repositorio la secuencia operativa de Hermes:

`AUDIT → GATE → TEST → EVIDENCIA → GOBERNANZA → siguiente fase`

con bloqueo explícito antes del backtest.

## Cambios

- Añadido `.github/workflows/hermes-orchestrator.yml`.
- El workflow ejecuta `start_hermes.py` como primer gate funcional.
- Verifica `.hermes/audit_state.json` y exige `audit_score >= 0.80` y estado aceptable.
- Ejecuta pytest únicamente después del gate de auditoría.
- Añadido artifact de evidencia de auditoría.
- Añadido gate de gobernanza que verifica la documentación normativa y mantiene el backtest bloqueado hasta A0→A9.
- Corregido `.github/workflows/hermes-tests.yml` para no depender de un `requirements.txt` inexistente; instala dependencias mínimas cuando no existe manifest.

## Límite importante

GitHub Actions por sí solo no contiene el agente Hermes local capaz de modificar código ante un fallo. Por seguridad, el runner **no inventa correcciones ni cambia criterios**. El loop de corrección real continúa siendo responsabilidad del agente Hermes conectado (`HERMES_FIX_COMMAND` local). El CI sí impide que un gate fallido se convierta en PASS y proporciona evidencia reproducible.

## Resultado

Infraestructura CI preparada para arrancar Audit-First en GitHub. Pendiente de ejecutar el workflow y registrar su resultado real antes de declarar `AUDIT-CI-01` cerrado.

## Commit

- Workflow: commit `73a89da7e205259b8137d5c83368a903dc56902c`
- Tests workflow: commit `e5793de04fd241e8a4f61c01d511ac2007c479b7`
