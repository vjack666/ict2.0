# FAILURE_TAXONOMY_V1

**Fecha:** 2026-09-15  
**Owner:** CAIO Hermes / Assurance  
**Estado:** ACTIVO PARA MATERIALIZACION DIAGNOSTICA  
**Alcance:** `failure_anatomy_v1`  
**Politica:** `can_trade=false`, `shadow_mode=true`

## 1. Proposito

Este contrato define la taxonomia inicial de causas candidatas de fallo para la
linea de aprendizaje `failure_anatomy_v1`.

La taxonomia no autoriza trading, no cambia labels historicos y no convierte un
resultado de laboratorio en edge economico. Su funcion es diagnostica:

```text
features_at_t -> failure_drivers -> failure_risk
```

## 2. Target principal

El target binario de la linea es:

```text
is_failure = 1 si label_end_6 == failure
is_failure = 0 si label_end_6 in {continuation, reversal}
```

`label_end_6` se usa solo como etiqueta supervisada. Ninguna feature del modelo
puede derivarse de outcomes futuros.

## 3. Drivers autorizados

### HTF_CONFLICT

La direccion de la secuencia entra en conflicto con sesgos o alineacion HTF
observables en `features_at_t`.

Ejemplos:

- secuencia alcista con bias HTF bajista;
- secuencia bajista con bias HTF alcista;
- `h1_alignment=AGAINST`.

### ADVERSE_CONTEXT

El contexto alrededor de la secuencia es adverso o explicitamente en contra.

Ejemplos:

- `context_bucket=AGAINST`;
- `h1_alignment=AGAINST`.

### IMMATURE_SEQUENCE

La secuencia aun no muestra suficiente madurez estructural antes del outcome.

Ejemplos:

- `sequence_depth < 4`;
- falta una etapa critica esperada en la secuencia.

### CONSTRAINT_CONTRADICTION

Las restricciones operativas contradicen la direccion de la secuencia.

Ejemplos:

- secuencia alcista con `allow_long=false`;
- secuencia bajista con `allow_short=false`;
- `direction_hint` contrario a `sequence_direction`.

### WEAK_STRUCTURE

La estructura observada antes del resultado es debil o incompleta.

Ejemplos:

- falta `DISPLACEMENT`;
- falta `STRUCTURE`;
- no hay confirmacion estructural suficiente en la representacion causal.

### LOW_SUPPORT_REGIME

El patron pertenece a un regimen con soporte insuficiente en TRAIN/DESIGN.

Se calcula con combinaciones de contexto ajustadas solo sobre TRAIN. Si una
combinacion aparece poco o no aparece en TRAIN, el driver queda activo para
advertir que el modelo debe abstenerse o tratarlo con cautela.

### DIRECTIONAL_AMBIGUITY

La direccion no tiene autoridad clara en las features disponibles antes del
resultado.

Ejemplos:

- `direction_hint=UNKNOWN`;
- bias `MIXED`, `NEUTRAL` o `UNKNOWN`;
- mezcla simultanea de senales alcistas y bajistas.

### UNKNOWN

Se usa cuando ningun driver anterior se activa. No significa que no exista una
causa real; significa que esta taxonomia v1 no la puede explicar con las
features actuales.

## 4. Regla causal

Todos los drivers deben calcularse exclusivamente desde campos disponibles
antes del resultado:

```text
event_time / features_at_t / constraints / context_inputs / context_layers / sequence
```

Prohibido usar:

```text
label_end_6
label_end_12
label_end_24
label_end_48
predicciones OOS posteriores
metricas agregadas calculadas sobre HOLDOUT para ajustar features
```

La unica excepcion es `is_failure`, que es el target supervisado y no una
feature.

## 5. Estado de interpretacion

Esta taxonomia queda autorizada para:

- materializar `failure_anatomy_v1`;
- entrenar un modelo diagnostico `failure_risk_v1`;
- auditar drivers y calibracion;
- preparar una fusion futura en Shadow Mode.

No queda autorizada para:

- trading;
- DEMO;
- live signals;
- promocion a produccion;
- cambio de `can_trade=false`.
