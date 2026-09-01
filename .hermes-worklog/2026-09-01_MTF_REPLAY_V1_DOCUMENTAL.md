# Cierre documental — MTF Replay Orchestrator v1

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex, CEO operativo y arquitecto de misión.
- **DEPARTAMENTO:** D1 PMO, D2 Ingeniería y D5 Assurance.
- **TAREA:** auditar lo existente y crear el pedido completo para construir el
  replay multitemporal y adaptar el visor local sin duplicar motores.

## STATUS

`COMPLETED_DOCUMENTATION / READY_FOR_IMPLEMENTATION`

Se cerró la documentación de entrada. No se implementó código ni se ejecutó
backtest científico. La siguiente acción exacta es T0 del plan ejecutable.

## Evidencia y decisiones

- Graphify confirmó las autoridades vigentes de Lifecycle, MarketState,
  SetupBuilder, Episodes, replay y outcome.
- La auditoría encontró que falta coordinación, no detección: se crea un
  orquestador consumidor en `backtest/`.
- El visor local del worktree `codex/visual-replay-wyckoff-v1-1` se reutilizará
  solo como UI. Sus proyecciones históricas no se portan.
- Se resolvió la ambigüedad temporal con un batch normativo:
  `CLOSE_BATCH → APPLY_AUTHORITY → SNAPSHOT → DECISION → EXECUTION → EMIT`.
- Se evitó hardcodear H4→M15→M5: existen perfiles versionados. El primer perfil
  ejecuta en M15; M5 entra luego como refinamiento explícito.
- Se añadió diseño streaming, deltas, chunks y resume para proteger equipos con
  memoria limitada.
- Se separaron cancelación pre-entry, invalidación post-entry y outcome.
- Graphify se actualizó localmente: 12.151 nodos, 20.059 aristas y 1.047
  comunidades; el HTML se omitió por superar su límite de 5.000 nodos.
- Engram no estuvo expuesto como herramienta en esta sesión; la decisión
  duradera queda registrada en este worklog y en el índice, pendiente de
  sincronización por el siguiente responsable durante T0.1.

## Archivos

- `docs/planificacion/AUDITORIA_COBERTURA_MTF_REPLAY_V1.md`
- `docs/contratos/CONTRATO_MTF_REPLAY_ORCHESTRATOR_V1.md`
- `docs/planificacion/SDD_MTF_REPLAY_ORCHESTRATOR_V1.md`
- `docs/planificacion/SDD_VISUAL_BACKTEST.md`
- `.hermes/plans/2026-09-01_MTF_REPLAY_ORCHESTRATOR_V1.md`
- `docs/INDICE_AUTORIDAD.md`
- `docs/00_HERMES_START_HERE.md`
- `.hermes-index.md`

## Riesgos

1. Schema 2.0 todavía no existe en código.
2. El port del visor debe auditarse archivo por archivo para no traer una
   segunda autoridad de MarketState/SetupBuilder.
3. Una corrida real requiere GO posterior, dataset/config pre-registrados y no
   puede usarse para optimizar durante la aceptación del software.
4. Los parquets y artefactos experimentales sucios preexistentes quedan fuera
   del write set y del commit de esta misión.

## Siguiente acción

Asignar D2 como director y ejecutar T0.1–T0.5. D5 debe cerrar M0 antes de que
T1 escriba el schema 2.0. No push.
