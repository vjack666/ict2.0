# SDD — Mapa de Arquitectura y Plan FVG/OB

**Proyecto:** ict2.0  
**Fecha:** 2026-08-17  
**Estado:** CONTRATO PARA HERMES

## 1. Objetivo

Evolucionar el motor existente Swing/BOS/CHOCH a un modelo ICT causal:

`Liquidity → Sweep → Displacement → BOS/CHOCH/MSS → FVG/OB → POI → Retest → Entry → SL → TP`

FVG y OB deben ser **objetos persistentes**, no booleanos. Deben conservar identidad, dirección, TF, geometría, lifecycle, timestamps de creación/confirmación/tradabilidad, mitigación, invalidación, edad y genealogía causal.

Arquitectura:

```text
DATA
  ↓
Swing → BOS → CHOCH/MSS
  ↓
Sweep → Displacement
  ↓
 ┌──────┴──────┐
 FVG           OB
 └──────┬──────┘
        ↓
 PD ARRAY / POI
 FVG | OB | Breaker | BPR
        ↓
 HTF / ITF / EXEC context
        ↓
 Retest / Touch
        ↓
 Execution
        ↓
 Learning dataset
```

## 2. Hallazgos actuales

### `tools/event.py`
Ya tiene `origin_bar`, `confirmation_bar`, `break_bar`, `price`, `parent_id` y `status`. Es la base correcta para ampliar el modelo de objetos sin romper Swing/BOS/CHOCH.

### `tools/bos.py`
Ya existe linaje BOS → Swing mediante `parent_id`. Debe reutilizarse para FVG/OB.

### `engine/fvg_poi.py`
Ya existe FVG geométrico de 3 velas y anclaje HTF. **Problema:** `_track_fvg_fill()` mantiene sólo un FVG activo por dirección; no representa múltiples FVG simultáneos ni lifecycle individual. `fvg_for_bos()` debe migrar a objetos/linaje.

### `engine/order_block.py`
Ya existe OB y `order_block_for_bos()`. **Problema crítico:** usa `close.shift(-1)` para confirmar follow-through. Esto sólo es válido si el OB queda explícitamente confirmado/tradable después de esa vela; el consumidor no puede tratar el flag de la vela origen como información disponible allí. Además `_track_ob_validity()` sólo mantiene un OB vigente.

### `engine/execution.py`
Actualmente la entrada fina se basa principalmente en swings. Debe aceptar un POI FVG/OB y esperar touch/retest antes de ejecutar.

### `.hermes-index.md`
Existe infraestructura de bitácoras y estado. Cada fase debe registrar hipótesis, cambios, pruebas, métricas, fallos y decisión siguiente.

## 3. Mapa archivo por archivo

| Archivo | Acción | Objetivo |
|---|---|---|
| `tools/event.py` | MODIFICAR | Soportar objetos FVG/OB y tiempos candidate/confirmation/tradable. |
| `tools/fvg.py` | CREAR | Tool vela-a-vela para FVG persistentes. |
| `tools/order_block.py` | CREAR | Tool vela-a-vela para OB y variantes. |
| `tools/pd_array.py` | CREAR | Contrato común FVG/OB/Breaker/BPR/POI + lifecycle. |
| `tools/relationships.py` | CREAR | Grafo de relaciones causales. |
| `detectors/fvg.py` | CREAR/REUTILIZAR | Geometría FVG pura, sin look-ahead. |
| `detectors/order_block.py` | CREAR/REUTILIZAR | OB con confirmación temporal explícita. |
| `detectors/breaker.py` | CREAR | OB invalidado + cambio estructural → Breaker. |
| `detectors/bpr.py` | CREAR | Confluencia OB+FVG. |
| `detectors/displacement.py` | AUDITAR | Evento causal consumible por FVG/OB. |
| `detectors/bos.py` | AUDITAR | Preservar parent_id y compatibilidad. |
| `detectors/choch.py` | AUDITAR | Preservar IDs y tiempos. |
| `engine/fvg_poi.py` | REFACTORIZAR | Objetos + lifecycle + lineage + HTF; mantener compatibilidad durante migración. |
| `engine/order_block.py` | REFACTORIZAR | Confirmación temporal, lifecycle individual, tipos y lineage. |
| `engine/htf_pd_index.py` | MODIFICAR | Indexar PD arrays por TF/dirección sin futuro HTF. |
| `engine/htf_narrative.py` | AUDITAR/MODIFICAR | FVG/OB como evidencia contextual, nunca OTE. |
| `engine/expediente.py` | MODIFICAR | Persistir sweep→displacement→structure→FVG/OB→POI→execution. |
| `engine/invalidation.py` | MODIFICAR | Invalidación común de FVG/OB/Breaker. |
| `engine/execution.py` | MODIFICAR | POI touch/retest→confirmación→entry; SL estructural; TP liquidez. |
| `engine/dealing_range.py` | AUDITAR | EQ/Premium/Discount sólo contexto. |
| `engine/dealing_range_eq.py` | AUDITAR | Sin OTE/Fibonacci. |
| `engine/bias_from_tools.py` | AUDITAR | No sustituir bias estructural por FVG/OB. |
| `agents/*ict*` | AUDITAR | Eliminar checks booleanos donde proceda. |
| `agents/decision*` | AUDITAR/MODIFICAR | Consumir POI, calidad y lineage; no OTE. |
| `orchestration/*` | MODIFICAR | Transportar objetos sin perder IDs/timestamps. |
| `learning/*` | MODIFICAR | Features FVG/OB + lineage + outcome + availability timestamp. |
| `scripts/smoke_motor_lectura.py` | MODIFICAR | Smoke end-to-end con FVG/OB. |
| `scripts/*backtest*` | CREAR/MODIFICAR | Ablación reproducible. |
| `tests/test_fvg*` | CREAR | Geometría + lifecycle FVG. |
| `tests/test_order_block*` | CREAR | OB + variantes + lifecycle. |
| `tests/test_breaker*` | CREAR | OB→Breaker. |
| `tests/test_bpr*` | CREAR | OB+FVG. |
| `tests/test_lineage*` | CREAR | Integridad causal. |
| `tests/test_no_lookahead*` | CREAR | Tests temporales. |
| `tests/test_execution_poi*` | CREAR | Retest→entry→SL→TP. |
| tests BOS/CHOCH existentes | PRESERVAR | Cero regresión. |

