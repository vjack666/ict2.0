# EXP-SEQ-CTX-01B — expansión muestral preregistrada

**Estado:** PREREGISTRADO; pendiente de ejecución local
**Relacionado:** [`EXP_SEQ_CTX_01.md`](EXP_SEQ_CTX_01.md)
**Propósito:** evaluar si la insuficiencia de `depth>=4` puede resolverse con
una población más amplia, sin cambiar retrospectivamente la hipótesis primaria.

## Decisión metodológica

El resultado `depth>=4` de EXP-SEQ-CTX-01 queda congelado como análisis
primario: `CTX_ALIGNED=13`, `CTX_AGAINST=33`, `CTX_NEUTRAL=7`, por lo que es
`INSUFFICIENT_N` y no permite inferencia.

La variante secundaria fija antes de la ejecución:

- universo: cadenas `canonical_bos` con `depth>=3`;
- deduplicación: una cadena por `structure_bar`, igual que el experimento base;
- dataset: `datasets/eurusd_dukascopy_20y`, EURUSD H1/H4/D1, snapshot existente;
- contexto: `MTFNavigator` y los mismos buckets `ALIGNED/AGAINST/NEUTRAL`;
- outcomes: movimiento firmado del close en `+6/+12/+24/+48` barras;
- sin EMA, ATR como sesgo, OTE, entry, stop, PnL ni optimización;
- gate obligatorio: causal FULL-vs-PREFIX `PASS` y TNA behavioral/full-span `PASS`;
- objetivo de suficiencia: al menos 30 observaciones en `ALIGNED` y 30 en
  `AGAINST` en el conjunto elegible. Si no se alcanza, el resultado sigue siendo
  `INSUFFICIENT_N`.

Cambiar `depth>=4` a `depth>=3` cambia explícitamente la población estudiada;
no se presenta como confirmación del resultado primario ni como edge.

## Control temporal OOS / walk-forward

La configuración se fija sin ajuste a los resultados:

| Bloque | Ventana de estructura | Uso |
|---|---|---|
| DESIGN | 2006-01-01 a 2015-12-31 | descripción inicial, no tuning automático |
| VALIDATION | 2016-01-01 a 2020-12-31 | comprobación cronológica de estabilidad |
| HOLDOUT | 2021-01-01 a 2025-12-31 | evaluación final sin tocar umbrales |

Cada bloque exige que el horizonte `+48` permanezca dentro de su propio límite;
se excluyen eventos cuyo outcome cruce el límite del bloque. El script reporta
conteos por bloque y pooled, además de tasas y medias. No existe entrenamiento
de parámetros: OOS aquí significa evaluación cronológica de una especificación
congelada, no validación de un modelo ajustado.

## Criterio de lectura

- `n>=30` en ambos buckets pooled solo habilita describir la distribución;
- se reportan por separado los conteos y resultados de cada bloque temporal;
- una diferencia positiva no se convierte en edge, señal, autorización de
  backtest ni promoción;
- cualquier inestabilidad, signo contrario o muestra insuficiente se conserva
  como resultado negativo;
- no se preparan datos para entrenamiento IA mientras el protocolo no produzca
  evidencia suficiente y reproducible. Si se prepara un manifest posterior,
  deberá conservar `can_trade=false` y permanecer offline/shadow.

## Artefactos previstos

- `scripts/lab/experiments/exp_seq_ctx_01b_oos.py`;
- `reports/audits/experiments/seq_ctx_01b_oos/report.json`;
- `reports/audits/experiments/seq_ctx_01b_oos/report.md`.

La ejecución es local y no modifica datasets. El resultado se considera
`PASS_SAMPLE_SUFFICIENT` solo para descripción comparativa si se cumplen los
gates y el mínimo pooled; no habilita inferencia causal ni edge. De lo contrario
es `INSUFFICIENT_N` o `BLOCKED`.
