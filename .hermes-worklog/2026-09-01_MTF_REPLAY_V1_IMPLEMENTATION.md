# Implementación y auditoría — MTF Replay Orchestrator v1

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex, director D2; control D5 y cierre D1/D7.
- **DEPARTAMENTO:** Ingeniería, Assurance, PMO y Delivery.
- **TAREA:** ejecutar T0–T6 y T8, cerrar M0–M9 y dejar T7 real separado.
- **MODO:** `LOCAL_ONLY`, sintético, `can_trade=false`.

## STATUS

`COMPLETED — M0–M9 PASS TÉCNICO SINTÉTICO`

No se ejecutó T7, datos reales, edge, IA, MT5, órdenes, promoción ni push.

## Implementación

- Schema 2.0 con política fail-closed, IDs, timestamps, lineage, ciclos,
  checksum y compatibilidad 1.0.
- Reloj streaming HTF→LTF por batches de cierre simultáneo.
- Integración por APIs públicas con MarketState, SetupBuilder, Episodes y
  `sequential_outcome`.
- Identidad canónica de setup derivada del lineage sin modificar SetupBuilder.
- Cancelación/supersession antes del fill e invalidación superior post-entry
  diferenciadas.
- No same-bar fill por defecto.
- Checkpoint/resume por hashes, deltas, manifest y chunks físicos.
- Visor React/Vite local schema 2.0, compatibilidad histórica rotulada, carga
  perezosa y ocultamiento de T+1/outcome futuro.

## Auditoría D5

- Reporte: `reports/audits/mtf_replay/mtf_replay_audit.json`.
- `aggregated_status=PASS`; M0–M9 PASS.
- Perfiles: H4→M15 y H4→M15→M5 refinement.
- 100 batches sintéticos por perfil.
- FULL/PREFIX: 10/25/50/75/90 % PASS en ambos.
- Dos corridas por perfil con checksum idéntico.
- Corrida continua vs resume: estado final idéntico.
- Chunk sizes distintos: checksum lógico idéntico.
- `engine/` no importa `backtest/`.
- Suite final: 464 Python PASS.
- Viewer: 3 PASS, build Vite PASS, `npm audit`: 0 vulnerabilidades.
- Graphify actualizado: 12.275 nodos, 20.399 aristas y 1.042 comunidades.
- Engram guardado: observación `680`, topic
  `architecture/mtf-replay-orchestrator-v1`.

## Fallas encontradas y corregidas

1. Setup usa UUID efímero entre snapshots: el consumidor añadió clave canónica
   por componentes, sin cambiar el motor.
2. El primer audit runner no encontraba `npm` desde Python en Windows: usa
   `npm.cmd` resuelto con `shutil.which`.
3. Vite 6.4.2 tenía vulnerabilidad alta en Windows: actualizado a 6.4.3 y
   revalidado con cero vulnerabilidades.
4. El chunking inicial era solo lógico: se añadió materialización atómica de
   manifest y archivos lazy-load.
5. El reloj materializaba innecesariamente la lista completa de batches: se
   cambió a iteración directa. El artefacto monolítico aún reside en memoria;
   M8 certifica el fixture acotado y T7 medirá si requiere un sink streaming.

## Archivos principales

- `backtest/mtf_replay.py`
- `backtest/schema.py`
- `backtest/viewer/`
- `audits/codigo/mtf_replay.py`
- `tests/test_mtf_replay_schema.py`
- `tests/test_mtf_replay_orchestrator.py`
- `reports/audits/mtf_replay/mtf_replay_audit.json`

## Riesgos y siguiente acción

El PASS solo certifica infraestructura sintética. Falta T7: preregistrar un
mes, dataset/hash y perfil y obtener GO explícito. Esa corrida no podrá tunear
reglas ni usar sus resultados como edge. Los parquets y reportes experimentales
preexistentes permanecieron fuera del write set.
