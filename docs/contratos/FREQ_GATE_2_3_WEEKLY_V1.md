# FREQ_GATE_2_3_WEEKLY_V1

**Estado:** `DRAFT_FOR_MEASUREMENT`
**Ambito:** laboratorio local, diagnostico determinista
**No autoridad:** `can_trade=false`, `entry_authorized=false`

## Proposito

Medir si las familias PO3, Turtle Soup y Silver Bullet producen una poblacion
natural combinada de aproximadamente dos a tres oportunidades intradia por
semana calendario. Este gate no ajusta parametros ni declara rentabilidad.

## Unidad de conteo

Un evento economico se identifica como:

```text
symbol | decision_time_utc | direction
```

Un evento puede tener varias `strategy_family`; se cuenta por familia y una
sola vez en el total combinado. Si dos candidatos comparten la llave, el
artefacto debe conservar el solapamiento y justificar la deduplicacion.

## Entradas minimas

Cada candidato debe tener `candidate_id`, `strategy_family`, `decision_time`,
`symbol`, `direction`, `split`, `source_lineage`, `sweep_evidence`,
`structure_evidence`, `pd_array_evidence`, `killzone`, `execution_evidence`
y los flags `can_trade=false`, `entry_authorized=false`.

Una evidencia ausente se registra como `EVIDENCE_MISSING`; no se convierte en
un `False` silencioso ni permite inferir que el modelo fue rechazado.

## Medidas obligatorias

- Frecuencia por semana calendario, por semana con decision points y por
  semana con datos efectivamente cubiertos. Los denominadores nunca se mezclan.
- Conteo por familia, combinado deduplicado, semana, mes, ano, sesion,
  direccion, simbolo y split `TRAIN`/`VALIDATION`/`TEST_OOS`.
- Funnel por familia: universo, contexto, liquidez, POI, sweep, displacement,
  BOS/CHOCH, FVG/OB, retorno, ejecucion y candidato.
- Solapamientos de familias y razones de exclusion por gate.

## Veredicto

`PASS_FREQUENCY_DIAGNOSTIC` requiere que la frecuencia combinada deduplicada
se informe en semanas calendario y quede en el intervalo de 2 a 3. No es un
requisito para modificar reglas: si el resultado es menor, el estado es
`INSUFFICIENT_FREQUENCY`; si es mayor, se revisa concentracion y calidad antes
de sacar conclusiones.

Ningun veredicto de este gate es `PASS_EDGE`, autorizacion de entrada, orden,
paper trading ni promocion de modelo.

## Lectura Misión 7

La ventana 2022-03-07..2022-03-13 no satisface todavía este gate. Es una
aceptación funcional del cableado, no una medición formal de frecuencia:

- población inicial: 121 episodios;
- IA shadow aceptó 40 para análisis;
- meta investigativa: 2–3 oportunidades/semana;
- no hubo deduplicación final por `symbol|decision_time|direction` combinando
  familias;
- PO3 apareció completo en 121/121, lo que indica exceso de amplitud para un
  gate de frecuencia.

Veredicto actual: `REVIEW_CALIBRATION_REQUIRED`. La próxima corrida debe
reducir población por calidad y deduplicar familias antes de evaluar
`PASS_FREQUENCY_DIAGNOSTIC`.
