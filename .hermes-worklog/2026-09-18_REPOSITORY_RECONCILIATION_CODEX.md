# Reconciliación y ordenamiento del repositorio — 2026-09-18

## Misión

Ordenar `vjack666/ict2.0` sin usar Work y sin destruir historia.

## Rama de trabajo

`codex/repository-order-20260918`, creada desde `entrenamiento-ia`.

## Hallazgo principal

GitHub no encuentra ancestro común entre `main` y `entrenamiento-ia`.
Se evita deliberadamente `--allow-unrelated-histories` y cualquier reescritura
de `main`.

## Cambios

- creado `docs/REPOSITORY_CANONICAL_STATE.md`;
- actualizado `README.md`;
- actualizado `docs/REPOSITORY_MAP.md`;
- actualizado `docs/REPOSITORY_ORDER.md`;
- creado `requirements-ai.txt`;
- creado `.python-version` con Python 3.11.15;
- eliminadas rutas absolutas de Windows en los tres scripts IA centrales:
  - `train_setup_quality_v1.py`;
  - `train_failure_risk_v1.py`;
  - `materialize_failure_anatomy_v1.py`;
- limpiado el `entry_id` duplicado en `engine/sequence.py`;
- actualizado `.hermes-index.md`.

## Lo que NO se hizo

- no se borraron ramas;
- no se fusionó `main`;
- no se regeneraron datasets;
- no se entrenaron modelos;
- no se modificaron labels ni resultados OOS;
- no se habilitó trading.

## Riesgo pendiente

La reconciliación completa de historias debe hacerse por unidades verificables.
El siguiente gate es ejecutar imports/tests relevantes en un checkout de esta
rama y después decidir qué línea se convertirá en la rama por defecto.

## Estado

`READY_FOR_AUDIT`
