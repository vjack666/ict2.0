# SDD — EVOLUCIÓN DEL MOTOR ICT: FVG + ORDER BLOCKS

**Versión:** 1.1  
**Fecha de sincronización:** 2026-08-20  
**Estado:** Contrato de diseño vigente; FVG/OB y lineage estructural implementados, ejecución/backtest aún bloqueados por la pila pre-backtest.
**Fuente de verdad:** `docs/ict/SPEC_TESIS_FORMAL.md` + contratos vigentes y enmienda de eliminación de OTE.

## 1. Propósito

Diseñar una evolución del motor que convierta FVG y Order Blocks en entidades temporales y causales integradas con Swing/BOS/CHOCH, liquidez y displacement.

El diseño debe favorecer aprendizaje posterior: el dataset de señales debe conservar contexto y lineage, no solo la etiqueta final.

## 2. Modelo conceptual

```text
Market Data
   ↓
Swing / Structure
   ↓
Liquidity → Sweep
   ↓
Displacement
   ↓
BOS / CHOCH / MSS
   ↓
PD Arrays
   ├── FVG
   ├── OB
   ├── Breaker
   └── BPR
   ↓
POI / Context State
   ↓
Sequence / MTF navigation
   ↓
Retest / Execution
   ↓
SL / TP / Outcome
```

## 3. Entidades

### FVG

Campos mínimos: identidad, dirección, timeframe, creación/confirmación/tradabilidad, geometría, estado, mitigación, touch, invalidación, edad y lineage.

Detector canónico vigente: tres velas, confirmación cerrada, sin look-ahead.

### Order Block

Campos mínimos: identidad, dirección, timeframe, source candle, creación/confirmación/tradabilidad, geometría, estado, footprint/follow-through, mitigación, invalidación y lineage.

Detector canónico vigente: footprint candle + closed follow-through.

### Breaker

Debe conservar referencia al OB padre y al evento que lo invalidó. No se considera detector terminado solo por existir en `ObjectType`.

### BPR / composite POI

Debe representar relación entre componentes, no duplicarlos.

### POI

POI es un rol asignado a uno o más PD Arrays y debe conservar componentes, TF, dirección, dealing-range context, alineación HTF, displacement, freshness, quality y lineage.

## 4. Lineage

Cada objeto derivado debe poder responder qué sweep, displacement y evento estructural lo precedieron y cuándo se volvió tradable.

La relación es unidireccional respecto al tiempo histórico y auditable.

## 5. Temporalidad

Separar explícitamente:

- HTF: contexto;
- ITF: zona/estructura;
- EXEC/LTF: confirmación y timing.

Un objeto HTF no puede usar información posterior al timestamp de decisión EXEC para validar una señal histórica.

## 6. Ejecución

La ejecución futura debe poder esperar:

`structure confirmation → zone creation → zone becomes tradable → price returns → execution confirmation → entry`.

No se confunde creación de zona con ejecución.

La existencia de FVG/OB, Context State, Sequence COMPLETE o `SETUP_READY` no autoriza por sí sola una orden.

## 7. Calidad

La calidad es explicable y debe poder someterse a ablación. Features potenciales incluyen sweep, displacement, BOS/CHOCH, freshness, overlap, stacking, HTF alignment y edad/mitigación.

No se congela un peso como verdad absoluta antes de validación empírica.

## 8. Backtest y aprendizaje

Las entidades deben ser observables para medir creación, confirmación, primer toque, entrada, mitigación, invalidación, MFE, MAE y outcome R cuando exista una especificación de ejecución congelada.

El backtest permanece bloqueado hasta los gates pre-backtest/TNA definidos por el plan maestro.

## 9. Seguridad contra look-ahead

Toda función que consume datos futuros para confirmar una entidad debe producir timestamp de confirmación. La entidad no participa antes de `tradable_at`.

Tests y auditorías deben mutar/truncar el futuro y comprobar invariancia histórica.

## 10. Compatibilidad

La evolución no debe romper Swing/BOS/CHOCH existentes. El blocker histórico de pivotes BOS no causales fue corregido; cualquier cambio futuro de estructura requiere regresión explícita.

## 11. Observabilidad

Cada señal debe poder explicar, como mínimo:

`structure → liquidity → sweep → displacement → PD array → Context State → sequence/POI → retest → entry → SL → TP`.

Si una señal no puede explicar su lineage, está incompleta para aprendizaje.

## 12. Estado empírico actual

- FVG/OB strict 20Y: PASS + lineage causal.
- Funnel MTF+Sequence 20Y: PASS + gate CI.
- Sequence COMPLETE: n=3, insuficiente para declarar edge.
- Context State × Sequence: `INSUFFICIENT_N`, n=24 depth≥4 deduplicado.
- TNA trace: PASS estratificado; behavioral/full-span pendiente.
- OTE/Fibonacci: prohibidos; dealing range EQ50 only.

Estos resultados son evidencia de integridad/población, no de rentabilidad.
