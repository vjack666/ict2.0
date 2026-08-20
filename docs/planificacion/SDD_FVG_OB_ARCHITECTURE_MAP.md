# SDD — Mapa de Arquitectura y Plan FVG/OB

**Proyecto:** `ict2.0`  
**Estado:** DOCUMENTO NORMATIVO VIVO — sincronizado hasta Fase D  
**Última sincronización:** 2026-08-18  
**Regla:** este SDD se actualiza al cerrar cada fase, experimento arquitectónico o cambio de contrato relevante.

## 1. Objetivo

Evolucionar el motor existente Swing/BOS/CHOCH a un modelo ICT causal donde FVG y Order Block sean objetos persistentes, trazables y temporalmente seguros.

Cadena objetivo:

`Liquidity → Sweep → Displacement → BOS/CHOCH/MSS → FVG/OB → POI → Retest → Entry → SL → TP → Outcome`

**Estado real por fases:**

- Fase A — Fundaciones: `PASS`.
- Fase B — Contratos de dominio FVG/OB: `PASS`.
- Fase C — Detección canónica FVG/OB: `PASS`.
- Fase D — Relación causal y lineage: `PASS`.
- Fase E — Ejecución: `READY`.
- Fase F/G/H: `PENDING`.

FVG/OB deben conservar identidad, dirección, TF, geometría, lifecycle, timestamps de candidate/confirmation/tradable, mitigación, invalidación, edad y lineage.

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
   POI / contexto HTF-ITF-EXEC
         ↓
   Retest / Touch
         ↓
   Execution
         ↓
   Outcome / Learning dataset
```

La arquitectura actual separa explícitamente:

1. **Contrato de objeto** — `engine/market_object.py`.
2. **Detección** — `engine/detectors/fvg.py` y `engine/detectors/ob.py`.
3. **Lineage** — `engine/lineage.py`.
4. **Tests** — contratos, detectores y relaciones temporales.

No se mezclan detección, ejecución y aprendizaje en Fases B-D.

## 3. Estado implementado y hallazgos actualizados

### `engine/market_object.py`

Es el contrato canónico de `MarketObject`.

Ya soporta:

- `FVG`, `ORDER_BLOCK`, `BREAKER`, `BPR` y eventos estructurales;
- dirección `-1/0/1`;
- `origin_tf`, `role`, geometría y estado;
- `candidate_bar/time`, `confirmation_bar/time`, `tradable_bar/time`;
- `first_touch`, `invalidated`, `mitigation`, `age`;
- `parent_object` y `related_objects`;
- invariantes de temporalidad y lineage.

Gate B quedó validado con 13 tests.

### `engine/detectors/fvg.py`

Detector canónico de FVG de tres velas.

- Bullish: `low[i] > high[i-2]`.
- Bearish: `high[i] < low[i-2]`.
- Confirmación/tradabilidad sólo cuando la tercera vela está cerrada.
- Devuelve `MarketObject`, no un booleano.
- Los tests de Fase C incluyen invariancia por prefijo para impedir look-ahead.

Gate C quedó validado con la suite en verde.

### `engine/detectors/ob.py`

Detector canónico de OB basado en:

`footprint candle + closed follow-through`.

La vela huella debe cumplir el `min_body_ratio` y el follow-through debe cerrar rompiendo el extremo de la huella. La tradabilidad comienza con la confirmación cerrada.

**Importante:** esto cubre el OB canónico de Fase C; **no significa todavía que todos los tipos especializados de la tesis estén implementados**. Breaker/BPR están presentes en el contrato de dominio, pero requieren fases/detectores específicos posteriores.

### `engine/lineage.py`

Implementa:

- `CausalLink` inmutable;
- `link(parent, child, relation)`;
- `validate_links(...)`;
- `trace_setup_lineage(signal)`.

Garantías:

- parent y child son distintos;
- `parent_bar <= child_bar`;
- si existen timestamps, `parent_time <= child_time`;
- no se permiten enlaces duplicados;
- `bar_index` es obligatorio para crear lineage;
- la cadena se valida por origen (`parent_object`), no por proximidad temporal.

Gate D quedó validado con 27 tests.

## 4. Modelo de datos vigente

### FVG

```text
id
direction
origin_tf
role
zone_high
zone_low
creation_time
candidate_bar / candidate_time
confirmation_bar / confirmation_time
tradable_bar / tradable_time
state
mitigation_level
first_touch / first_touch_time
touch_count
invalidated_bar / invalidated_time
age_bars
parent_object
related_objects
meta
```

### OB

```text
id
direction
type
origin_tf
role
zone_high
zone_low
creation_time
candidate_bar / candidate_time
confirmation_bar / confirmation_time
tradable_bar / tradable_time
state
quality_score
parent_object
related_objects
meta
```

La taxonomía completa de OB queda explícitamente pendiente de formalización contra la tesis antes de etiquetar variantes adicionales.

## 5. Lifecycle vigente

El contrato de estados es:

```text
CREATED
   ↓
ACTIVE
   ├── PARTIALLY_MITIGATED
   │       └── MITIGATED
   ├── MITIGATED
   ├── INVALIDATED
   ├── EXPIRED
   └── CONSUMED
