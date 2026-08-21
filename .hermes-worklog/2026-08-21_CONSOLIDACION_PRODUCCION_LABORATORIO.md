# Consolidación de producción y laboratorio — 2026-08-21

## Objetivo

Consolidar una base operativa estable y auditable para Hermes, separando el
motor de lectura diaria del laboratorio y cerrando el diagnóstico del lote
experimental actual sin modificar ni promocionar el motor activo.

## Cambios realizados

- Se creó `runtime/engine_registry.json`.
- Se creó `runtime/engine_registry.py` con validación fail-closed.
- La lectura diaria valida el registro antes de consumir datos y publica el
  motor activo en el brief.
- Se creó `docs/planificacion/SDD_PRODUCCION_LABORATORIO.md`.
- Se creó el reconciliador `scripts/lab/experiments/reconcile_current_experiments.py`.
- Se generaron `reports/audits/experiments/current_batch/EXP_MASTER_RECONCILIATION.json` y `.md` desde
  artefactos presentes en disco.

## Organización de auditorías — cierre de la misión

- Se reorganizó `reports/audits/` por dominio: `data/`, `temporal/`,
  `runtime/`, `ltf/`, `infrastructure/` y `experiments/`.
- Los experimentos quedaron separados en `current_batch/`, `sequential/` y
  `fvg_ob/`.
- La raíz `reports/audits/` quedó sin archivos sueltos: 51 artefactos fueron
  reubicados sin eliminación de contenido.
- Se actualizaron las rutas en documentación, scripts y workflows de CI para
  que los próximos resultados se escriban en la estructura nueva.
- Se añadió una excepción explícita en `.gitignore` para conservar los
  artefactos de `reports/audits/data/` en el repositorio.

## Estado experimental verificado

- Esperados: 15 experimentos.
- Artefactos de auditoría presentes: 10.
- A: A1 PASS, A2 BLOCKED, A3 FAIL, A4 PASS provisional, A5 PASS según su
  veredicto mecánico.
- B: B1–B5 BLOCKED por ausencia de JSON de auditoría en disco.
- C: C1 PASS provisional, C2 FAIL provisional, C3 BLOCKED, C4 PASS, C5 FAIL.
- Promoción: BLOCKED.

## Verificación

```text
tests/test_engine_registry.py + tests/test_daily_motor.py
14 passed, 1 warning
```

La compilación de los runners afectados pasó correctamente y el reconciliador
volvió a producir el informe en
`reports/audits/experiments/current_batch/`, manteniendo 15 esperados, 10
observados y el grupo B en estado `BLOCKED`.

La suite completa quedó en `90 passed, 1 failed`: el fallo está en
`tests/test_sequential_outcome.py::test_sweep_nodes_carry_wick_extremes_backward_compatible`
y no afecta los archivos modificados por esta misión. Se conserva como deuda
separada para una misión específica del motor secuencial.

## Decisión

`GEN-000` permanece como motor activo. El laboratorio no puede sustituirlo.
No se promovieron señales, parámetros ni candidatos.
