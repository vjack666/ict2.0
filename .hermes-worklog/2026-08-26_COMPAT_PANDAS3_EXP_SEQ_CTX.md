# Bitácora — Compatibilidad pandas 3.x en EXP-SEQ-CTX-01

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo
**Departamento:** CTO / ingeniería + CRO / assurance
**Tarea:** Robustecer la fábrica y validadores OOS frente a timestamps naive y tz-aware bajo pandas 3.x.
**Status:** `COMPLETED` — commit local selectivo y push realizado a rama de revisión.

## Objetivo y alcance

Se atendió la mejora opcional identificada tras el preflight. El cambio queda
limitado a la normalización de fechas de la fábrica/validadores de
`EXP-SEQ-CTX-01`. No se ejecutó la fábrica, no se regeneraron datasets, no se
corrió backtest, no se descargó mercado y no se modificó `data/` ni `datasets/`.

## Cambio realizado

- Se añadió `_as_utc_timestamp()` en `scripts/lab/experiments/exp_seq_ctx_01_dataset.py`.
- La función localiza valores naive y convierte valores tz-aware a UTC.
- Se reutilizó en límites de bloques, ampliación OOS y validador OOS.
- Se añadieron pruebas para ambos formatos y para límites con zona horaria.

## Evidencia verificada

- `pytest -q tests/focal/test_oos_expansion_focal.py tests/test_exp_seq_ctx_01_context_bucket.py` → **23 passed**.
- `py_compile` sobre los tres scripts afectados → PASS.
- `git diff --check` → PASS.
- Graphify actualizado localmente después del cambio; `graphify-out/` es regenerable e ignorado por Git.
- Los cambios previos de parquet, gráficos, briefs y `.codex/` permanecen sin incluir.

## Autoauditoría

La primera ejecución detectó un fixture de prueba incorrecto: una hora local
se convertía al día siguiente UTC y quedaba fuera de `HOLDOUT`. Se corrigió el
fixture y se repitió toda la validación con resultado 23/23.

## Riesgos y límites

- El parche mejora compatibilidad y no constituye evidencia científica ni
  desbloquea `FEASIBILITY_FAIL_INSUFFICIENT_N`.
- La fábrica y la ampliación OOS deben regenerarse solo bajo autorización
  científica posterior; este cierre no certifica nuevos conteos.
- Push ejecutado tras la autorización explícita del usuario; la rama aún requiere revisión antes de cualquier promoción.

## Siguiente acción

Auditar la rama publicada `codex/pandas3-exp-seq-ctx-20260826`. No mezclarla
con `main`; después decidir por separado el siguiente experimento y su permiso
de ejecución.
