# Preregistro — Enmienda PIT: la vela de confirmación no se evalúa contra su propio objeto

## Motivo

T7d sigue dando 0 setups completos tras la enmienda H6 (commit `de24d68`).
Diagnóstico con datos reales del 2025-01-17: el gate que bloquea ya NO es el
orden causal del DAG, sino la guarda PIT del lifecycle
(`_bar_after_tradable` en `engine/lifecycle.py`), que usa comparación
`bar_time >= tradable_time`.

El productor fija `tradable_time` = timestamp de la vela de confirmación
(contrato: "los eventos nacen, se confirman y se vuelven tradables al cierre
de su vela"). La vela de confirmación se observa EXACTAMENTE en ese timestamp,
por lo que `>=` la deja pasar y el objeto es evaluado contra la vela que lo
CREA:

- `OB_H4_180_BULL`: la vela de followthrough [08:00, 12:00) se observa a las
  12:00 == `tradable_time` 12:00 → evaluada → `PARTIALLY_MITIGATED` a las
  12:00 (la vela que confirma el OB lo mitiga).
- `FVG_M15_2710_BULL`: la tercera vela [14:45, 15:00) se observa a las
  15:00 == `tradable_time` 15:00 → evaluada → `PARTIALLY_MITIGATED` (su low
  ES el límite de la zona: `zone_low = third.low`, siempre la toca).
- `FVG_M15_2711_BULL`: idéntico a las 15:15.

A las 15:30 ningún POI/refinement queda ACTIVE → 0 setups. La población real
existe (el setup 15:15/15:30 es válido), pero el lifecycle la elimina por
auto-mitigación de la vela de confirmación.

Esta enmienda se registra ANTES de tocar código, conforme al protocolo de
cambios de contrato congelados.

## Cambio de contrato

La guarda PIT pasa de `bar_time >= tradable_time` a `bar_time > tradable_time`
(estrictamente después). Consecuencia: la vela de confirmación —la única vela
observada exactamente en `tradable_time`— queda excluida de la evaluación del
objeto que ella misma confirma.

- Se mantiene point-in-time: ninguna vela anterior a `tradable_time` toca el
  objeto (sigue excluida).
- Se mantiene la autoridad por TF: solo la vela del `authority_tf` decide el
  estado oficial; las observaciones LTF no mutan estado.
- Se mantiene fail-closed: sin timestamp válido no se asume "después".
- NO se relaja ningún otro gate: POI/FVG ACTIVE, contexto HTF alineado,
  relación FVG↔OB, lineage hijo→padre, FULL/PREFIX, determinismo, H6.

## Justificación técnica

La vela de confirmación es la vela que COMPLETA la formación del objeto:

- OB: la vela de followthrough valida el order block (patrón
  `OB_FOOTPRINT_FOLLOWTHROUGH`). Su rango recorre la zona del source candle
  por construcción; evaluarla contra el OB que confirma es auto-mitigación.
- FVG: la tercera vela define `zone_low` (bull) / `zone_high` (bear); su low
  ES el borde de la zona, así que SIEMPRE la toca. Evaluarla es
  auto-mitigación garantizada.

Semánticamente, un objeto no puede ser mitigado por la vela que lo crea: la
mitigación requiere una vela POSTERIOR a la confirmación. Como `tradable_time`
es el timestamp de la vela de confirmación y cada vela se observa una sola vez
en su timestamp, `>` excluye exactamente esa vela y ninguna otra. Los tests
existentes ya respetan esta convención (nunca evalúan la vela de confirmación:
empiezan en bar+1), por lo que el cambio no altera casos cubiertos.

## Alcance

- `engine/lifecycle.py`: `_bar_after_tradable` — `bt >= tt` → `bt > tt`
  (actualizar docstring).
- `tests/test_lifecycle.py`: añadir un caso que evalúe la vela de confirmación
  y verifique que NO transiciona (antes: `PARTIALLY_MITIGATED` espurio).
- `docs/contratos/CONTRATO_HISTORICAL_EVENT_OBJECT_PRODUCER_V1.md`: reflejar
  que la vela de confirmación no se evalúa contra su propio objeto.

## Gates tras el cambio

1. Determinismo e IDs estables.
2. Lineage causal correcto (padre existe, `parent_time <= child_time`, sin
   referencias a futuro).
3. Lifecycle correcto: la vela de confirmación no transiciona su objeto;
   POI/FVG ACTIVE en T.
4. FULL/PREFIX exacto en 25/50/75/90%.
5. Setups completos > 0, elegibles > 0, episodios > 0.
6. Ningún setup aparece antes de que todas sus evidencias estén disponibles.
7. Sin look-ahead: la frontera X/Y tiene pruebas automáticas.

Si T7d vuelve a dar 0 setups tras este cambio, se diagnostica el siguiente
gate sin relajar reglas para fabricar población.

## Prohibiciones

- No se mide edge, beneficio ni WR en esta etapa.
- No se optimiza sobre resultados.
- No se entrena IA todavía.
- No se opera MT5 ni se emiten órdenes.
- No se amplía la ventana ni se seleccionan meses por resultados.