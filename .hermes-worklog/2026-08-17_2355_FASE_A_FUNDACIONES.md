# Worklog — Fase A: saneamiento de fundaciones

**Fecha:** 2026-08-17  
**Objetivo:** corregir los bloqueos reales de Fase A y preparar una ejecución verificable de CI antes de habilitar Fase B.

## INSPECCIÓN

Se revisó `main` y se comprobó que:

- existe `tests/test_market_object_pd_contract.py`;
- `engine/market_object.py` ya contiene el contrato temporal candidate/confirmation/tradable;
- `.github/workflows/hermes-tests.yml` usa `actions/setup-python@v5` con `cache: pip`;
- el repositorio no tenía `requirements.txt`, `pyproject.toml` ni `pytest.ini`.

Esto explica directamente el error anterior del runner:

`No file ... matched to [**/requirements.txt or **/pyproject.toml]`.

## CORRECCIÓN 1 — Dependencias CI

Se añadió `requirements.txt` con dependencias mínimas y fijadas para la suite actual:

- `pytest==8.3.5`
- `pytest-cov==6.1.1`

No se agregaron paquetes por especulación. Las dependencias se limitan a lo necesario para ejecutar la suite existente.

## CORRECCIÓN 2 — Contrato base `MarketObject`

Se reforzaron invariantes estructurales:

- dirección válida `-1/0/1`;
- geometría de zona no invertida;
- contadores no negativos;
- primer toque no anterior a la disponibilidad tradable;
- invalidación no anterior al candidato.

No se modificó la semántica de detección FVG/OB.

## CORRECCIÓN 3 — Tests

Se amplió `tests/test_market_object_pd_contract.py` para cubrir las nuevas invariantes y mantener los tests existentes de serialización, temporalidad y capas POI.

## RESULTADO

**Código corregido y preparado para CI.**

**Gate A: PENDIENTE DE EVIDENCIA CI.**

No se declara PASS hasta observar un workflow real con instalación y pytest exitosos.

## REGLA DE CONTROL

Fase B permanece pausada. No se avanzará a nuevos detectores FVG/OB hasta que el Gate A sea `PASS`.

## Siguiente evidencia requerida

1. GitHub Actions — setup Python: PASS.
2. Instalación de requirements: PASS.
3. `pytest -q --disable-warnings --maxfail=1`: PASS.
4. Actualizar `.hermes-index.md` y cerrar A únicamente con esa evidencia.
