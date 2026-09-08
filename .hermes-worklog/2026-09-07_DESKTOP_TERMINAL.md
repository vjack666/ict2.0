# Terminal de escritorio — diseño 1

AGENTE: Codex director; bot_integrity, terminal_ui y execution_audit.
DEPARTAMENTO: D7 Delivery, D2 Ingeniería; revisión independiente D5 Assurance.
TAREA: entregar terminal local ligero para MT5 y lectura ICT/Wyckoff canónica.
STATUS: COMPLETED para la aplicación; ejecución operativa pendiente de productor.

## Entrega

React/Vite y lightweight-charts en ventana Edge app, sin empaquetar Electron.
Acceso directo del escritorio ICT Terminal; servicio 127.0.0.1:8790.
Cinco pestañas: Mercado, ICT/Wyckoff, Bot mecánico, Posiciones y Bitácora.
Lectura de contexto de gobierno, índice, bitácoras, tesis ICT/Wyckoff y contratos,
Engram y consulta Graphify; no se afirma lectura íntegra de todos los datasets.

Precio cada segundo, velas cada cinco segundos, 400 velas por TF, seis TF,
100 eventos y transporte incremental. Motor en proceso separado solo ante
cambio de velas cerradas. Vela abierta excluida de decisiones. Zonas y BOS
proceden del motor. Fallos/frescura se muestran explícitamente.

Bot integrado con flag de ejecución y armado manual; validación estricta de
snapshot, serialización y reconciliación de cierres parciales. No cambia la
estrategia ni crea un productor probabilístico. can_trade=false en diagnóstico.
HTTP limitado a loopback, Host/Origin/token, cuerpo limitado y documentos
permitidos; dependencias y dist ignorados por Git.

## Evidencia

Pruebas focales de terminal y bot: 47 PASS antes de ampliar regresión mensual.
La ampliación a tres suites mensuales no pudo recolectarse: literales finales
`\\n` en backtest/mechanical_bot_monthly.py:419 y
scripts/report_mechanical_bot_monthly.py:229 causan SyntaxError. Confirmados
también mediante git show HEAD, anteriores a esta misión. No son imports del
terminal. Se conserva su código y no se declara PASS de regresión mensual.
Empaquetado: 4 PASS; build Vite correcto, JavaScript 128.02 KB gzip.
QA visual y correcciones en runtime/desktop_terminal/ui/design-qa.md.
Auditoría independiente execution_audit: READY para QA de lectura; observación
de node_modules sin ignore corregida y verificada con git check-ignore.

reports/desktop_terminal/live_validation.json: muestra 2026-09-07 23:52 UTC,
DEMO, conexión READY, tick 2.1 s, seis TF x 400, bot OFF, cero posiciones.
20 peticiones incrementales: p50 10.368 ms, p95 24.231 ms, 11.7 KB aprox.
Motor 5552.8 ms en proceso separado: no es latencia del gráfico cacheado.
Son mediciones locales, no garantía de demora cero. QA envió cero órdenes.

## Riesgos y siguiente acción

Falta productor de runtime/mechanical_bot/latest_snapshot.json: WAIT_SNAPSHOT
impide armado. La capacidad mecánica se prueba con dobles, no con órdenes demo
o reales. Esta entrega no acredita edge, promoción ni procedencia histórica.
Offset del servidor +3 h configurado explícitamente; revisar si cambia broker/DST.
Cerrar ventana conserva servicio; no ejecutar otro controlador del mismo magic.
Entrega local lanzable, sin instalador firmado ni publicación Sites.
Siguiente acción operativa: abrir acceso directo y observar; habilitar ejecución
requiere resolver primero el contrato/productor y los gates vigentes.

ARCHIVOS: runtime/desktop_terminal/, scripts/start_desktop_terminal.py,
scripts/Start-ICT-Desktop.ps1, mechanical_bot/{core,service,mt5_adapter}.py,
tests/test_desktop_terminal.py y pruebas mecánicas, SDD y este cierre.