```

Las transiciones se controlan mediante `transition_to()` y no se permite saltar arbitrariamente entre estados.

La semántica completa de touch/retest y ejecución se cerrará en Fase E.

## 6. Integración ICT vigente

La cadena causal canónica que el lineage puede representar es:

`LIQUIDITY → SWEEP → DISPLACE → BOS → POI/REFINEMENT → RETURN`

Dentro del producto FVG/OB, los objetos pueden quedar relacionados con esa cadena mediante `parent_object`/`CausalLink`.

Reglas vigentes:

1. Un FVG/OB aislado es un objeto, no un setup automático.
2. Sweep + displacement + estructura + FVG/OB es contexto y no una garantía de edge.
3. La relación causal debe ser explícita; no se infiere sólo por cercanía temporal.
4. Breaker/BPR no se consideran detectores terminados sólo porque existan en `ObjectType`.
5. Entrada, SL y TP quedan fuera de Fases B-D.
6. OTE/Fibonacci están prohibidos.
7. EQ/Premium/Discount, si se conservan, son contexto y no sustituyen la lógica ICT de FVG/OB.

## 7. Anti-look-ahead universal

Contrato base:

`candidate_time <= confirmation_time <= tradable_time <= observation_time`

Y a nivel de barras:

`candidate_bar <= confirmation_bar <= tradable_bar <= observation_bar`

### FVG

```text
bar i-2 + i-1 + i
        ↓
FVG conocido cuando i cierra
        ↓
consumible desde ese punto según el contrato
```

### OB

```text
bar i-1 = footprint candidate
bar i   = closed follow-through
bar i   = confirmation/tradable
bar i+1 ... = touch/retest posible
```

### Lineage

```text
parent.bar_index <= child.bar_index
parent_time <= child_time
```

Cualquier violación debe producir fallo de test y bloquear el Gate.

## 8. Plan y gates vigentes

### Fase 0 — Auditoría

`PASS`

### Fase A — Fundaciones

`PASS` — CI reproducible e importabilidad del motor.

### Fase B — Contratos de dominio FVG/OB

`PASS` — 13 tests.

### Fase C — Detección

`PASS` — 20 tests; FVG + OB canónicos y anti-look-ahead por prefijo.

### Fase D — Relación causal / lineage

`PASS` — 27 tests; `CausalLink`, orden temporal, resolución de padres y duplicados.

### Fase E — Ejecución

`READY`.

Alcance previsto:

`POI → retest/touch → confirmación → entry → SL → TP`

sin mirar datos futuros y sin convertir la aparición del objeto en entrada automática.

### Fase F — Aprendizaje / ablación

`PENDING`.

### Fase G — OOS / robustez

`PENDING`.

### Fase H — Cierre

`PENDING`.

## 9. Archivo por archivo — estado real

| Archivo | Estado | Próposito |
| --- | --- | --- |
| `engine/market_object.py` | IMPLEMENTADO | contrato de objetos y lifecycle |
| `engine/detectors/fvg.py` | IMPLEMENTADO | FVG canónico causal |
| `engine/detectors/ob.py` | IMPLEMENTADO | OB canónico con follow-through cerrado |
| `engine/lineage.py` | IMPLEMENTADO | relaciones causales y auditoría de lineage |
| `tests/test_market_object_pd_contract.py` | IMPLEMENTADO | contrato de objetos |
| `tests/test_phase_c_detectors.py` | IMPLEMENTADO | detectores FVG/OB + anti-look-ahead |
| `tests/test_phase_d_lineage.py` | IMPLEMENTADO | causalidad y temporalidad |
| `docs/FASE_B_CONTRATO_DOMINIO_FVG_OB.md` | VIGENTE | especificación B |
| `docs/FASE_C_DETECCION_FVG_OB.md` | VIGENTE | especificación C |
| `docs/FASE_D_RELACION_CAUSAL.md` | VIGENTE | especificación D |
| `.hermes-index.md` | VIGENTE | estado maestro |
| `.hermes-worklog/` | VIGENTE | evidencia histórica |

Los archivos del árbol original como `engine/fvg_poi.py` y `engine/order_block.py` se consideran **legacy/compatibilidad** hasta que una auditoría específica demuestre que pueden eliminarse o migrarse. No deben convertirse silenciosamente en una segunda implementación normativa.

## 10. Lo que todavía NO está terminado

1. Taxonomía completa y tests de todos los tipos de OB de la tesis.
2. Detección especializada de Breaker y BPR.
3. Lifecycle completo de mitigación/touch a nivel de ejecución.
4. Integración HTF/ITF/EXEC como grafo causal completo.
5. POI → retest → entry → SL → TP.
6. Dataset causal y outcome.
7. Ablación y aprendizaje.
8. OOS y robustez.
9. Validación específica M5; actualmente M5 está diferido.

## 11. Criterios de aceptación global

### Técnica

- 100% de tests de fase en verde.
- Cero regresiones de BOS/CHOCH.
- Cero look-ahead demostrado por tests.
- Lifecycle reconstruible.
- Lineage íntegro y verificable.
- Código canónico único por concepto.

### Empírica

No se declara edge por unit tests. Cuando se llegue a backtest/ablación se compararán baseline, +FVG, +OB y combinaciones causales con una metodología temporal reproducible.

## 12. Bucle Hermes

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

Una fase sólo se considera cerrada cuando el código, los tests, el SDD, el índice y la bitácora describen el mismo estado.

## 13. Resultado arquitectónico esperado

Para cualquier vela histórica `t`, el motor debe poder reconstruir, sin consultar información posterior a `t`:

> estructura vigente → liquidez/sweep → displacement → BOS/CHOCH/MSS → FVG/OB generado → tipo → lifecycle → lineage → POI → retest → ejecución → outcome.

La arquitectura queda preparada para que Fase E añada ejecución y, posteriormente, Fase F determine qué configuraciones aportan edge real.
