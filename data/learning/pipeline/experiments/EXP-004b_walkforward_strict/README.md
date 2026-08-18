# EXP-004b — Strict Walk-Forward

## Resultado

**GATE_3_STRICT: PASS**

- Folds válidos: 9
- PR-AUC medio OOS: 0.317
- Base rate: 0.191
- Lift: 1.66×
- Criterio formal: lift ≥ 1.5× base y ≥ 3 folds

## Protocolo

- Modelo: GradientBoostingClassifier (n=200, depth=3)
- Features: 11 canónicas
- Embargo: 7 días
- Purging: activo
- Horizonte del label: H1 ≈ 1 día
- Folds: expanding window por año
- Universo: CHOCH unique EURUSD H1/H4, 2012–2022
- Label: `label_ep`

## Resultado H1

PR-AUC medio: **0.280** (std 0.07).

El comportamiento es temporalmente inestable: 2016 y 2017 muestran lift >1.5×, mientras 2015 y 2020 son cercanos a 1.0×.

## H4

Sólo 2 folds, con 1–2 positivos por fold. Se considera **ruido estadístico** y no se utiliza para decidir.

## Interpretación

El modelo aporta ranking OOS marginalmente superior al azar en H1, pero **no constituye evidencia de edge operativo fuerte**.

El resultado está lejos del ROC-AUC in-sample ~0.798 y confirma que el split aleatorio sobreestimaba el rendimiento.

El universo es `CHOCH unique`, no `choch_real`; por tanto este experimento evalúa ranking de calidad entre candidatos CHOCH, no la validez del filtro de producción `choch_real`.

## Decisión

No se habilita un peso de IA del 15% basándose sólo en este experimento.

Siguiente validación recomendada: **ablación de `score_n`** y comparación controlada de features. No reinterpretar el PASS formal como PASS operativo.

Artefacto fuente:
`walkforward_strict.json`
