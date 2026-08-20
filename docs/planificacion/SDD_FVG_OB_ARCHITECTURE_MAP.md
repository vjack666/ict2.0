# SDD — Mapa de Arquitectura y Plan FVG/OB

**Proyecto:** `ict2.0`  
**Estado:** DOCUMENTO NORMATIVO VIVO — sincronizado hasta Funnel 20Y, Context State y TNA trace  
**Última sincronización:** 2026-08-20  
**Regla:** este SDD se actualiza al cerrar cada fase, experimento arquitectónico o cambio de contrato relevante.

## 1. Objetivo

Evolucionar el motor Swing/BOS/CHOCH a un modelo ICT causal donde FVG y Order Block sean objetos persistentes, trazables y temporalmente seguros.

Cadena objetivo:

`Liquidity → Sweep → Displacement → BOS/CHOCH/MSS → FVG/OB → POI → Retest → Entry → SL → TP → Outcome`

**Estado real por fases:**

- Fase A — Fundaciones: `PASS`.
- Fase B — Contratos de dominio FVG/OB: `PASS`.
- Fase C — Detección canónica FVG/OB: `PASS`.
- Fase D — Relación causal y lineage: `PASS`.
- D-extension FVG↔OB 20Y: `PASS STRICT + gate CI`.
- Funnel MTF+Sequence 20Y: `PASS + gate CI`.
- AHF: `IMPLEMENTADO v1`.
- TNA trace integrity: `PASS estratificado`; behavioral/full-span pendiente.
- Fase E — Ejecución: **BLOQUEADA como backtest hasta cerrar la pila pre-backtest/TNA**.
- F/G/H: `PENDING`.

## 2. Arquitectura vigente

```text
OHLC / DATA
   ↓
Swing → BOS / CHOCH
   ↓
Liquidity / Sweep → Displacement
   ↓
 ┌───────────────┐
 FVG             OB
 │                │
 └───────┬────────┘
         ↓
   MarketObject / PD Array
         ↓
   CausalLink / lineage
         ↓
   Context State HTF/ITF/EXEC
         ↓
   Sequence / AHF navigation
         ↓
   Retest / Touch
         ↓
   Execution (futuro; contrato separado)
         ↓
   Outcome / Learning dataset
```

La arquitectura separa contrato de objeto, detección, lineage, Context State/navigation y ejecución.

## 3. Estado implementado

### `engine/market_object.py`

Contrato canónico de MarketObject con identidad, dirección, TF, geometría, lifecycle, timestamps y lineage. Gate B validado.

### `engine/detectors/fvg.py`

Detector canónico de FVG de tres velas con confirmación cerrada y tests de invariancia por prefijo.

### `engine/detectors/ob.py`

Detector canónico de OB basado en footprint candle + closed follow-through. Breaker/BPR siguen siendo extensiones de contrato, no detectores terminados por existir en ObjectType.

### `engine/lineage.py`

`CausalLink` y validaciones temporales/duplicados. Gate D validado.

### `engine/dealing_range.py`

Solo `DISCOUNT | EQ | PREMIUM`; OTE/Fibonacci 62–79% prohibidos.

### `engine/mtf_navigation.py` / `engine/ahf.py`

Navegación MTF/AHF v1 implementada. El parche O(n) de precompute conserva equivalencia bit-exact en la regresión publicada; el uso sigue sujeto a PIT y contratos de capas.

### `engine/daily_motor.py`

Lectura LTF diaria D1→H4→H1→M15 implementada como snapshot observacional; no es API de órdenes.

## 4. Lineage y temporalidad

Garantías vigentes:

- parent y child distintos;
- `parent_bar <= child_bar`;
- timestamps monotónicos;
- no enlaces futuros;
- candidate/confirmation/tradable/observation respetan el contrato temporal.

## 5. Integración ICT vigente

La cadena causal canónica representable es:

`LIQUIDITY → SWEEP → DISPLACE → BOS → POI/REFINEMENT → RETURN`

Reglas:

