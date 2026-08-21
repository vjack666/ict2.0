# INCIDENTE DE GOBERNANZA — Frente B5 (abc)

**Fecha:** 2026-08-20 19:25 UTC-5
**Severidad:** MEDIA (gobernanza, no código)

## Hallazgo
El subagente delegado para B5 ejecutó `git checkout -b feature/b5-ablation` sobre una rama que
YA EXISTÍA con trabajo activo de Ruben (engine-seq-v2-causal: engine/sequential_events.py,
audit_state.json, scripts/exp_seq_x_context_state.py). Además fue TRUNCATED por rate limit 429
(5 subagentes en paralelo saturaron la API). Resultado: b5_ablation.py quedó untracked en la
rama de Ruben, EXP-006 no se generó, B5 incompleto.

## Corrección (CEO)
1. Resguardo b5_ablation.py a /tmp.
2. git clean elimina el script de la rama de Ruben (working tree de Ruben queda limpio).
3. Rama aislada LIMPIA feature/b5-ablation-clean (desde main) con el script.
4. Fix del script: quitar os.chdir (rompía venv/sklearn), rutas absolutas desde REPO, sys.path REPO.
5. Reinstalado torch+sklearn en venv (se habian perdido en regeneracion del venv).
6. Ejecutado B5 directamente -> EXP-006 generado (GATE 5 FAIL, evidencia real).

## Lección
- Antes de git checkout -b, verificar que la rama no exista.
- Subagentes comparten working tree -> se pisan el HEAD. No delegar ejecucion con git checkout
  concurrente; ejecutar directo o aislar filesystem.
- Rate limit: no lanzar >2-3 subagentes con LLM en paralelo.

## Estado
- b5_ablation.py: BIEN (348 lineas, stacking, PIT, walk-forward, GATE 5).
- EXP-006: GENERADO (GATE 5 FAIL, honesto).
- Rama: feature/b5-ablation-clean (aislada, no toca main ni Ruben).
