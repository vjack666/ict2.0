# Plan de trading demo EURUSD — 2026-09-07

**Estado:** WAIT_SNAPSHOT / SIN ORDEN
**Cuenta verificada:** MetaQuotes-Demo 10011586708
**Política del motor:** `can_trade=false`

## Lectura actual con velas cerradas

El feed MT5 se refrescó hoy. El brief canónico generado a las 07:36 Ecuador usó cierres hasta M15 12:15 UTC, M5 12:30 UTC y M1 12:35 UTC. EURUSD cerró M15 en 1.16241.

El Context State es `BULLISH`, la ubicación H4 es `MID` y M15 muestra `OBSERVABLE_SETUP`: estructura a favor, retest observado y FVG LONG activo con medio 1.16263. M5 acompaña el sesgo, M1 no; eso queda como diagnóstico y no puede borrar el contexto HTF.

El estocástico M15 cerrado 14,3,3 quedó K=52.21 y D=34.86, con K previo=27.73 y D previo=27.59. El cruce previo salió desde sobreventa, pero K ya está por encima de 20. No existe gatillo mecánico de compra en este instante. Tampoco existe `runtime/mechanical_bot/latest_snapshot.json` fresco con dirección, probabilidad >=70% y confirmación; el bot debe abstenerse.

## Plan de hoy

1. Mantener el bot apagado hasta publicar un snapshot canónico fresco de EURUSD.
2. La única vigilancia alcista permitida por el contexto sería: snapshot BUY confirmado >=70% y un nuevo cruce alcista M15 desde debajo de 20. La orden se evaluaría en el M1 siguiente.
3. Una venta requeriría su propio snapshot SELL confirmado >=70% y el cruce bajista M15 desde arriba de 80; el contexto actual no la respalda.
4. M5/M1 se muestran como diagnóstico. No se calculan SL ni TP fijos: la gestión demo usa la canasta dinámica definida (0.10/0.20/0.30, +$60 y -2% del balance capturado).
5. Si no aparece el snapshot y el cruce correspondiente, no hay operación.

## Prueba demo realizada

El servicio se conectó de forma read-only al terminal configurado de MetaQuotes-Demo. Se ejecutó armar → analizar → tick → apagar con `execution_enabled=false`: terminó OFF, no encontró snapshot y las posiciones antes/después fueron idénticas (vacías para EURUSD). No se envió ninguna orden.

## Pendiente para una entrada demo real

El productor canónico debe escribir `runtime/mechanical_bot/latest_snapshot.json` con dirección, probabilidad, confirmación y `asof_time` frescos. No se reemplazará con una señal inventada.
