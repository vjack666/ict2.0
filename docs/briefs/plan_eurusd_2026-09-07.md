# Plan diagnóstico EURUSD — lunes 2026-09-07

> Datos locales MT5 cerrados hasta 2026-09-04 23:59 UTC. El mercado estaba cerrado al generar este mapa; debe refrescarse al abrir antes de usarlo.
> `can_trade=false`. No es una orden ni calcula entrada, SL o TP.


## EURUSD

- **Precio actual (M15 cierre):** `1.16132`
- **Datos hasta:** D1 2026-09-04 00:00 · H4 2026-09-04 20:00 · H1 2026-09-04 23:00 · M15 2026-09-04 23:45 · M5 2026-09-04 23:55 · M1 2026-09-04 23:59

- **Context State:** `BULLISH` · location=`MID` · fuente=`engine.mtf_navigation.MTFNavigator`
- **Snapshot operativo MT5:** `READY` · objetos históricos=`3428` · TF faltantes=`[]` · provenance=`PASS`
- **Sesgo diagnóstico legacy:** `BEARISH` (fuente D1+H4) · D1=BEARISH H4=BEARISH H1=BEARISH
- **Wyckoff:** fase=`ACCUMULATION` · estado=`PRO_TREND` · authority_tf=`D1` · alignment=`ALIGNED`
- Wyckoff conflicto: `False` · `proceso Wyckoff y dirección ICT compatibles`
### Semana en curso (OHLC del mismo feed MT5)
- Ventana: `2026-08-31T00:00:00+00:00` → `2026-09-04T23:45:00+00:00` · barras M15=`431`
- Open `1.15763` · High `1.16413` · Low `1.15663` · Close `1.16132`
- Lectura: rango y posición semanal; no es PnL ni una instrucción de entrada.
### LTF / exec M15 (motor diario)
- Estado: `WAIT_LTF_CONFIRMATION`
- Dirección heredada del contexto: `BULLISH`
- Contexto permitido: `True` · razón: `context_state_constraints_allow`
- Sequence canónica: disponible=`True` · refs=`441` · depth=`4`
- Estructura a favor: `False` · zonas canónicas: `41` · retest: `OBSERVED`
- Marcadores legacy de DataFrame (no promocionan estado): zona=`True` · retest=`False`
- Política: `OBSERVE_ONLY_NO_ORDER` — no es entry ni autorización de operación.

### LTF microestructura MT5 (M5/M1 — solo confirmación)
- `M5`: disponible=`True` · asof=`2026-09-04 23:45:00+00:00` · trend=`BEARISH` · BOS=`0` · momentum=`-1`
- `M1`: disponible=`True` · asof=`2026-09-04 23:45:00+00:00` · trend=`BEARISH` · BOS=`0` · momentum=`1`
- Confirmación M5/M1 para dirección `BULLISH`: available=`True` · confirmed=`False` · score=`-2` · detalle=`{'M5': 'against', 'M1': 'against'}`
- Regla: M5/M1 confirman o esperan; no cambian el Context State ni autorizan órdenes.

### Zona (dealing range H4)
- Zona premium/discount: `MID`
- Rango H4: high `1.16413` · low `1.15849` · mid `1.16131`

### Liquidez objetivo (BSL/SSL H4)
- SSL: `1.09008` — **NO FIAR** (fuera de rango del precio actual; dato de origen inconsistente)

### PD arrays activos (M15 — zonas de reacción)
- FVG LONG: mid `1.16130` tier=T2 · fill=bullish_unfilled (0.0 ATR del precio)
- FVG SHORT: mid `1.16149` tier=T2 · fill=bullish_unfilled (-0.3 ATR del precio)

### Sweeps recientes (M15)

### Killzones a vigilar (sesión NY)
- **London Open**: 02:00-05:00 ET  →  01:00-04:00 Ecuador (ago)
- **New York AM**: 08:30-11:00 ET  →  07:30-10:00 Ecuador (ago)
- **New York PM**: 13:00-16:00 ET  →  12:00-15:00 Ecuador (ago)
- **Silver Bullet**: 10:00-11:00 ET / 14:00-15:00 ET  →  09:00-10:00 / 13:00-14:00 Ecuador (ago)

### Setups a VIGILAR (regla dura: entry en retorno a zona, no close del BOS)
- Sesgo alcista, precio neutro: vigilar reacción en discount para buscar long.

*sección generada en 17.1s*

## Plan operativo de observación

1. Al abrir Londres, refrescar MT5 y confirmar que D1/H4/H1 no cambiaron.
2. Mantener el Context State HTF como referencia; M15 solo debe mostrar sweep y displacement/BOS confirmado antes de pasar a espera LTF.
3. M5/M1 confirman el retest o mantienen `WAIT_LTF_CONFIRMATION`; no pueden borrar por sí solos D1/H4/H1.
4. Si falta confirmación, abstenerse: no hay escenario ejecutable.
