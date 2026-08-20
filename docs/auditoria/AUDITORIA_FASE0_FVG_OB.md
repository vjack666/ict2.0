# AUDITORÍA FASE 0 — FVG + ORDER BLOCKS + FUENTES EXTERNAS

**Fecha:** 2026-08-17  
**Estado:** COMPLETADA — GATE A: PASS CON BLOCKERS DOCUMENTADOS  
**Alcance:** auditoría previa a implementación. Esta fase no modifica lógica de trading.

## 1. Objetivo

Auditar el estado real de `vjack666/ict2.0` antes de implementar FVG/OB, incluyendo arquitectura, temporalidad, anti-look-ahead, lineage, lifecycle, datos, backtest, OTE residual, tests y fuentes externas.

Fuentes externas incorporadas a la auditoría:

- `vjack666/SMC-SYSTEMS`, rama `main`.
- Historia de `ict_backtest` en `vjack666/ict2.0`.

## 2. Estado del motor ICT

El motor ya dispone de `engine/`, `detectors/`, `tools/`, `analysis/`, `orchestration/` y una ontología `MarketObject`/lineage suficiente para construir la capa FVG/OB. También existen dos familias de detectores FVG/OB que requieren contrato canónico antes de seguir.

### Arquitectura observada

```text
RAW OHLC
  ↓
Data Feed
  ↓
Detectors / Tools
  ├── Swing
  ├── BOS / CHOCH
  ├── Liquidity / Sweep
  ├── Displacement
  ├── FVG
  └── OB
  ↓
MarketObject / candle metadata
  ↓
SequenceState
  ↓
POI / Zone Authority / Execution
  ↓
Signal / expediente
  ↓
Learning / evaluation
```

## 3. Hallazgos internos críticos

### A0-01 — Duplicidad FVG/OB

Existen:

- `detectors/fvg.py`
- `engine/fvg_poi.py`
- `detectors/ob.py`
- `engine/order_block.py`

No deben evolucionar como cuatro fuentes de verdad. Fase B debe fijar contrato canónico y Fase C debe eliminar o aislar duplicaciones.

### A0-02 — Divergencia OB

`engine/order_block.py` sigue el canon documentado de vela contraria + cuerpo fuerte + follow-through posterior. `detectors/ob.py` usa otra formulación y añade clasificaciones parciales. No se debe escoger por intuición: se resolverá contra tesis/rulebook y tests de comportamiento.

### A0-03 — Lifecycle limitado

El tracking actual no representa correctamente múltiples FVG/OB coexistentes, mitigaciones y stacking. El dominio debe soportar múltiples objetos persistentes por dirección/TF.

### A0-04 — Contrato temporal incompleto

`MarketObject` aporta identidad, zona, estado, parent/related objects y tiempos base, pero FVG/OB necesitan distinguir explícitamente:

`candidate → confirmation → tradable → mitigation/invalidation`.

No se puede consumir una entidad antes de `tradable_time`.

### A0-05 — Lineage

`engine/lineage.py` ya soporta una cadena causal base. Debe extenderse para que FVG/OB sean objetos causales explícitos:

`LIQUIDITY → SWEEP → DISPLACEMENT → BOS/CHOCH → FVG/OB → POI → RETURN → ENTRY`.

### A0-06 — Datos

`data/` está ignorado por Git y `data/raw/EURUSD_M5.parquet` no está en el árbol remoto. Hermes debe comprobar disponibilidad local antes de backtest real y auditar schema, timestamps, timezone, duplicados, gaps y orden.

Existe además una discrepancia histórica entre rutas documentadas y loader que debe resolverse antes del backtest.

### A0-07 — OTE residual

Persisten físicamente `engine/ote.py` y `detectors/fib.py`. No se borran en Fase 0. Fase B/C debe auditar imports/consumidores y retirar cualquier dependencia. OTE/Fibonacci 62–79% no puede volver al pipeline bajo otro nombre.

### A0-08 — Suite de tests

No aparece un directorio `tests/` en el árbol remoto auditado. Esto queda como riesgo crítico hasta localizar la suite efectiva o reconstruir los tests contractuales necesarios.

## 4. Auditoría externa — `vjack666/SMC-SYSTEMS`

El repositorio externo es Python modular y contiene detectores ICT, backtest y pipeline ML. Su README describe FVG, OB, displacement, premium/discount, BOS, CHOCH, liquidity sweeps, análisis multi-timeframe y un pipeline ML con validación/walk-forward.

### 4.1 `detectors/fvg.py` — VALOR ALTO / RESCATE SELECTIVO

Implementa FVG de tres velas, tamaño, midpoint y tracking básico de fill, además de `pd_type/pd_tier`.

**Decisión:** comparar matemática contra el canon ICT actual y rescatar únicamente partes demostrablemente mejores. Su tracking también conserva sólo una zona activa bullish/bearish, por lo que no resuelve nuestro requisito de lifecycle multi-zona.

### 4.2 `detectors/ob.py` — VALOR ALTO / RESCATE SELECTIVO

Implementa OB, estado/edad y clasificación parcial de `OB`, `REJECTION_BLOCK` y `PROPULSION`; deja Breaker/Mitigation/BPR para integración posterior.

**Decisión:** referencia comparativa, no fuente de verdad. Su `shift(-1)` y semántica de dirección deben pasar por el contrato temporal ICT antes de reutilizar código.

### 4.3 `detectors/displacement.py` — VALOR ALTO / POSIBLE RESCATE

Tiene configuración explícita de displacement basada en rango promedio, body ratio, wick ratio y magnitud. El código documenta que su matemática fue migrada desde una utilidad histórica de `ict_backtest` a rango puro.

