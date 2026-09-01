# Decisión — ejecución exclusivamente local

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo
**Departamento:** Dirección/gobierno + D7 Delivery + CRO
**Status:** `COMPLETED`

## Regla vigente

`LOCAL_ONLY` es el único modo operativo válido. Todo test, auditoría, funnel,
experimento, backtest, descarga, entrenamiento o script se ejecuta desde:

```text
C:\Users\v_jac\Desktop\ICT SYSTEM
```

No existe destino externo de ejecución. `REMOTE_EXECUTION`,
`CLOUD_EXECUTION`, `WORKFLOW_RUN`, `workflow_dispatch`, `runner` y CI no son
estados ni acciones permitidas. Solo pueden aparecer en bitácoras históricas
para describir hechos pasados.

## Evidencia

- `gh api repos/vjack666/ict2.0/actions/permissions` devuelve `enabled=false`.
- No existe `.github/workflows` en el checkout operativo.
- No existen referencias ejecutables locales a `workflow run`, `gh workflow run`
  o `workflow_dispatch`.
- Los workflows históricos de GitHub no constituyen una ruta vigente.

## Cierre

Se actualizaron `docs/EXECUTION_STRATEGY.md`,
`docs/auditoria/AUDITORIAS_ESTADO.md`, `.hermes-index.md` y
`governance/PROTOCOLO_AGENTE.md`. Las bitácoras históricas no se reescriben:
conservan hechos pasados, pero quedan subordinadas a esta política vigente.

## Aclaración del cliente

La palabra `remoto` no define ningún modo actual del proyecto. Cualquier
documento fechado antes de esta decisión que la utilice se interpreta como
registro histórico, no como instrucción, destino o autorización de ejecución.
