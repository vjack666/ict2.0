# 2026-09-06 — Bot mecánico MT5 / entrega local

**Departamento:** D2/D5/D7.
**Estado:** COMPLETED_LOCAL_IMPLEMENTATION.
**Autoridad:** plan explícito del cliente.

## Resultado

Se añadió `mechanical_bot/` como ejecutor separado del motor. Consume solamente el contrato de snapshot `direction/probability/confirmed/asof_time`, exige 70% y usa el cruce estocástico M15 14,3,3 como última confirmación. M5/M1 se conservan como diagnóstico sin veto.

El adaptador MT5 filtra por símbolo y magic number, valida retcodes de ejecución, conserva el ciclo tras reinicio y falla a `ERROR` si falta una posición propia restaurada. El dashboard loopback muestra Context State, zonas, BOS y M5/M1 del snapshot, y ofrece análisis, encendido, apagado y cierre manual; el lanzador tiene PID único y `--execution-enabled` como requisito explícito antes de activar el hilo de 15 s.

## Evidencia

`python -m pytest tests/test_mechanical_bot_core.py tests/test_mechanical_bot_service.py tests/test_mechanical_bot_mt5_adapter.py tests/test_mechanical_bot_dashboard.py -q` → 21 passed.

No se conectó ni se envió una orden a MT5 durante esta implementación. No hubo push, promoción ni cambio del `can_trade=false` del motor.

## Riesgo y siguiente acción

El bot se abstiene hasta que un productor autorizado escriba un snapshot fresco y confirmado en `runtime/mechanical_bot/latest_snapshot.json`; el sistema inteligente actual no genera una probabilidad operativa certificada. La ejecución debe comenzar en demo usando el lanzador y verificar la cuenta que muestra el dashboard antes de armar el ciclo.
