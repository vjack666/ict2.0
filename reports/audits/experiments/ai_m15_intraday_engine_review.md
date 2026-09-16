# Revision IA + Motor M15 Intradia

**Fecha:** 2026-09-15  
**Estado:** `REVIEW_READY_FOR_SHADOW_DATASET`  
**Trading:** `can_trade=false`, `entry_authorized=false`

## Que se logro

Se conecto una pieza que estaba desalineada:

- El ensamblador M15 (`engine.m15_evidence_assembler`) produce evidencia rica:
  `{present, time, source}`.
- El evaluador mecanico (`engine.mechanical_signal_assessment`) esperaba
  booleanos planos: `true/false`.

Ahora el evaluador entiende ambos formatos. En simple: antes el motor podia
traer una carpeta completa con sello, hora y fuente, pero el portero solo
aceptaba una tarjeta que dijera `true`. Ahora el portero lee la carpeta
completa.

## Antes

La cadena M15 completa tenia esta intencion:

```
H4/H1 alineados -> sweep -> displacement -> BOS/CHOCH -> FVG/OB -> retest
```

Pero habia una friccion tecnica:

```
assembler: {"sweep": {"present": true, "time": "...", "source": "..."}}
assessor:  espera {"sweep": true}
```

Eso podia bloquear una evidencia valida por forma, no por contenido.

## Ahora

`assess_mechanical_signal()` acepta:

```json
{"sweep": true}
```

y tambien:

```json
{"sweep": {"present": true, "time": "2026-09-11T14:15:00+00:00", "source": "canonical_sweep"}}
```

Si toda la cadena esta presente, devuelve `CANDIDATE_SETUP` diagnostico.
Si falta algo, sigue fallando cerrado con causa explicita:

- sin sweep -> `NO_SWEEP`
- sin displacement -> `NO_DISPLACEMENT`
- sin BOS/CHOCH -> `NO_BOS`
- sin FVG/OB -> `NO_FVG_OR_OB`
- sin retest -> `WAIT_RETEST`

## Relacion con la IA

La IA todavia no cambia el motor. La IA mira lo que el motor diagnostica y
aprende a responder:

- este candidato se parece a fallos pasados;
- este candidato se parece a casos mejores;
- no tengo suficiente evidencia, mejor abstenerse.

La IA es filtro sombra, no boton de compra/venta.

## Estado del snapshot actual

Existe `runtime/mechanical_bot/latest_snapshot.json`, pero su `asof_time` es
`2026-09-11T00:00:00+00:00`. Para la revision del 2026-09-15 esta stale. No
se usa como prueba de setup vivo ni de oportunidad actual.

## Pruebas

```text
python -m pytest tests/test_mechanical_signal_assessment.py
6 passed

python -m pytest tests/test_poi_stoch_evaluator.py tests/test_poi_stoch_evaluator_integration.py
106 passed
```

## Dictamen

`PASS_BRIDGE_MECHANICS`: la union mecanica entre evidencia M15 rica y evaluador
canonico quedo funcional.

`REVIEW_DATASET_REQUIRED`: aun falta construir el dataset sombra que una:

```
M15 chain -> POI+Stoch -> AI shadow score -> outcome real
```

Ese dataset es el siguiente paso antes de afirmar que la IA mejora la busqueda
de una oportunidad intradia Londres-NY.

## Lista de trabajo

1. Materializar `M15_INTRADAY_SHADOW_DATASET_V1` con datos locales inmutables.
2. Etiquetar cada decision_time con cadena M15, POI+Stoch, score IA y outcome.
3. Separar TRAIN/VALIDATION/TEST_OOS sin fuga temporal.
4. Elegir thresholds solo en VALIDATION.
5. Evaluar una sola vez en TEST_OOS.
6. Si falla, redisenar features o thresholds y repetir el loop sin promover.
7. Si pasa, abrir revision independiente; no activar trading automaticamente.
