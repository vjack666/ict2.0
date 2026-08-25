# Cierre — Puente bidireccional Engram y cancelación OAuth

**AGENTE:** Codex, mensajero y auditor del puente
**DEPARTAMENTO:** Piso 1 Conocimiento / Operaciones Hermes
**TAREA:** Cancelar OAuth pendiente de `engram_shared` y establecer el handoff bidireccional Codex ↔ Hermes
**STATUS:** `BLOCKED` — la autorización OAuth compartida debe completarse en el navegador externo predeterminado

## EVIDENCIA

- Se identificó el proceso exacto de Hermes que ejecutaba `mcp add engram_shared --auth oauth`.
- La entrega técnica de `Ctrl+C` al console group fue rechazada por Windows; se canceló selectivamente el PID identificado.
- Verificación posterior: el proceso OAuth terminó y no quedó listener en `127.0.0.1:27890`.
- `engram_local` y `C:/Users/v_jac/.engram/engram.db` permanecen intactos; la base solo fue comprobada por existencia, no leída.
- La configuración efectiva de Hermes conserva `engram_shared` con URL remota y `auth: oauth`, sin header `Authorization` activo.
- El handoff se guardó en Engram local y en Engram compartido sin contraseñas, tokens, API keys ni datos sensibles.

## PROTOCOLO OPERATIVO

Codex actúa como mensajero bidireccional en los límites definidos por el cliente:

```text
Hermes → Engram local → Codex → Engram compartido → cliente
cliente → Engram compartido → Codex → Engram local → Hermes
```

Al iniciar y cerrar cada tarea se sincronizan decisiones, estado, bitácora, grafo,
evidencias, rama, commit, bloqueadores y siguiente acción. No se sincronizan
credenciales, secretos, API keys, contraseñas ni datos sensibles.

## ARCHIVOS Y ESTADO

- `C:/Users/v_jac/AppData/Local/hermes/config.yaml` — entrada efectiva OAuth de `engram_shared`.
- `C:/Users/v_jac/.hermes/config.yaml` — configuración de voz/local conservada sin el bloque remoto obsoleto.
- `C:/Users/v_jac/.engram/engram.db` — conservada, no leída.
- `.hermes-worklog/2026-08-25_BRIDGE_ENGRAM_BIDIRECTIONAL_OAUTH_CANCELLED.md` — esta bitácora.
- `graphify-out/` — salida local regenerable; no se versiona.

## RIESGOS Y BLOQUEADORES

- El navegador integrado no completa de forma fiable el callback local `127.0.0.1:27890`.
- No se debe copiar manualmente la URL OAuth ni probar evasiones de Cloudflare.
- `engram_shared` no se declara conectado hasta que Hermes complete OAuth en el navegador externo y `hermes mcp test engram_shared` confirme la conexión.
- El checkout contiene cambios ajenos sin commit; no se incluyen en este cierre.

## SIGUIENTE ACCIÓN

Completar el login OAuth desde el navegador externo abierto por la terminal nueva
de Hermes. Después ejecutar `hermes mcp test engram_shared`, verificar el puente
con una consulta no sensible y cerrar una nueva sincronización Codex ↔ Hermes.
