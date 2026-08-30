# Plan operativo — Reconciliación post-A7 y transición a Episodes/Funnel

**Fecha:** 2026-08-30
**Owner:** Codex como CEO operativo; Hermes como director de D2 bajo coordinación
**Modo:** LOCAL_ONLY; sin push, sin remoto, sin producción
**SDD rector:** `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`
**Entrada:** A7 técnico completado; Lifecycle, MarketState y Setup Builder existentes en `engine/`

## Objetivo

Dejar una única lectura coherente para Hermes y Codex sobre lo que existe,
qué está verificado, qué no debe duplicarse y cuál es el siguiente trabajo:
Episodes/Funnel sobre setups históricos causales.

## Orden obligatorio

### Fase 0 — Inventario y autoridad

- leer `AGENTS.md`, `.hermes-index.md`, el SDD rector, contratos y último worklog;
- confirmar rama, `git status --short`, HEAD y write set;
- separar archivos activos de `.hermes-cert/`, ramas históricas y artefactos;
- consultar Graphify para navegación, sin tratarlo como certificación.

**Salida:** matriz de autoridad sin duplicados.

### Fase 1 — Verificación de la capa existente

- revisar `MarketObject`, `lifecycle`, `market_state` y `setup_builder`;
- ejecutar las suites focales y guardar comandos/resultados;
- verificar autoridad TF, observación LTF, idempotencia, terminalidad,
  `projection_at(T)`, persistencia y elegibilidad;
- comprobar que Setup Builder no muta Lifecycle ni usa el presente.

**Salida:** auditoría de implementación; cualquier fallo corregible se repara
en esta misma fase y se vuelve a verificar.

### Fase 2 — FULL/PREFIX del estado

- definir decisiones T y corpus/configuración exactos;
- comparar literalmente snapshots FULL/PREFIX, no solo hashes parciales;
- reportar divergencias con objeto, campo, TF, tiempo y causa;
- si falla, clasificar `BLOCKED`, corregir el motor o el comparador y repetir.

**Salida:** evidencia reproducible o blocker explícito.

### Fase 3 — Preparación Episodes/Funnel

- no escribir código aún;
- definir Episode, ventana causal, identidad, agrupación, estados y razones de
  rechazo;
- distinguir `SetupEligibility` de estado del objeto y de resultado futuro;
- redactar `CONTRATO_EPISODES_FUNNEL.md` y `SDD_EPISODES_FUNNEL_V1.md`;
- proponer tests negativos y write set.

**Gate:** aprobación documental independiente de D5 antes de implementar.

### Fase 4 — Implementación futura

Solo después del gate anterior:

- D2 implementa `engine/episodes.py` con write set cerrado;
- D5 crea/ejecuta auditoría del funnel;
- D1 actualiza índice, worklog y SDD con evidencia real;
- D7 crea commit local selectivo; nunca push en cierre normal.

## Reglas de auto-corrección

1. Si un test, contrato, referencia o gate falla, no declarar `COMPLETED`.
2. Diagnosticar causa raíz, corregir dentro del write set y repetir todas las
   verificaciones afectadas.
3. No cambiar el criterio para hacer pasar la corrida.
4. Si falta evidencia, declarar `REVIEW`/`BLOCKED`, no inferir PASS.
5. Si aparece código duplicado, detener la integración, localizar la autoridad
   canónica y eliminar la duplicación solo con alcance aprobado.
6. Si el alcance cambia, actualizar SDD/plan antes de programar.
7. Cada cierre debe dejar evidencia, archivos, riesgos y siguiente acción en el
   formato de `AGENTS.md`.

## Gates de salida

- `objective_satisfied=true`;
- tests requeridos pasan en el alcance completo;
- evidencia y bitácora registradas;
- cero blockers sin resolver;
- archivos y documentos consistentes;
- `git diff --check` limpio;
- Graphify actualizado tras cambios;
- commit local selectivo, sin push.

## No objetivos

No backtest de rendimiento, no edge, no entrenamiento, no órdenes, no cambios
de dataset, no descarga externa, no CME/OI, no OTE y no migración a otra rama o
host para ocultar un bloqueo local.
