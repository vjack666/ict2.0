# Baseline económico PROXY_PILOT — 2022

## Resultado consolidado

| Periodo | Trades | Resueltos | Media net_R |
|---|---:|---:|---:|
| 2022 Q1 | 19 | 7 | -0,618815 |
| 2022 Q2 | 16 | 5 | -1,350170 |
| 2022 Q3 | 16 | 4 | -1,252994 |
| 2022 Q4 | 24 | 3 | -1,129482 |
| **Total** | **75** | **19** | **-1,025420** |

## Dictamen

El baseline sin IA fue negativo en las cuatro particiones trimestrales
observadas, después de spread de 1 pip, slippage de 0,3 pip y comisión de
US$5 por lote por lado. Esto es una señal fuerte contra la hipótesis de edge
en este proxy, pero no permite declarar `NO_EDGE` global: la tasa de outcomes
resueltos es baja (19/75), la cobertura histórica no coincide todavía con las
particiones completas del SDD y la procedencia de los CSV intradía continúa sin
certificación total.

**Estado:** `REVIEW` diagnóstico / `BLOCKED` para certificación global.  
**Política:** baseline sin IA; `can_trade=false`; `can_train=false`.
