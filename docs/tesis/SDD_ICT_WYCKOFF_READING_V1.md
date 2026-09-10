# SDD — Lectura ICT/Wyckoff por temporalidad V1

**Fecha:** 2026-09-10  
**Estado:** COMPLETO PARA REVISIÓN · lectura contextual, no autoridad de órdenes

## Regla principal

D1, H4, H1 y M15 se publican por separado. Ningún promedio resuelve una contradicción. `direction_hint` pertenece a Context State; Wyckoff explica fase y relación, pero no muta ese campo ni autoriza entradas.

## Matriz de lectura

| Salida | Significado | Acción |
|---|---|---|
| PRO_TREND / ALIGNED | ICT y Wyckoff comparables coinciden | contexto favorable |
| TRANSITION / CONFLICT | oposición sin evidencia suficiente | esperar |
| COUNTERTREND / CONFLICT | oposición más evento Wyckoff explícito | vigilar confirmación M15 |
| NEUTRAL / UNRESOLVED | falta dirección comparable | abstener |

Eventos mínimos para `COUNTERTREND`: SPRING, UPTHRUST, UTAD, SOS, SOW o RANGE_BREAK, con polaridad compatible y confirmación temporal cerrada. No basta cualquier evento.

## Contratendencia

Un M15 bajista contra H4/D1 alcista es una hipótesis contratendencia. El motor puede leerla y mantenerla en espera, pero no debe convertirla en señal automática. El operador puede elegir manualmente un lado bajo el SDD del bot; esa autorización queda separada del contexto.

## Estado auditado

El 2026-09-10 se observó D1 `MIXED`/compresión, H4 `BULLISH`, M15 `BEARISH` y Wyckoff `DISTRIBUTION` con `CONFLICT`. Es evidencia mixta, no una dirección única.

## Verificación

Cada snapshot debe conservar TF, hora, estructura, fase, evento, alineación, conflicto, explicación y política. Tests deben demostrar que Wyckoff no muta `direction_hint`, que ausencia de evento produce `TRANSITION`, y que `COUNTERTREND` requiere evidencia válida.
