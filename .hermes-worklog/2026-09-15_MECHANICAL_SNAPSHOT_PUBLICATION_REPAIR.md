# Reparación de publicación del snapshot mecánico tras POI+Stoch M15

**Fecha:** 2026-09-15
**Misión:** restaurar una frontera de publicación ejecutable, explícita y
fail-closed para `runtime/mechanical_bot/latest_snapshot.json`.
**Departamento dueño:** D2 — ingeniería del motor diario.
**Auditoría requerida:** D5 — verificación independiente de productor,
consumidor y gates.
**Estado:** COMPLETED técnicamente, tras revisión independiente D5; no habilita
trading ni certificación científica.

## Hallazgo causal

El archivo eliminado no era una salida del flujo POI+Stoch M15: era un fixture
estático fechado `2026-09-11T00:00:00+00:00` que afirmaba `BUY`, `0.75` y
`confirmed=true`. Su eliminación junto con la integración evitó que una señal
vieja pareciera vigente, pero el publicador solo devolvía `False`; no dejaba un
motivo duradero para el consumidor u operador.

La fuente canónica conserva el contrato `OBSERVE_ONLY_NO_ORDER`. Fase 2B sigue
siendo la única ruta para una futura señal con dirección/probabilidad, pero no
es el productor de la simplificación POI+Stoch: conectarla aquí reintroduciría
confirmaciones retiradas y dejaría la ruta sin productor real.

## Cambio

`TerminalRuntime._publish_bot_snapshot()` ahora:

1. acepta únicamente un snapshot canónico `READY`, del símbolo configurado y
   con política `OBSERVE_ONLY_NO_ORDER`;
2. exige `decision_time` y `object_projection` de objetos canónicos, sin
   derivar `BUY`/`SELL`, probabilidad ni confirmación desde POI, contexto o
   estocástico;
3. ante rechazo elimina de forma segura cualquier contrato anterior y escribe
   `runtime/mechanical_bot/latest_snapshot_status.json` de esquema
   `MECHANICAL_BOT_SNAPSHOT_PUBLICATION_V1`, con `status`, `code`, `detail` y
   `failed_gates` explícitos;
4. publica mediante reemplazo atómico un contrato de observación con
   `can_trade=false`, `entry_authorized=false` y `object_projection` canónica
   sin transformarla. Esa proyección permite que el controlador POI+Stoch
   vuelva a aplicar su validación cerrada de M15; no es autorización.

## Evidencia

```text
C:\Python314\python.exe -m pytest -p no:cacheprovider tests\test_desktop_snapshot_health.py tests\test_mechanical_signal_publication.py tests\test_mechanical_signal_assessment.py tests\test_poi_stoch_evaluator.py tests\test_poi_stoch_evaluator_integration.py tests\test_mechanical_bot_service.py -q
174 passed in 1.34s

C:\Python314\python.exe -m py_compile runtime\desktop_terminal\backend.py mechanical_bot\service.py engine\poi_stoch_evaluator.py tests\test_desktop_snapshot_health.py tests\test_poi_stoch_evaluator.py tests\test_mechanical_bot_service.py
PASS
```

Las pruebas añadidas cubren: ausencia de proyección POI (bloqueada con causa),
un archivo viejo eliminado al faltar evidencia y una publicación atómica que
conserva la proyección sin inventar campos de señal. También se comprueba que
un adaptador de prueba con ejecución habilitada no puede alcanzarse cuando el
contrato conserva `can_trade=false`.

La revisión D5 detectó que el servicio llamaba al evaluador con
`check_proximity`, aunque la firma no lo admitía. El evaluador ahora incorpora
una preselección explícita que devuelve `POI_SELECTED_FOR_PRICE`, nunca una
entrada, para obtener el lado bid/ask antes de la reevaluación estricta. La
prueba focal cubre esa ruta real sin sustituir el evaluador.

## Límites y siguiente acción

No se ejecutó MT5, no se arrancó el runner y no se llamó a `order_send`. La
publicación POI no habilita trading. Una futura señal direccional con
probabilidad continúa bloqueada hasta que D4/D5 cierren con evidencia los nueve
gates de Fase 2B; los fixtures de prueba no son una certificación ni
autorización de producción.
