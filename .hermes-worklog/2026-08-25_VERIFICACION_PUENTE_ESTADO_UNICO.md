# Verificación — Puente Engram, GitHub y estado único

**AGENTE:** Codex, auditor y mensajero bidireccional
**DEPARTAMENTO:** Piso 1 Conocimiento / Operaciones Hermes
**TAREA:** Probar comunicación Engram en ambos sentidos, revisar GitHub y consolidar el estado operativo
**STATUS:** `BLOCKED` — el canal local funciona; la autenticación OAuth de Hermes hacia `engram_shared` sigue pendiente

## EVIDENCIA

- **Engram local, escritura:** se guardó el handoff de control `Inicio verificacion puente Engram` en el proyecto `ict2.0`.
- **Engram local, lectura:** la búsqueda local devolvió la observación creada, confirmando el ciclo Codex → Engram local → Codex.
- **Engram compartido, escritura:** se añadió un handoff de inicio a la conversación `ICT SYSTEM — Protocolo de comunicación entre entornos`.
- **Engram compartido, lectura:** se recuperaron los handoffs y decisiones recientes de la conversación, confirmando el ciclo Codex → Engram compartido → Codex.
- **GitHub:** `origin/feature/a5-audit-datos` y `HEAD` coinciden en `46e7b4ba8316690f746763ee5582d2875b3b501a`.
- **Bitácora vigente:** `2026-08-25_BRIDGE_ENGRAM_BIDIRECTIONAL_OAUTH_CANCELLED.md` mantiene `BLOCKED` hasta completar OAuth externo.
- **Graphify:** 5.794 nodos, 9.916 relaciones, 496 comunidades; extracción 96%.
- No se ejecutaron experimentos, backtests, descargas ni operaciones sobre datasets.

## ESTADO ÚNICO

```text
Engram local Hermes       = OPERATIVO y verificado
Engram compartido Codex   = OPERATIVO para Codex y verificado
Hermes → Engram compartido = NO VERIFICADO; OAuth pendiente
GitHub rama de revisión   = SINCRONIZADA con origin
Graphify                  = ACTUALIZADO localmente
Laboratorio científico    = SIN EJECUCIÓN en esta tarea
```

La arquitectura vigente es un puente manual estructurado, no una sincronización
de bases en tiempo real. Codex traduce handoffs entre ambos almacenes y excluye
credenciales, tokens, API keys, contraseñas, transcripciones crudas y datos sensibles.

## RIESGOS Y BLOQUEADORES

- No declarar `PASS` del puente Hermes ↔ Engram compartido hasta que Hermes complete OAuth en el navegador externo y `hermes mcp test engram_shared` confirme la conexión.
- El checkout conserva cambios ajenos sin commit en datos, gráficos, briefs y `.codex/`; no se incluyen.
- La decisión científica siguiente aún pertenece al cliente y será entregada a Hermes como misión separada.

## SIGUIENTE ACCIÓN

El cliente prepara la decisión científica siguiente. Codex la recuperará desde
Engram compartido, la convertirá en un handoff seguro para Engram local y Hermes,
y verificará su rama, bitácora, gates y siguiente acción antes de cualquier ejecución.
