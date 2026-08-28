# Auditoría de limpieza y mantenimiento del repositorio

- **Fecha:** 2026-08-28
- **Agente:** Codex / Repository Steward (D1) con verificación de riesgo
- **Estado:** COMPLETED — fase segura; limpieza destructiva WAITING por confirmación explícita
- **Objetivo:** instalar las skills recomendadas para Claude y devolver ICT SYSTEM a un estado mantenible sin perder trabajo local, evidencia científica ni procedencia de datos.

## Skills instaladas

Instalación global para Claude en `C:\Users\v_jac\.claude\skills`:

- `repo-maintenance` de `tyroneross/build-loop`.
- Los nueve tracks de `claude-plugin-code-cleanup` de `atj393`.
- `tech-debt-audit` de `ksimback/tech-debt-skill`.
- Las cinco skills `architecture-*` de `garrettgoff/claude-code-architect`.
- `clean` de `melodic-software/claude-code-plugins` (`repo-hygiene`).

Total: 17 skills con `SKILL.md` verificado. No se añadió código de terceros al checkout de ICT SYSTEM.

## Baseline reproducible

- Rama activa: `codex/audit-hermes-cert-20260826`.
- HEAD activo: `6583b710dcba43eab9f6ad642bb1589baeffabfa`.
- `main`: `c2e9aecbff16a69fe3df61ddef60812a97b62f03`.
- Checkout actual: 25 rutas modificadas/no confirmadas; se preservan íntegramente.
- Git: 18 ramas locales, 16 worktrees, 2 stashes, sin operación de merge/rebase en curso.
- Ramas candidatas a integración/eliminación: no se actuó sobre ninguna; la única rama contenida por `main` está todavía montada en un worktree sucio.
- Grafo existente consultado: `graphify-out/graph.json`; el mapa confirma la separación `engine`, `backtest`, `lab`, `runtime/Hermes`, `audits/tests` y `data`.

## Hallazgos

### 1. No existe un candidato seguro para borrado automático

El inventario de artefactos encontró solamente `.pytest_cache` como raíz reconocida por `repo-maintenance`; tiene menos de siete días y no cumple la retención. `git clean -ndX` muestra además `__pycache__`, `.venv`, `graphify-out`, `graphify-tmp`, `data/learning`, datasets raw y artefactos `.hermes-cert`. Estos últimos no se clasifican como caché descartable: pueden contener datos, evidencia o estado de laboratorio. Permanecen intactos.

### 2. El worktree no permite un reset global

Hay worktrees sucios con cambios en motor, SDD, auditorías, datos y reportes. No se usó `reset --hard`, `git clean`, eliminación de ramas ni `stash drop`. Antes de cualquier poda debe auditarse cada worktree por propietario, rama, hash, suciedad y equivalencia de parches.

### 3. Hay duplicación nominal, pero parte es compatibilidad deliberada

Se observaron wrappers como `scripts/verify_engine.py` → `scripts/smoke/verify_engine.py` y `scripts/tna_20y_parallel.py` → `scripts/audit/tna_20y_parallel.py`. No deben eliminarse por coincidencia de nombre. También hay nombres repetidos dentro de `agents`, `analysis`, `tools`, `detectors` y `engine`; requieren un mapa de consumidores antes de consolidar. La autoridad de lógica diaria sigue siendo `engine/` y `backtest/` sigue siendo consumidor aislado.

### 4. Portabilidad de la skill externa

El script `repo-maintenance` aborta en Windows al intentar invocar `ps` para detectar procesos. El resto del baseline se reprodujo mediante sus funciones de auditoría con el sondeo de procesos desactivado y con inventario Git nativo. No se modificó la skill de terceros; si se quiere usarla directamente en Windows, debe abrirse una tarea separada para una adaptación portable y sus pruebas.

## Plan de mantenimiento

1. **Cerrado:** instalar y verificar skills; consultar índice, gobierno, worklog reciente y Graphify.
2. **Cerrado:** baseline Git/artefactos y clasificación conservadora de cambios locales.
3. **Pendiente de confirmación:** ejecutar únicamente el dry-run de cachés; proponer la lista exacta y bytes antes de borrar. Nunca incluir `.venv`, `data/`, `graphify-out`, `graphify-tmp` ni evidencia de `.hermes-cert` sin decisión específica.
4. **Siguiente misión:** auditar worktrees/ramas uno por uno y crear refs de recuperación antes de cualquier retiro. No eliminar ramas con worktree o trabajo no integrado.
5. **Siguiente misión:** analizar wrappers y duplicados mediante consumidores, hash, historial y tests; consolidar solo si hay equivalencia comprobada.
6. **Siguiente misión:** definir política de retención para `data/learning`, artefactos de laboratorio, gráficos y Graphify, incluyendo escritor canónico, procedencia, antigüedad y cuarentena recuperable.
7. **Siguiente misión:** hacer portable la detección de procesos de `repo-maintenance` en Windows, con prueba local, sin cambiar el motor ICT.

## Límites respetados

- No se ejecutaron experimentos, backtests, entrenamiento, descargas, promoción ni push.
- No se modificaron `engine/`, `data/`, `datasets/`, `lab/` ni resultados científicos.
- No se tocaron cambios sucios, stashes, worktrees, ramas ni artefactos ignorados.
- La instalación de skills ocurrió fuera del repositorio.

## Siguiente acción

Solicitar confirmación explícita para el conjunto concreto de cachés regenerables que el usuario desea retirar. Hasta entonces, el estado correcto es `WAITING`, no `CLEAN`.
