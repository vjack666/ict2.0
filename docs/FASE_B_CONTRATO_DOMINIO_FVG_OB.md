# FASE B — CONTRATO DE DOMINIO FVG / OB / BREAKER / BPR

**Fecha:** 2026-08-17  
**Fase:** B — Contratos de dominio  
**Estado:** `IN_PROGRESS / GATE_PENDING`  
**Autoridad:** `docs/SDD_FVG_OB_ENGINE.md` + tesis ICT vigente

## 1. Objetivo

Cerrar el modelo de dominio que utilizará el motor para representar PD Arrays como objetos persistentes, temporales y causales, sin introducir todavía detectores ni reglas de entrada.

## 2. Contrato canónico

### 2.1 Tipos

`FVG`, `ORDER_BLOCK`, `BREAKER` y `BPR` son tipos canónicos de `ObjectType`.

### 2.2 Capas

Se mantiene la ontología vigente: `POI` sólo puede originarse en `D1/H4/H1`. M15/M5/M1 permanecen como refinamiento/ejecución según el contexto top-down. Fase B no cambia esa autoridad.

### 2.3 Integridad estructural

`MarketObject` debe rechazar:

- dirección fuera de `{-1, 0, 1}`;
- zonas invertidas (`zone_high < zone_low`);
- contadores negativos;
- `quality_score` fuera de `[0,1]`;
- `first_touch_bar` sin `touch_count >= 1`.

### 2.4 Contrato temporal

Cuando los campos existen:

`candidate <= confirmation <= tradable`

Nunca existe `tradable` sin `confirmation`.

Además:

- `first_touch >= tradable`;
- `invalidated >= candidate`;
- `candidate_time <= confirmation_time <= tradable_time` cuando los tiempos son comparables.

La implementación no puede aceptar información futura sólo para construir un objeto histórico.

### 2.5 Lifecycle

Las transiciones válidas son explícitas:

```text
CREATED
  ├─> ACTIVE
  ├─> INVALIDATED
  └─> EXPIRED

ACTIVE
  ├─> PARTIALLY_MITIGATED
  ├─> MITIGATED
  ├─> INVALIDATED
  ├─> EXPIRED
  └─> CONSUMED

PARTIALLY_MITIGATED
  ├─> PARTIALLY_MITIGATED
  ├─> MITIGATED
  ├─> INVALIDATED
  ├─> EXPIRED
  └─> CONSUMED
```

`MITIGATED`, `INVALIDATED`, `EXPIRED` y `CONSUMED` son terminales. No pueden reactivarse.

### 2.6 Lineage

`parent_object` y `related_objects` forman parte del contrato. Se prohíben autorreferencias, duplicados y IDs vacíos. La Fase D será responsable de imponer relaciones causales específicas (por ejemplo, displacement → FVG/OB) una vez definidos los detectores canónicos.

## 3. Tests

`tests/test_market_object_pd_contract.py` cubre:

- round-trip de serialización;
- los cuatro tipos PD Array;
- orden temporal por barras y tiempos;
- requisitos de `tradable` y `first_touch`;
- invalidación temporal;
- invariantes estructurales;
- integridad de lineage;
- lifecycle y estados terminales;
- regla POI HTF.

## 4. Gate B

No se declara PASS hasta que GitHub Actions ejecute:

1. instalación reproducible;
2. verificación de importación;
3. suite completa con código 0;
4. todos los tests de contrato en verde.

No se permite relajar el contrato para conseguir verde.

## 5. Fuera de alcance

- detector FVG;
- detector OB;
- Breaker/BPR como detectores;
- scoring operativo;
- entradas/SL/TP;
- aprendizaje;
- M5 como requisito de validación.

## 6. Próximo paso

Ejecutar CI sobre esta fase. Si falla cualquier prueba, corregir y repetir hasta Gate B `PASS`.