1. FVG/OB aislado es objeto, no setup automático.
2. Sweep + displacement + estructura + FVG/OB es contexto, no garantía de edge.
3. Relación causal explícita; no inferida solo por proximidad.
4. Breaker/BPR requieren detectores específicos antes de considerarse completos.
5. Entrada, SL y TP no forman parte de la validación estructural de B-D.
6. OTE/Fibonacci prohibidos.
7. EQ/Premium/Discount son contexto geométrico, no sustituto de la lógica ICT.

## 6. Funnel 20Y — estado actualizado

El Funnel 20Y está **CERRADO CON GATE CI**.

- H1: 22477 FVG / 2799 OB / 702 relaciones.
- H4: 6497 / 862 / 206.
- D1: 1543 / 214 / 58.
- Sequence H1: 1460 cadenas / 3 COMPLETE.
- MTF dense: 1239 muestras / `ok_rate=1.0`.

`ok_rate=1.0` es integridad de navegación, no win rate. `3 COMPLETE` es insuficiente para declarar edge.

## 7. TNA / navegación temporal — estado actualizado

La auditoría temporal AHF tiene evidencia `PASS_TRACE_INTEGRITY` en una muestra estratificada: 750 trazas, 501 transiciones y 193 invalidaciones. Esto valida integridad del trace de esa muestra, **no** el behavioral/full-span de 20 años.

El siguiente gate es TNA behavioral/full-span.

## 8. Plan y gates vigentes

| Gate | Estado |
|---|---|
| Fase A | PASS |
| Fase B | PASS |
| Fase C | PASS |
| Fase D | PASS |
| D-extension FVG↔OB | PASS STRICT + CI |
| Funnel MTF+SEQ 20Y | PASS + CI |
| Context State contract | NORMATIVO |
| AHF implementation | IMPLEMENTADO v1 |
| TNA trace | PASS estratificado |
| TNA behavioral/full-span | PENDIENTE |
| Sequence×Context State | INSUFFICIENT_N |
| Fase E execution/backtest | BLOQUEADA hasta gates previos |
| F/G/H | PENDING |

## 9. Lo que todavía NO está terminado

1. Taxonomía completa y tests de todos los tipos de OB de la tesis.
2. Detección especializada de Breaker y BPR.
3. Lifecycle completo de mitigación/touch a nivel de ejecución.
4. Integración HTF/ITF/EXEC como grafo causal completo de producción.
5. POI → retest → entry → SL → TP como especificación de ejecución congelada.
6. Dataset causal de outcome para backtest.
7. TNA behavioral/full-span.
8. Experimentos con n suficiente para declarar edge.
9. Ablación, OOS y robustez.
10. Validación específica M5; actualmente diferida.

**No queda como deuda:** corregir BOS/CHOCH a pivotes causales; ese blocker ya fue resuelto y debe permanecer documentado como tal.

## 10. Criterios de aceptación global

### Técnica

- tests de fase en verde;
- cero regresiones de estructura no intencionales;
- cero look-ahead demostrado por tests/auditorías;
- lifecycle reconstruible;
- lineage íntegro;
- código canónico único por concepto.

### Empírica

No se declara edge por unit tests, Funnel PASS ni TNA TRACE PASS. Backtest/ablación debe comparar baseline y cohortes con metodología temporal reproducible.

## 11. Bucle Hermes

```text
AUDIT
  ↓
IMPLEMENT
  ↓
TEST
  ↓
ANALYZE
  ↓
FIX / REVERT
  ↓
RETEST
  ↓
GATE
  ↓
UPDATE SDD + .hermes-index.md + WORKLOG
  ↓
NEXT PHASE
```

Una fase solo se considera cerrada cuando código, tests, SDD, índice y bitácora describen el mismo estado.

## 12. Resultado arquitectónico esperado

Para cualquier vela histórica `t`, el motor debe poder reconstruir sin consultar información posterior a `t`:

> estructura vigente → liquidez/sweep → displacement → BOS/CHOCH/MSS → FVG/OB generado → lifecycle → lineage → Context State → navegación → retest → ejecución → outcome.

La arquitectura está preparada para que la siguiente evidencia cierre TNA behavioral/full-span y, posteriormente, permita una especificación de ejecución/backtest sin confundir integridad con edge.
