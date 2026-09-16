# M15_AI_SHADOW_FUNNEL_BACKTEST_V1

**Fecha:** 2026-09-15  
**Estado:** `DIAGNOSTIC_ONLY`  
**Autoridad:** `can_trade=false`

## Proposito

Medir si la IA sombra mejora el filtro de candidatos del motor M15 antes de
pasar a un backtest economico con costes, fill, SL/TP y PnL.

## Definicion

Este contrato compara:

1. **Motor solo:** `tf_outcome_v1_003`.
2. **Motor + IA sombra:** fusion seleccionada en `shadow_fusion_v1`, usando
   `failure_risk_v1` como filtro diagnostico.

La regla de seleccion diagnostica es:

```text
prediccion != failure -> candidato pasa
prediccion == failure -> candidato se evita
```

## Funnel

El embudo minimo es:

```text
TEST_OOS rows
-> London-NY proxy UTC
-> motor base selecciona
-> IA sombra selecciona
-> IA sombra selecciona en ventana
-> IA sombra selecciona no-fallos
```

La ventana Londres-NY es proxy de investigacion (`07:00-16:59 UTC`) y no
certifica sesion broker ni permiso operativo.

## Metricas

- `coverage`: proporcion de candidatos que pasan.
- `failure_rate_selected`: fallos entre candidatos aceptados.
- `failure_avoidance_recall`: porcentaje de fallos historicos evitados.
- `non_failure_capture`: porcentaje de no-fallos historicos conservados.

## Minimos diagnosticos

Para `PASS_DIAGNOSTIC_SHADOW_FUNNEL`:

- la IA evita mas fallos que el motor solo;
- la IA no aumenta la tasa de fallos entre seleccionados;
- cobertura IA `>= 10%`;
- al menos un candidato IA en ventana Londres-NY proxy.

## Limites

No es backtest economico. No incluye spread, slippage, comision, fill,
stop-loss, take-profit, horizonte economico ni PnL. No autoriza trading.
