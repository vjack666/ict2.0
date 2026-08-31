# Plan operativo — Puente de estado operativo MT5 v1

**Owner:** Codex/CEO operativo
**Departamentos:** D2 Ingeniería, D4 Datos, D5 Assurance, D1 Documentación,
D7 Delivery
**Modo:** LOCAL_ONLY
**Contrato:** `docs/contratos/CONTRATO_MT5_OPERATIONAL_SNAPSHOT_V1.md`
**SDD:** `docs/planificacion/SDD_MT5_OPERATIONAL_STATE_BRIDGE_V1.md`

## Objetivo

Producir una lectura semanal/diaria desde el MT5 local, cerrada por tiempo,
causal, trazable y solo informativa. El trabajo termina cuando el snapshot se
puede reproducir y explicar; no cuando genera una entrada.

## Reparto

| Dueño | Entrega | Write set |
|---|---|---|
| D2 | adaptador read-only sobre APIs existentes | `engine/` acordado |
| D4 | auditoría de esquema, frescura y hashes; no modifica datos | `audits/`/reporte acordado |
| D5 | tests negativos, PIT, FULL/PREFIX y determinismo | `tests/`/auditoría acordada |
| D1 | contrato, SDD, índice y worklog | `docs/`, `.hermes-index.md`, `.hermes-worklog/` |
| D7 | integración del brief y commit selectivo | `scripts/`/artefactos acordados |

## Reglas de ejecución

1. Leer AGENTS, contrato, SDD, índice y worklog antes de editar.
2. Consultar Graphify y Engram para contexto, sin tratarlos como evidencia.
3. Verificar Git y write sets; conservar cambios ajenos.
4. Si una tarea descubre una subtarea necesaria, incorporarla al plan y
   ejecutarla si permanece dentro de este alcance; no cambiar de misión.
5. Si aparece un fallo corregible, corregir productor/contrato, repetir tests y
   auditar de nuevo. No ocultar hallazgos cambiando el criterio.
6. Si falta una decisión de autoridad, datos o licencia, marcar `REVIEW` o
   `BLOCKED`; no rellenar ni saltar el gate.
7. Cerrar con `AGENTE/DEPARTAMENTO/TAREA/STATUS/EVIDENCIA/ARCHIVOS/RIESGOS/
   SIGUIENTE ACCIÓN`, worklog, índice, Graphify y commit local selectivo.

## Fuera de alcance

Dukascopy, nuevas descargas, backtest de rendimiento, experimentos, IA,
órdenes, broker, producción y `git push`.

## Gates

- M0 preflight: PASS
- M1 contrato/SDD: PASS
- M2 ensamblaje read-only: pendiente
- M3 causalidad/determinismo: pendiente
- M4 brief/evidencia: pendiente
- M5 auditoría independiente: pendiente