**Nota:** antes de crear cualquier archivo indicado como `CREAR/REUTILIZAR`, Hermes debe comprobar el árbol real y evitar duplicar implementaciones existentes.

## 4. Modelo de datos

### FVG

`id, direction, tf, origin_bar, confirmation_bar, tradable_time, top, bottom, mid, size, displacement_id, structure_event_id, sweep_id, state, mitigation_level, first_touch, touches_count, invalidated_at, age, quality`

### OB

`id, direction, type, source_bar, origin_bar, confirmation_bar, tradable_time, top, bottom, body_ratio, displacement_id, structure_event_id, sweep_id, state, first_touch, touches_count, invalidated_at, age, quality, parent_ob_id`

### POI

`id, tf, direction, kind(FVG|OB|BREAKER|BPR), component_ids, htf_context, lineage_ids, state, quality, tradable_time, first_touch`

## 5. Lifecycle

```text
CANDIDATE → CONFIRMED → TRADABLE → ACTIVE
                                  ├→ PARTIAL_MITIGATION
                                  ├→ TOUCHED
                                  ├→ MITIGATED
                                  ├→ INVALIDATED
                                  └→ EXPIRED/AGED
```

Cada estado debe poder reconstruirse para cualquier `t` sin consultar velas posteriores.

## 6. Integración ICT

Cadena preferente:

`liquidity → sweep → displacement → BOS/CHOCH/MSS → FVG/OB → POI → return/retest → execution confirmation`

Reglas:

1. FVG/OB aislado puede existir como objeto, pero no es automáticamente setup premium.
2. Sweep + displacement + structure + FVG/OB mejora calidad contextual; no crea un gate duro sin evidencia.
3. OB + FVG puede formar BPR.
4. OB invalidado conserva su historial y puede transformarse en Breaker cuando la tesis lo permita.
5. Entry no debe ser automáticamente el close del BOS si el contrato exige retorno al POI.
6. OTE/Fibonacci no participa.
7. EQ/Premium/Discount sólo son contexto y nunca deben volver a representar OTE.

## 7. Anti-look-ahead

Contrato universal:

`candidate_time <= confirmation_time <= tradable_time <= observation_time`

OB:

```text
bar 100: candidato
bar 101: follow-through confirma
bar 101 close: tradable
bar 102+: touch/retest posible
```

Nunca se puede usar en bar 100 información de bar 101.

FVG:

```text
bar i-2 + i-1 + i → FVG conocido al cierre de i → tradable desde i+1
```

La definición final debe fijarse mediante tests temporales antes de medir edge.

## 8. Fases de implementación

**F0 Baseline:** tests actuales, métricas Swing/BOS/CHOCH, outcome congelado, OTE ausente.  
**F1 Contratos:** objetos, IDs, estados y timestamps.  
**F2 FVG:** detector + lifecycle + tool + tests.  
**F3 OB:** detector + confirmación + tipos + lifecycle.  
**F4 Breaker/BPR:** genealogía y confluencia.  
**F5 Lineage/MTF:** Sweep/Displacement/BOS/CHOCH ↔ FVG/OB ↔ HTF/ITF/EXEC.  
**F6 Execution:** POI touch/retest → confirmation → entry → SL → TP.  
**F7 Learning:** dataset causal.  
**F8 Ablación:** baseline, +FVG, +OB, +FVG+OB, +Sweep+Displacement+FVG+OB.  
**F9 OOS/robustez:** ventanas temporales y régimen si hay datos suficientes.  
**F10 Cierre:** documentación, bitácora, índice, métricas y commit.

## 9. Aceptación

### Técnica

- 100% tests nuevos verdes.
- Tests BOS/CHOCH existentes verdes.
- 0 look-ahead.
- lifecycle reconstruible.
- lineage íntegro.
- ejecución reproducible.

### Empírica

Objetivo preferente frente al baseline:

- PF o expectancy ≥10% mejor en desarrollo.
- OOS sin degradación >5% cuando haya datos suficientes.
- Drawdown sin empeorar >10%.
- Muestra razonable de operaciones.

Si una variante no aporta edge, no se fuerza. Puede conservarse como feature descriptiva sólo si no degrada el baseline.

## 10. Bucle Hermes

`AUDIT → IMPLEMENT → TEST → BACKTEST → EVALUATE → DIAGNOSE → FIX/REVERT → REPEAT`

No se permite DONE sólo por compilar o pasar unit tests. Cada iteración registra hipótesis, archivos, pruebas, métricas, fallo, decisión y commit.

## 11. Resultado final

Para cualquier vela histórica `t`, el motor debe poder reconstruir:

> estructura vigente → liquidez tomada → displacement → BOS/CHOCH/MSS → FVG/OB generado → tipo → lifecycle → BPR/Breaker → contexto HTF/ITF/EXEC → tradable_time → touch → entrada → resultado.

Si puede reconstruir esa cadena sin mirar el futuro, el sistema queda preparado para que la IA determine qué configuraciones ICT aportan edge real.