**Decisión:** comparar parámetros y matemática con el displacement actual de ICT. Si demuestra superioridad y compatibilidad, rescatar sólo la lógica matemática/configuración, no el módulo completo.

### 4.4 `detectors/liquidity.py` / `liquidity_context.py` — REFERENCIA

Existen implementaciones externas de liquidez/contexto. No se adoptan en Fase 0 porque el motor ICT ya posee su cadena de liquidez/sweep. Se compararán sólo si un blocker del dominio lo requiere.

### 4.5 `detectors/zones.py` — RECHAZADO

Contiene explícitamente OTE 0.62–0.79.

**Decisión:** excluir completamente de cualquier migración.

### 4.6 `ml/validator.py` — REFERENCIA FUTURA

Aporta validación de schema, determinismo, columnas críticas y leakage. Sin embargo, su lista de features contiene OTE, por lo que no puede copiarse sin depuración.

### 4.7 `ml/walk_forward.py` — REFERENCIA FUTURA

Aporta ventanas cronológicas y opción de PurgedKFold. Es útil para la fase de aprendizaje/OOS, pero no debe convertirse en dependencia del motor de detección.

**Decisión general sobre SMC-SYSTEMS:** usarlo como fuente comparativa; no copiar el repositorio entero ni importar módulos acoplados. Cada rescate debe demostrar equivalencia o superioridad mediante tests.

## 5. Auditoría de `ict_backtest`

No existe actualmente un directorio `ict_backtest/` en `main`.

La historia del repositorio confirma que `ict_backtest/` fue eliminado deliberadamente en el commit `425fb5325c43bc056cd9eb80fbf103c249ed2f45` porque era un backtest desechable, no usado por `engine/` ni `detectors/`. El commit documenta que contenía backtest, simulador, optimización, costes, diagnósticos y `semantic_adapter` y que la dependencia histórica era `ict_backtest → engine`, nunca al revés.

**Decisión:** NO resucitar `ict_backtest/` ni migrar módulos completos al motor.

La única excepción será rescatar una utilidad matemática mínima y aislada si una auditoría comparativa demuestra que mejora el contrato actual. La matemática de `avg_candle_range` ya es un ejemplo de este patrón: fue absorbida como lógica mínima en displacement.

## 6. Regla de migración entre repositorios

Nada se copia por volumen ni por nombre.

```text
CANDIDATO
  ↓
COMPARAR CON TESIS ICT
  ↓
COMPARAR CON IMPLEMENTACIÓN ACTUAL
  ↓
TEST DE EQUIVALENCIA / SUPERIORIDAD
  ↓
ANTI-LOOK-AHEAD
  ↓
¿MEJORA REAL?
  ├── NO → RECHAZAR Y DOCUMENTAR
  └── SÍ → EXTRAER SÓLO MÓDULO/LÓGICA MÍNIMA
                    ↓
                 TESTS
                    ↓
                 COMMIT
```

El código externo no puede traer OTE, Fibonacci, indicadores o dependencias innecesarias al motor sólo porque vengan acoplados al módulo candidato.

## 7. Mapa de rescate provisional

| Fuente | Candidato | Acción | Motivo |
| --- | --- | --- | --- |
| SMC-SYSTEMS | `detectors/fvg.py` | COMPARAR / RESCATAR SELECTIVAMENTE | FVG + fill/mid metadata |
| SMC-SYSTEMS | `detectors/ob.py` | COMPARAR / RESCATAR SELECTIVAMENTE | OB + clasificación parcial |
| SMC-SYSTEMS | `detectors/displacement.py` | COMPARAR / POSIBLE RESCATE | matemática explícita |
| SMC-SYSTEMS | `ml/validator.py` | REFERENCIA FUTURA | schema/leakage/determinismo |
| SMC-SYSTEMS | `ml/walk_forward.py` | REFERENCIA FUTURA | OOS/PurgedKFold |
| SMC-SYSTEMS | `detectors/zones.py` | RECHAZAR | contiene OTE |
| ICT histórico | `ict_backtest/` completo | NO MIGRAR | backtest desechable eliminado |
| ICT histórico | utilidades matemáticas aisladas | EVALUAR CASO POR CASO | sólo si son imprescindibles |

## 8. Decisiones de Fase 0

1. No modificar todavía la lógica de trading.
2. `SPEC_TESIS_FORMAL` + enmienda OTE mantienen autoridad superior.
3. FVG/OB deben terminar con una fuente de verdad canónica en `engine/` y objetos persistentes `MarketObject`.
4. `SMC-SYSTEMS` queda como fuente de referencia comparativa, no como dependencia.
5. Sólo se migrará código externo cuando un test demuestre equivalencia o superioridad y se pueda aislar el mínimo necesario.
6. `ict_backtest/` no se revive.
7. No se migra ningún módulo que introduzca OTE, Fibonacci, indicadores o acoplamiento innecesario.
8. La validación ML/OOS externa se evaluará en las fases de aprendizaje/robustez, no durante la detección base.
9. La comparación externa pasa a ser una entrada formal de Fase B.

## 9. Gate A — cierre

**FASE 0 COMPLETADA.**

Resultado: `PASS CON BLOCKERS DOCUMENTADOS`.

La auditoría cubrió el motor ICT, `SMC-SYSTEMS` y el historial de `ict_backtest`. No quedan tareas de Fase 0 pendientes.

Los blockers pasan a Fase B/C y no se consideran resueltos por esta auditoría.

**Siguiente fase:** Fase B — contratos de dominio FVG/OB/Breaker/BPR + temporalidad + selección de candidatos de rescate externo.
