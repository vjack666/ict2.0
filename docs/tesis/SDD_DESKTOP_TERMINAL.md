# Terminal de escritorio ICT SYSTEM

Fecha: 2026-09-07. Dueño D2/D7, auditor D5. Diseño visual 1 seleccionado por el cliente.

## Alcance autorizado

Aplicación local con pestañas Mercado, ICT/Wyckoff, Bot mecánico, Posiciones y
Bitácora. Reutiliza `engine.mt5_operational_snapshot` y `mechanical_bot`;
no crea estrategia, probabilidad, señal ni productor alternativo.
La referencia visual es el primer concepto mostrado el 7 de septiembre.
Las cifras ilustrativas y calendario de ese concepto no son datos del producto.

## Contrato técnico

- Frontend React/Vite en `runtime/desktop_terminal/ui`, servido en loopback por
  `scripts/start_desktop_terminal.py`. Ventana independiente con Edge app mode;
  alternativa navegador local cuando ese runtime no exista.
- MT5 seleccionado explícitamente, sin terminal por omisión. Un ciclo de precios
  de 1 segundo y velas de 5 segundos conserva caché en memoria acotada.
- Motor en proceso separado, con una sola petición pendiente y recalculado
  cuando cambie una vela cerrada. No bloquea las peticiones HTTP ni el precio.
- D1/H4/H1/M15/M5/M1, exclusivamente velas cerradas para análisis. Vela abierta
  identificada para gráfico; nunca se transmite como evidencia canónica.
- Gráfico interactivo con biblioteca de canvas, sin generar PNG por tick.
- Todo estado presenta origen, timestamp, frescura y fallos explícitos.
- Transporte MT5 con offset servidor explícito: +3 h observado 2026-09-07
  comparando tick 16:13 servidor con reloj 13:13 UTC; el CLI permite ajustarlo
  por cambio de broker/DST. No modifica parquets ni el updater histórico.
  Los hashes del snapshot identifican JSON OHLCV en memoria; no certifican un dataset.
- Bot OFF al abrir, ejecución deshabilitada por defecto. Activación de ejecución
  mediante flag explícito y armado manual con cuenta visible. Nunca se arma
  ni envía una orden durante QA. Conserva contrato mecánico y can_trade=false
  del motor; falta de snapshot operativo bloquea entradas.
- API de acciones con comprobación de Host/Origin y token local, sin CORS abierto.
- Bitácora y posiciones son proyecciones de evidencia local real.
- Sin despliegue remoto, modificación de datasets, backtest ni entrenamiento.

## Criterios de aceptación

Tests con adaptadores falsos para APIs, exclusión de vela abierta, caché,
errores y acciones protegidas. Build frontend, inspección visual y navegación
de cinco pestañas en Browser. Medir latencia HTTP y tamaño de bundle. Evidencia
de MT5 real en modo lectura, sin afirmar cero latencia. Cierre con worklog,
índice, Graphify, auditoría independiente y commit selectivo local sin push.

## Addendum V2 — control manual y lectura de conflictos (2026-09-10)

La interfaz expone **Activar bot**, **Compra manual** y **Venta manual**. Activar
solo inicia el controlador. Seleccionar un lado registra `manual_direction` y
deja el estado `WAIT_STOCHASTIC`; la orden se envía únicamente tras el cruce M15.
Durante Londres, Compra manual se rechaza con `LONDON_SELL_ONLY`.

El panel debe mostrar por separado `direction_hint`, sesgo de cada TF, fase y
`phase_state` de Wyckoff, gatillo estocástico, dirección manual y autoridad de
ejecución. Un conflicto es una salida explicable y no una señal agregada.
Las FVG se diferencian por `z.direction`: alcistas en verde y bajistas en rojo,
con dirección escrita en la etiqueta y en la tabla.

## Addendum V3 — readiness explicable y fail-closed (2026-09-10)

**Armar bot** inicia exclusivamente el loop de espera; no equivale a señal ni a
orden. La posibilidad de una entrada automática se publica por separado como
`readiness.ready` y exige simultáneamente: `execution_enabled=true`, snapshot
canónico válido del símbolo y con antigüedad máxima de 20 minutos, dirección
BUY/SELL, probabilidad finita `>=0.70`, `confirmed=true` más cruce estocástico
M15 direccional sobre velas cerradas, y sesión Londres o Nueva York activa.

Cada requisito expone `passed`, `code`, `detail`, valor observado y valor
requerido. La sesión usa ventanas locales `[08:00,12:00)` con weekday y DST de
cada plaza; ICT Terminal la habilita siempre como gate de entrada. El frontend
solo presenta este contrato del servicio y falla cerrado si está ausente. Todos
los gates vuelven a evaluarse en el tick antes de cualquier `order_send`.
El motor canónico conserva `can_trade=false` por defecto; readiness no cambia
esa autoridad ni constituye promoción o señal.

## Addendum V4 — disponibilidad canónica y señal mecánica (2026-09-10)

La salud del análisis `MT5_OPERATIONAL_SNAPSHOT_V1` se presenta separada de
los seis requisitos de entrada del servicio mecánico. Un análisis vigente
no implica que exista una señal con probabilidad y confirmación autorizadas.
La ausencia de esa señal debe describirse como tal, sin afirmar que falta
el análisis canónico cuando está disponible.

La salud diagnóstica valida esquema, símbolo, estado, reloj con zona horaria,
antigüedad y cierres de las seis temporalidades contra `decision_time`.
Un fallo de feed, cálculo o vigencia impide mostrarla como válida. El cálculo
fallido admite reintentos acotados sin esperar una vela nueva.
El canal de lectura permanece separado de `runtime/mechanical_bot/latest_snapshot.json`;
no se derivan probabilidad, confirmación ni autoridad de entrada a partir del
contexto. Se conservan `OBSERVE_ONLY_NO_ORDER`, `can_trade=false` y
`entry_authorized=false`. Esta salud técnica no es certificación histórica.
