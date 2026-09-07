# 2026-09-07 — Validación demo del bot mecánico y plan EURUSD

**Departamento:** D2/D5/D7.
**Estado:** COMPLETED_READ_ONLY_DEMO_CHECK.

## Hechos comprobados

- El actualizador MT5 completó EURUSD D1/H4/H1/M15/M5/M1 desde el terminal configurado y escribió la punta local; el brief fresco se generó con M15 12:15 UTC, M5 12:30 UTC y M1 12:35 UTC.
- El Context State es BULLISH, H4 está en MID y M15 `OBSERVABLE_SETUP` tiene estructura a favor, retest observado y FVG LONG activo. No es una autorización de orden.
- El terminal correcto para EURUSD es `C:\Program Files\FundedNext MT5 Terminal\terminal64.exe`, que reporta `MetaQuotes-Demo`, cuenta 10011586708, balance/equity $4,732.57 y sin posiciones EURUSD.
- El terminal por omisión de MetaTrader5 se conectaba a `Deriv-Demo`, donde EURUSD no tenía tick. El lanzador ahora pasa de forma explícita el terminal operativo configurable.
- Prueba read-only: `execution_enabled=false`, armar → analizar → tick → apagar. El snapshot estuvo ausente, el estado quedó OFF y las posiciones no cambiaron. No hubo `order_send`.
- Stochastic M15 cerrado: K=52.21, D=34.86; el cruce precedente salió desde sobreventa, pero K ya está por encima de 20. No hay gatillo de entrada presente.

## Plan

El plan de hoy queda `WAIT_SNAPSHOT`: se vigila un nuevo cruce BUY M15 bajo 20 solo si un snapshot canónico fresco y confirmado publica BUY con probabilidad >=70%. La estrategia no inventa dicho snapshot ni SL/TP fijos.

## Verificación

`C:\Python314\python.exe -m pytest tests/test_mechanical_bot_core.py tests/test_mechanical_bot_service.py tests/test_mechanical_bot_mt5_adapter.py tests/test_mechanical_bot_dashboard.py -q` → 22 passed.

## Riesgo y siguiente acción

El dashboard se probó a nivel de servicio; el entorno automático rechazó el lanzamiento persistente en segundo plano para inspección HTTP. Cuando el productor canónico publique un snapshot válido, se puede repetir el mismo recorrido en demo con ejecución explícitamente habilitada y armar manualmente el bot.
