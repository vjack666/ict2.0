# Worklog — Fase A: saneamiento de fundaciones

**Fecha:** 2026-08-17  
**Objetivo:** corregir los bloqueos reales de Fase A y cerrar el Gate A con evidencia reproducible.

## INSPECCIÓN

Se identificaron tres bloqueos reales:

- `setup-python` necesitaba una dependencia declarada para su caché;
- la suite no podía importar `engine` en CI;
- la documentación no debía declarar A cerrada sin evidencia ejecutada.

## CORRECCIONES

### Dependencias CI

Se añadió `requirements.txt` con:

- `pytest==8.3.5`
- `pytest-cov==6.1.1`

### Paquete `engine`

Se añadió `engine/__init__.py` y se fijó `PYTHONPATH=${{ github.workspace }}` en CI.

### Pytest

Se añadió `pytest.ini` con `pythonpath = .` y `testpaths = tests`.

El workflow ahora verifica explícitamente:

- existencia de `engine/__init__.py`;
- existencia de `engine/market_object.py`;
- import real de `engine`;
- ejecución mediante `python -m pytest`.

### Contrato base

Se mantuvieron/reforzaron las invariantes estructurales y temporales de `MarketObject` sin introducir lógica nueva de estrategia FVG/OB.

## EVIDENCIA DE EJECUCIÓN

**Workflow:** `Hermes Tests`  
**Run:** `#26`  
**Run ID:** `32081912747`  
**Commit:** `dacf7b221d22d1549b6aa687fbf2421da6430212`  
**Merge ref ejecutado por GitHub:** `dc0e9948ce44c8c25f6a8084364389e37b7abd95`

Resultados:

```text
setup-python              PASS
install dependencies      PASS
verify repository/import  PASS
pytest                    PASS

8 passed in 0.02s
```

## RESULTADO

**GATE A = PASS.**

No se relajaron invariantes para conseguir verde. El fallo anterior `ModuleNotFoundError: No module named 'engine'` fue corregido y verificado en ejecución real.

## DECISIÓN

Fase A queda **CERRADA**.

Fase B queda **HABILITADA**, pero debe ejecutar su propio contrato y gate antes de introducir nuevos detectores FVG/OB.

M5 continúa `DEFERRED`; no forma parte del criterio de PASS de A.

## SIGUIENTE FASE

Iniciar Fase B — contratos de dominio FVG/OB/Breaker/BPR y lifecycle, con tests reales y actualización obligatoria de índice/bitácora al finalizar el gate.
