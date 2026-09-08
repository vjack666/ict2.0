# SDD — Bot mecánico MT5 con estocástico M15

**Estado:** implementación local, separado del motor inteligente.
**Fecha:** 2026-09-06.
**Autoridad:** instrucción explícita del cliente.
**Ámbito:** `mechanical_bot/` y `scripts/mechanical_bot_*`; no modifica `engine/`.

## Propósito

El bot recibe un *snapshot* externo de dirección y probabilidad. Es una capa de ejecución mecánica independiente: el motor sigue siendo de observación y conserva `can_trade=false`.

El snapshot debe incluir `symbol`, `direction`, `probability`, `confirmed` y `asof_time`. Puede transportar `context_state`, `zones`, `bos` y `m5_m1`; el dashboard los muestra como evidencia del productor canónico. Si falta cualquiera de los campos de decisión, está vencido (más de 20 minutos), no está confirmado o su probabilidad es menor de 0.70, el bot no abre una posición.

## Entrada

| Dirección del snapshot | Confirmación final M15 (14,3,3) | Acción |
| --- | --- | --- |
| BUY, probabilidad >= 0.70 | %K cruza por encima de %D desde zona <=20 | Compra 0.10 |
| SELL, probabilidad >= 0.70 | %K cruza por debajo de %D desde zona >=80 | Venta 0.10 |

M5 y M1 son diagnóstico visible. No se leen para permitir, rechazar o cancelar una entrada.

## Ciclo y riesgo

Cada ciclo conserva precio inicial, hora de la señal y balance al armarlo. Solo admite tres órdenes: 0.10 inicial, 0.20 a 20 pips adversos y 0.30 a 40 pips adversos, siempre medidos desde la primera entrada.

Se cierran únicamente las posiciones del símbolo y `magic_number` del bot cuando el P/L agregado llega a +60 USD o a -2% del balance inicial. Tras el cierre el mismo snapshot no puede reabrir el ciclo. Si el proceso se reinicia, se restaura el ciclo como `OFF`; posiciones faltantes generan `ERROR` y nunca una reentrada inferida.

## Ejecución y cuenta

El dashboard inicia `OFF`. El adaptador de MT5 requiere `--execution-enabled` y el botón **Encender bot** antes de que el hilo de bajo consumo (15 s, sin busy loop) pueda enviar acciones. Al detectar una cuenta real, deja una advertencia permanente con cuenta, servidor, saldo y equity; no bloquea por tipo de cuenta. La orden se considera válida solo con retcode MT5 `DONE` o `DONE_PARTIAL`.

No existe SL/TP por precio inventado. Los cierres son agregados por beneficio o pérdida flotante. Todos los eventos y el estado del ciclo se guardan localmente en JSONL/JSON bajo `.hermes-state/`.

## Estados

`OFF`, `ARMED`, `WAIT_SIGNAL`, `WAIT_STOCHASTIC`, `INITIAL_ENTRY`, `REENTRY_1`, `REENTRY_2`, `CLOSING`, `CLOSED`, `ERROR`.

## Verificación

### Prueba DEMO y caja negra — 2026-09-07

Autorización del usuario: dejar bot encendido para probar y registrar decisiones,
envíos y errores. La prueba se fija a login/servidor DEMO y bloquea el envío si
cambia la cuenta o el tipo. El armado puede esperar un snapshot aún ausente;
esto no elimina confirmación, probabilidad >=0.70, frescura ni cruce M15.

Nuevas entradas solo lunes a viernes en [08:00,12:00) Europe/London o
America/New_York, conforme a las ventanas documentadas del bot mensual.
ZoneInfo resuelve DST, sin importar código del backtest. La interfaz muestra
America/Guayaquil; trazas conservan UTC. Gestión de ciclos y cierres continúa
fuera de sesión. Para 2026-09-08 equivalen a 02:00–06:00 y 07:00–11:00 Guayaquil.

Caja negra durable: decisión y abstención, snapshot/huella, estocástico,
correlación de acción y petición previa a order_send, resultado MT5 completo,
last_error y excepción cuando corresponde. Fallo de escritura previo impide
envío. Ninguna prueba técnica necesita enviar una operación al broker.

### Integración del terminal local — 2026-09-07

El terminal de escritorio conserva esta estrategia y añade controles de servicio
serializados. Un snapshot exige símbolo, confirmación booleana estricta,
probabilidad finita dentro de [0, 1] y timestamp no futuro. OFF/ERROR/CLOSING
no producen entradas. Apagar espera el tick activo y conserva el ciclo.
Los cierres cotejan posiciones propias antes y después: una respuesta parcial
no acredita un ciclo cerrado. Los accesos nativos MT5 se protegen con RLock.
El productor de latest_snapshot.json sigue pendiente; WAIT_SNAPSHOT bloquea el
armado. No se generaron órdenes reales para verificar esta integración.

Las pruebas focales cubren frescura y confirmación del snapshot, umbral 70%, cruces M15, independencia M5/M1, escalera 0.10/0.20/0.30, cierres agregados, filtro magic/símbolo, recuperación, retcodes MT5 y estados demo/real.
