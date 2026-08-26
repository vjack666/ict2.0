# EXP-004B-01 — Generalización Temporal (PRE-REGISTRO BORRADOR — NO EJECUTAR)

> **Estado:** BORRADOR DE INVENTARIO Y PRE-REGISTRO. Preparado tras la certificación
> independiente de `EXP-WYCKOFF-ICT-01` (`CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`).
> **NO se ejecuta sin nueva autorización explícita del CEO (Ruben).**

## 0. Contexto y justificación

`EXP-SEQ-CTX-01` cerró como `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE` (625
filas totales, 397 HOLDOUT, 8 instrumentos, 3/6 celdas < n≥30). `EXP-WYCKOFF-ICT-01`
cerró como `FEASIBILITY_FAIL_INSUFFICIENT_N` (H1 TOTAL=515 < 778; máx celda primaria
361 << 389). Ambos fracasos son de **potencia/densidad de observaciones**, no de
edge negativo demostrado.

`EXP-004B-01` aborda una dimensión distinta: **generalización temporal** — ¿el comportamiento
de las celdas (ALIGNED/NEUTRAL/AGAINST × CONFLICT/NON_CONFLICT) se mantiene estable
a través de sub-ventanas temporales dentro de los bloques DESIGN/VALIDATION/HOLDOUT,
o hay deriva/estacionalidad que invalide la agregación por bloque?

## 1. Pregunta de investigación

¿La distribución de la celda primaria `ICT × CONFLICT/NON_CONFLICT` es estable
(tasa de reversión/continuación dentro de banda) cuando se particiona cada bloque
en sub-ventanas temporales (p.ej. anuales), o muestra deriva sistemática que
requeriría modelado por régimen?

## 2. Unidad de observación

Igual que `EXP-WYCKOFF-ICT-01`: nodo k de `SequentialChain` (k≥4), anclado en
`nodes[k].bar`, deduplicado por `(bar_k, direction)`, bucket relativo a
`sequence_direction` (reusa `exp_seq_ctx_01_dataset.context_bucket`), flag
`CONFLICT` del `WyckoffSnapshot`. **Solo conteos / proporciones por celda;
sin outcomes de PnL en esta fase de factibilidad de generalización.**

## 3. Diseño (PROPUESTA — requiere aprobación)

- **Universo fijado:** EURUSD 20Y Dukascopy `datasets/eurusd_dukascopy_20y/` H1/H4/D1
  (igual que preflight previo; ampliación de universo vedada salvo nueva autorización).
- **Partición temporal:** cada bloque DESIGN/VALIDATION/HOLDOUT subdividido en
  ventanas de 1 año (o trimestres), conservando la separación estricta de bloques.
- **Métrica:** tasa de `CONFLICT` y de `reversal/continuation` (vía `_label` de
  `exp_seq_ctx_01_dataset`, sin PnL) por celda primaria y por sub-ventana.
- **Estabilidad:** test de homogeneidad (Chi-cuadrado de proporciones entre
  sub-ventanas) por celda; IC Wilson 95% bootstrap 2000, seed 42.
- **Gate de suficiencia:** cada sub-ventana × celda debe alcanzar n≥30 para que la
  comparación sea válida; si no, la sub-ventana se reporta como `BLOCKED` (sin inferencia).

## 4. Hipótesis congelada (a completar antes de ejecutar)

- H0: la proporción de `CONFLICT` (y de reversión) es igual entre sub-ventanas de un
  mismo bloque, para cada celda primaria.
- HA: existe deriva temporal significativa (rechazo de H0 con corrección Holm/Bonferroni).
- Gate: n_subventana≥30 por celda; IC 95% no cruza 0 para la diferencia máx entre
  sub-ventanas; ventanas idénticas de SL/TP/horizonte.

## 5. Potencia (PRELIMINAR — pendiente cálculo)

Dado que H1 TOTAL=515 y la celda máx=361, una partición anual (≤20 sub-ventanas) dejará
la mayoría de sub-ventanas × celda muy por debajo de n≥30. **Esto sugiere que
EXP-004B-01, con el universo fijado, probablemente también sea INSUFICIENTE en
potencia por celda**, y requeriría (a) concentrarse solo en celdas agregadas
(NEUTRAL vs no-NEUTRAL, o ICT global) o (b) nueva autorización de universo.
El cálculo exacto de n por sub-ventana queda pendiente de aprobación.

## 6. Salvaguardas

- `can_train=false`, `can_trade=false`.
- Sin backtest, sin IA, sin descarga/modificación de datasets.
- Sin cambiar n/MDE/horizontes/buckets tras ver conteos.
- Reproducción limpia desde commit fijado; `generator_commit` real en el JSON.
- Separación DESIGN/VALIDATION/HOLDOUT estricta.

## 7. Entregables (al ejecutar, no ahora)

- `reports/audits/experiments/exp004b_01/generalization_temporal.json`
- `reports/audits/experiments/exp004b_01/gate_homogeneity.json`
- Worklog y actualización de índice/blockers.

---

**NO EJECUTAR SIN NUEVA AUTORIZACIÓN DEL CEO.**
