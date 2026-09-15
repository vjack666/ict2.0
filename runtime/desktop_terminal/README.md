# ICT Terminal

Terminal local para Windows. El acceso directo `ICT Terminal` del escritorio
abre una ventana independiente con Microsoft Edge en modo aplicación. El mismo
frontend se puede abrir en `http://127.0.0.1:8790/`.

## Inicio

`C:\Python314\python.exe scripts/start_desktop_terminal.py --desktop --execution-enabled`

También se puede usar `scripts/Start-ICT-Desktop.ps1`. Una instancia ya abierta
se reutiliza. Cerrar la ventana conserva el servicio en segundo plano para
continuar el monitoreo. Para detener un inicio de consola se usa Ctrl+C.

La ventana utiliza el runtime Edge instalado; no empaqueta Chromium/Electron.
La entrega es una aplicación local lanzable, no un instalador firmado.

## Pestañas

- Mercado: EURUSD real, D1/H4/H1/M15/M5/M1, zoom/arrastre, volumen tick y zonas
  activas/parcialmente mitigadas. Los marcadores BOS vienen del motor.
- ICT/Wyckoff: Context State, microconfirmación, zonas, objetos, secuencia,
  relaciones, lineage y trazabilidad del snapshot canónico.
- Bot mecánico: estado, cuenta, análisis, armado, apagado y cierre del ciclo.
- Posiciones: posiciones reales de la cuenta y magic, sin simular operaciones.
- Bitácora: eventos de sesión y biblioteca de bitácoras, tesis y contratos.

## Tiempo y rendimiento

Precio: 1 segundo. Velas: 5 segundos. Motor: una tarea en proceso separado al
cambiar una vela cerrada; no recalcula por cada petición del navegador.
400 velas por TF y 100 eventos en memoria. Transporte incremental por versión;
la vela abierta se actualiza con ticks y queda excluida del motor.

El reloj visual del terminal puede mostrar UTC+3, pero los campos `time` de la
API Python de MT5 son epoch Unix UTC y no se corrigen con un offset de broker.
El timestamp demasiado futuro, abierto o vencido produce error fail-closed.
El terminal se selecciona con `--terminal-path`; nunca se cambia en silencio.

El snapshot guarda hashes del JSON OHLCV normalizado en memoria y commit del
generador. `provenance.status=NOT_RUN`: no certifica dataset ni reproducción
histórica. El motor conserva `can_trade=false` y `entry_authorized=false`.

## Ejecución mecánica

El inicio normal y todas las pruebas reales de esta entrega usan ejecución
deshabilitada. El flag `--execution-enabled` habilita el adaptador, pero la
interfaz exige también armado manual y el snapshot válido que consume el bot.
No se debe abrir simultáneamente otro ejecutor sobre el mismo símbolo/magic.
El productor de señal de `runtime/mechanical_bot/latest_snapshot.json` no existe aún:
el controlador conserva `WAIT_SNAPSHOT` y no fabrica probabilidad ni confirma una entrada.
La API publica por separado `canonical_snapshot_health`: valida el análisis
`MT5_OPERATIONAL_SNAPSHOT_V1`, su símbolo, política de lectura, antigüedad máxima
de 180 segundos y cierres de las seis TF. La UI diferencia análisis vigente
de señal operable pendiente. Feed no vigente o error del motor invalidan la salud;
un análisis anterior solo puede seguir vigente durante un cálculo si cumple
todos los controles temporales. Los errores del worker se reintentan con espera
de 5 a 60 segundos, sin esperar una vela nueva ni duplicar tareas pendientes.

Apagar espera el tick en curso, conserva el ciclo y no liquida posiciones.
Cerrar ciclo verifica las posiciones propias antes y después; un cierre parcial
o incierto queda en ERROR para reconciliación. No hay SL/TP por precio añadido.
La cuenta REAL queda identificada de forma permanente en la pestaña del bot.

## Desarrollo y verificación

En `runtime/desktop_terminal/ui`: `npm ci`, `npm run build`.
El servidor sirve `dist/client`; no necesita un servidor Vite en producción.
`npm run test:sites` comprueba el empaquetado heredado, sin publicar el sistema.
Tests Python: `python -m pytest tests/test_desktop_terminal.py
tests/test_mechanical_bot_core.py tests/test_mechanical_bot_service.py
tests/test_mechanical_bot_mt5_adapter.py tests/test_mechanical_bot_dashboard.py -q`.

Sites no se despliega: la API depende del terminal local y contiene estado de
cuenta. La mención de Sites no constituye solicitud de publicación remota.
