# Prueba DEMO autorizada y reparación del envío MT5

AGENTE: Codex principal.
DEPARTAMENTO: D2 Ingeniería / D5 Assurance / D7 Delivery.
TAREA: iniciar el bot, investigar y demostrar su flujo con órdenes DEMO autorizadas.
STATUS: COMPLETED para transporte DEMO; activación del backend principal pendiente.

## Autorización y alcance

El usuario autorizó explícitamente órdenes DEMO para demostrar el flujo completo.
Se verificó MetaQuotes-Demo antes de actuar. La prueba técnica de transporte se
aisló de la estrategia: 0.01 lotes EURUSD, magic 26091099, cuenta DEMO fijada por
login y servidor, cuenta hedging, una apertura y cierre inmediato. No se cambió
el snapshot ni se inventó probabilidad/confirmación. La prueba no valida edge ni
equivale a una entrada automática autorizada por el motor.

## Evidencia operativa

- Instancia existente: ARM vía API produjo ARMED; el tick produjo WAIT_SIGNAL y
  registró OUTSIDE_ENTRY_WINDOW, correlación 09fc954f-c899-4371-a113-6a6b9bc55866.
  DISARM dejó el bot OFF. No había señal mecánica; estaba fuera de sesión.
- Primer envío de prueba: retcode 10013 Invalid request, sin posición creada.
  La respuesta MT5 contenía TradeRequest con todos los campos vacíos.
- Diagnóstico sin órdenes mediante order_check en MetaTrader5 5.0.5735:
  mapping posicional => retcode 0 / Done, named request=mapping => 10013 y
  request vacío. El test antiguo modelaba erróneamente una firma keyword-only.
- Reparación en el adaptador canónico: order_send(request) posicional, sin
  fallback ni reintento automático de firmas después de enviar.
- Segunda prueba con adaptador corregido: PASS_OPEN_CLOSE_RECONCILED.
  Ticket 152614915488; apertura deal 152466467184 y cierre deal 152466467189;
  ambos retcode 10009, volumen 0.01. Historial confirmó entry 0 y entry 1,
  ambas a 1.16135 y resultado DEMO neto 0.00, sin comisión/swap/fee.
- Cero posiciones de prueba restantes. La posición previa SELL 0.58,
  ticket 152613134698, mantuvo identidad, lado y volumen.
- 40 tests PASS: adaptador MT5, salud canónica y terminal. La prueba del
  adaptador exige mapping posicional y exactamente una llamada de envío.
- Bitácora de requests/results con hashes y resultados reconciliados en
  .hermes-state/snapshot-audit-baseline/demo_transport_blackbox.jsonl.
  Evidencia estructurada: reports/audits/runtime/demo_transport_20260910.json.

La firma coincide con la [documentación oficial de MetaQuotes](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py).
La aceptación real y la reconciliación del historial son la evidencia de esta
instalación, no solo el test con adaptador falso.

## Límites y siguiente acción

La revisión automática volvió a rechazar el reinicio del PID 10500 con demo-test,
execution-enabled y comprobación DEMO/OFF. No se alteró el proceso por ese comando.
El bot original quedó OFF después de la prueba de espera; no queda un loop armado.
La prueba de transporte usó el adaptador corregido en un proceso de una sola
ejecución. La instancia principal aún carga código anterior: reinicio pendiente
para activar tanto snapshot_health como la corrección de order_send.

No se demuestra flujo automático de señal a orden: sigue faltando productor de
señal válido y sesión activa. No se cambiaron gates, estrategia ni posiciones
ajenas. Autoauditoría con pruebas y broker; auditor independiente final no
disponible por límite de uso de los agentes. Sin push.
