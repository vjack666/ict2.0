# Plan empresarial de limpieza y mantenimiento — ICT SYSTEM

**Fecha:** 2026-08-28  
**Responsable operativo:** Codex / Repository Steward  
**Autoridad:** usuario/cliente; aprobación independiente para gates y promoción  
**Modo:** `LOCAL_ONLY`

## Objetivo

Mantener ICT SYSTEM como una empresa-laboratorio: cada área tiene dueño,
frontera, evidencia y ciclo de vida. La limpieza busca reducir ambigüedad y
costo operativo sin romper imports, contratos, datos, evidencia científica ni
trabajo paralelo.

## Organigrama operativo

| Departamento | Rutas canónicas | Responsabilidad | Regla de mantenimiento |
|---|---|---|---|
| D0 Dirección | `.hermes*`, `governance/` | misión, políticas y autoridad | no reescribir evidencia para forzar un estado |
| D1 Operaciones | `.hermes-worklog/`, `docs/`, `reports/` | documentación, bitácora y archivo | cada decisión durable deja evidencia |
| D2 Ingeniería | `engine/`, `agents/`, `analysis/`, `orchestration/`, `detectors/`, `tools/`, `runtime/` | motor diario y APIs | una sola autoridad canónica; compatibilidad explícita |
| D3 IA | `runtime/ai_learning/` | lineage, modelos, calibración y drift | Shadow Mode; `can_trade=false` |
| D4 Datos | `data/`, `datasets/` | procedencia, hashes y calidad | no borrar ni sustituir datos sin manifest y decisión |
| D5 Riesgo | `audits/`, `tests/` | QA, gates y reproducibilidad | auditoría independiente; fail-closed |
| D6 Laboratorio | `lab/` y `scripts/lab/` | hipótesis y experimentos | nunca promociona ni modifica la autoridad diaria |
| D7 Delivery | `scripts/`, `start_hermes.py` | entrypoints y entrega | wrappers documentados; sin push automático |

La ubicación física actual se conserva. El organigrama es una capa de
responsabilidad, no una orden para mover carpetas.

## Diagnóstico actual

- La separación de autoridad está establecida y respaldada por Graphify.
- Existen wrappers de compatibilidad en `scripts/`; no son duplicados eliminables
  por nombre.
- Los módulos de mayor tamaño están en `engine/` y `runtime/ai_learning/`;
  requieren refactor con tests, no una limpieza mecánica.
- `data/`, `reports/`, `graphify-out/`, `graphify-tmp/` y `.venv/` tienen
  propósitos distintos. No se deben mezclar en una purga global.
- Hay múltiples worktrees y ramas con trabajo activo o no integrado. Ninguno se
  retira por inferencia.

## Ciclo de mantenimiento

### M0 — Inventario y control de cambios

Registrar rama, HEAD, estado sucio, worktrees, stashes, artefactos, consumidores
y gates. Si hay cambios locales, se preservan y se usa staging selectivo.

### M1 — Cachés regenerables

Solo después de un dry-run y confirmación exacta se pueden retirar `__pycache__`
y `.pytest_cache` del checkout principal. Quedan fuera `.venv`, `data/`,
`datasets/`, `graphify-out/`, `graphify-tmp/`, `.hermes-cert/` y resultados de
laboratorio.

### M2 — Artefactos y procedencia

Cada artefacto debe clasificarse como `ACTIVO`, `EVIDENCIA`, `HISTÓRICO`,
`CACHÉ` o `CUARENTENA`. Los datos o resultados con valor probatorio se mueven
solo a una cuarentena recuperable después de registrar hash, origen y escritor.

### M3 — Worktrees, ramas y stashes

Auditar propietario, rama, base, HEAD, suciedad y trabajo único. Una rama con
worktree o cambios no fusionados se conserva. La poda exige prueba de
ancestro/equivalencia, ref de recuperación y autorización específica.

### M4 — Duplicados y arquitectura

Comparar hash, historial, imports, consumidores y tests. Mantener fachadas de
compatibilidad; retirar solo copias sin consumidores y con sustituto documentado.
No crear un segundo motor ICT ni una segunda autoridad Wyckoff/AHF.

### M5 — Verificación y cierre

Ejecutar verificaciones focales, `git diff --check`, actualizar Graphify,
registrar worklog y crear un commit local selectivo. `git push` y promoción son
decisiones separadas.

## Acciones ejecutadas en esta misión

- Skills de limpieza, deuda técnica, arquitectura y repo hygiene instaladas
  globalmente para Claude; 17 `SKILL.md` verificados.
- Baseline Git y artefactos ejecutado desde el checkout operativo local.
- Graphify actualizado: 10.233 nodos, 16.217 relaciones y 916 comunidades.
- No se borraron cachés, datos, reportes, ramas, worktrees ni stashes.
- Este plan y la bitácora asociada quedan como evidencia de D1.

## Backlog controlado

| Prioridad | Trabajo | Dueño | Estado |
|---|---|---|---|
| P0 | Confirmar el conjunto exacto de cachés regenerables | cliente + D1 | WAITING |
| P1 | Auditar worktrees/ramas antes de cualquier retiro | D5 + D1 | pendiente |
| P1 | Revisar wrappers y duplicados por consumidores | D2 + D5 | pendiente |
| P1 | Definir retención y cuarentena de `data/learning` y reportes | D4 + D6 | pendiente |
| P2 | Hacer portable el detector de procesos de `repo-maintenance` en Windows | D2 | pendiente |
| P2 | Refactorizar módulos grandes únicamente con contrato y tests | D2 + D5 | pendiente |

## Criterio de empresa saludable

El proyecto no se declara “limpio” por tener pocos archivos. Se declara
mantenible cuando cada ruta tiene dueño, cada artefacto tiene ciclo de vida,
cada duplicado tiene clasificación, cada cambio tiene evidencia y ninguna
limpieza destruye trabajo no clasificado.
