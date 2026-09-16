# Setup Grammar Supervision v1

**Fecha:** 2026-09-15  
**Estado:** `READY_FOR_MATERIALIZATION_DESIGN`  
**Trading:** `can_trade=false`

## Que se decidio

La intuicion del usuario es correcta: las neuronas actuales no construyen
setups. Hoy hacen principalmente:

```text
setup ya formado -> score/outcome/failure
```

El siguiente salto debe ser:

```text
tesis ICT -> piezas del setup -> diagnostico de pieza debil -> outcome
```

## Antes

La red ve features como:

- `sequence_depth`
- `context_bucket`
- `h1_alignment`
- `h4_location`
- `sequence_stages`
- outcome `continuation/reversal/failure`

Eso ayuda, pero es demasiado plano. No le ensena con claridad si fallo por:

- POI mal contextualizado;
- falta de retest;
- displacement debil;
- entrada tarde;
- wrong-side premium/discount;
- exec TF equivocado;
- killzone incorrecta.

## Ahora propuesto

Se abre la linea `SETUP_GRAMMAR_SUPERVISION_V1`.

La red debe aprender una rubrica de setup:

| Pieza | Pregunta simple |
| --- | --- |
| HTF | ¿El mapa grande esta alineado? |
| Sweep | ¿Hubo caza de liquidez real? |
| Displacement | ¿La salida fue fuerte o floja? |
| BOS/CHOCH | ¿La estructura confirmo? |
| FVG/OB | ¿Hay zona usable? |
| Retest | ¿El precio volvio a la zona? |
| POI | ¿La zona tiene narrativa o es geometria suelta? |
| Exec TF | ¿Entrada/SL/TP estan en la temporalidad correcta? |

## Investigacion

No hace falta investigar afuera para la primera version: la tesis local cubre
la columna vertebral. Pero si se quieren entrenar conceptos mas finos, quedan
items `RESEARCH_REQUIRED`:

- Killzones London/NY con conversion broker/UTC exacta.
- M3 como exec TF fino.
- Breaker, Mitigation Block y BPR como PD Arrays entrenables.

Todo hallazgo externo debe convertirse en contrato local antes de alimentar a
las neuronas.

## Siguiente trabajo

Materializar `SETUP_GRAMMAR_DATASET_V1` y entrenar `setup_quality_v1`.

Comparacion futura:

```text
motor solo
motor + failure_risk_v1
motor + setup_quality_v1
motor + ambas neuronas
```

## Dictamen

`READY_FOR_MATERIALIZATION_DESIGN`: la tesis ya puede guiar el entrenamiento,
pero todavia falta convertirla en dataset causal con etiquetas intermedias.
