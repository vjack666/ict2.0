# M15 AI Shadow Funnel + Diagnostic Backtest v1

**Fecha:** 2026-09-15
**Estado:** `REVIEW_DIAGNOSTIC_BACKTEST`
**Politica:** `can_trade=false`, `entry_authorized=false`, `shadow_mode=true`

## Resumen simple

Se hizo el embudo y un backtest diagnostico con las neuronas en sombra. En palabras simples: el motor propone candidatos, la IA decide si los dejaria pasar o los rechazaria, y luego medimos contra el resultado historico.

Esto todavia no es backtest economico de dinero: no incluye spread, slippage, comision, fill, SL/TP ni PnL.

## Imagenes

![Funnel M15 AI Shadow](C:/Users/v_jac/Desktop/ICT SYSTEM/reports/audits/experiments/ai/m15_ai_shadow_funnel_v1.png)

![Backtest diagnostico motor vs IA](C:/Users/v_jac/Desktop/ICT SYSTEM/reports/audits/experiments/ai/m15_ai_shadow_backtest_v1.png)

![Matriz de confusion IA sombra](C:/Users/v_jac/Desktop/ICT SYSTEM/reports/audits/experiments/ai/m15_ai_shadow_confusion_v1.png)

## Candidato neuronal usado

```json
{
  "loop_iteration": 1,
  "design": "failure_boost",
  "risk_source": "raw",
  "alpha": 0.15,
  "threshold": 0.3,
  "multiplier": 1.0
}
```

## Resultado TEST_OOS

| Metrica | Motor solo | Motor + IA sombra |
| --- | ---: | ---: |
| Cobertura seleccionada | 73.7% | 68.4% |
| Tasa de fallos entre seleccionados | 35.7% | 36.5% |
| Fallos evitados | 23.1% | 26.9% |
| Captura de no-fallos | 72.0% | 66.0% |

## Ventana Londres-NY proxy

Se uso una ventana diagnostica UTC `7:00-16:59`. En TEST_OOS la IA sombra selecciono `31` candidatos dentro de esa ventana y capturo `19` no-fallos.

## Lectura tecnica

La IA sombra mejora la deteccion de la clase `failure` frente al motor base en el dictamen de fusion previo. En este funnel/backtest diagnostico se mide el efecto como filtro: si predice `failure`, el candidato se evita; si predice `continuation` o `reversal`, el candidato pasa.

## Dictamen

El funnel queda en REVIEW: hay evidencia util, pero no alcanza para declarar mejora diagnostica estable bajo los minimos definidos.

## Limites

- No hay permiso de trade.
- No hay backtest economico todavia.
- No se activo MT5, DEMO ni live.
- La IA no modifica el motor; solo filtra en sombra.

## Siguiente paso

Como el estado es REVIEW, el siguiente paso no es activar backtest economico todavia. Primero se debe redisenar el filtro con TRAIN/VALIDATION para bajar la tasa de fallos seleccionados sin destruir la captura de no-fallos. Solo despues de un nuevo candidato congelado se vuelve a evaluar TEST_OOS.
