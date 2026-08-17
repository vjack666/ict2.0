# FASE B — CONTRATO DE DOMINIO FVG / OB / BREAKER / BPR

**Fecha:** 2026-08-17  
**Fase:** B — Contratos de dominio  
**Estado:** IMPLEMENTACIÓN INICIAL — GATE PENDIENTE DE EJECUCIÓN DE TESTS  
**Autoridad:** `docs/SDD_FVG_OB_ENGINE.md` + tesis ICT vigente

## 1. Objetivo

Cerrar el modelo de dominio que utilizará el motor para representar PD Arrays como objetos persistentes, temporales y causales.

## 2. Decisiones

### 2.1 Tipos canónicos

`FVG`, `ORDER_BLOCK`, `BREAKER` y `BPR` pasan a estar representados por `ObjectType`.

### 2.2 Estados

Los objetos pueden recorrer:

`CREATED → ACTIVE → PARTIALLY_MITIGATED → MITIGATED`

o terminar en `INVALIDATED`, `EXPIRED` o `CONSUMED` según la regla específica.

### 2.3 Contrato temporal

Cada objeto puede y debe conservar, cuando aplique:

- `candidate_bar/time`;
- `confirmation_bar/time`;
- `tradable_bar/time`;
- `first_touch_bar/time`;
- `invalidated_bar/time`;
- `mitigation_level`;
- `touch_count`;
- `age_bars`.

La invariante obligatoria es:

`candidate <= confirmation <= tradable`

y nunca puede existir `tradable` sin `confirmation`.

### 2.4 Linaje

Se mantiene `parent_object` y `related_objects`. Un FVG/OB futuro deberá apuntar al displacement/evento estructural que lo creó o confirmó, no reconstruirse por proximidad temporal.

### 2.5 Capas

Se mantiene la regla vigente: POI sólo en `D1/H4/H1`; M15/M5/M1 son refinamiento/ejecución según el contexto top-down. Esta fase no cambia esa autoridad.

## 3. Tests añadidos

`tests/test_market_object_pd_contract.py` cubre:

- round-trip serialización;
- orden temporal candidato → confirmación → tradable;
- prohibición de tradable sin confirmación;
- preservación de la regla de POI HTF.

## 4. Estado del gate

No se declara PASS hasta ejecutar la suite de tests en un entorno con dependencias del proyecto.

En la sesión de implementación actual no se pudo clonar `https://github.com/vjack666/ict2.0.git` desde el entorno de ejecución por falta de resolución de red. Por ello no se inventa un resultado de pytest.

**Gate B = BLOCKED_PENDING_TEST_EXECUTION.**

## 5. Siguiente acción autorizada

Una vez que Hermes disponga de un entorno con el repo local, ejecutar primero:

```bash
pytest -q tests/test_market_object_pd_contract.py
```

y después la suite completa disponible.

Si falla cualquier prueba, corregir y repetir antes de continuar con los detectores FVG/OB.
