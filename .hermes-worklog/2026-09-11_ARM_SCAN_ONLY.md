# 2026-09-11 — Armado de escaneo con ejecución deshabilitada

**Departamento:** D2 / D5 / D7
**Estado:** COMPLETED

## Objetivo

Habilitar el botón existente `Armar bot · iniciar loop` cuando MT5 está
conectado, sin habilitar órdenes ni fabricar una señal o un snapshot.

## Cambio

- El servicio publica `adapter_configured` y permite iniciar el runner de
  observación con un adaptador MT5 conectado.
- Con `execution_enabled=false`, cada tick registra
  `EXECUTION_DISABLED_SCAN_ONLY`; no crea un ciclo, no llega a `_execute()` y
  no puede enviar una orden.
- El backend permite únicamente `arm` en ese modo. Compra, venta manual y
  cierre de ciclo continúan rechazados con `EXECUTION_DISABLED`.
- La interfaz habilita el botón de armado por `adapter_configured`, no por la
  capacidad de ejecución.

## Evidencia

- `python -m pytest tests/test_mechanical_bot_service.py tests/test_desktop_terminal.py -q`
  → `49 passed`.
- `npm run build` en `runtime/desktop_terminal/ui` → PASS.
- `graphify update .` ejecutado después del cambio.

## Riesgos y límites

Este cambio no activa una cuenta, no modifica `can_trade=false`, no restaura el
snapshot runtime ausente y no envía ninguna orden. Un restart conserva el
fail-closed: el estado armado no es una autorización persistente.

## Siguiente acción

Reiniciar el servicio local cuando se quiera cargar esta versión; usar Armar
solo para observación hasta completar los gates de ejecución de una misión
explícita.
