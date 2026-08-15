# Primeros hallazgos — backtest del sesgo (T8)

Fecha: 2026-08-03
Símbolo: EURUSD
Timeframe: M15
k: 48 (12 horas hacia adelante)
Barras analizadas: 20,000
Runner: `PYTHONPATH=. python ict_backtest/sesgo/run_sesgo.py`
Reporte: `ict_backtest/results/sesgo/reporte_sesgo_2026-08-03.json`

## Métricas

| Categoría | Total | % del total | Aligned | % aligned |
|---|---:|---:|---:|---:|
| ALIGNED | 0 | 0.00% | 0 | — |
| PARCIAL | 18,436 | 92.18% | 17 | 0.09% |
| NO_DISPONIBLE | 1,564 | 7.82% | 0 | — |
| **Total** | **20,000** | **100%** | **17** | **0.09%** |

## Hallazgo principal

Por ahora el motor produce muy poco sesgo alineado y la señal predictiva es cercana a cero.

- No se observó ningún caso ALIGNED (D1/H4/H1 en la misma dirección).
- En los eventos PARCIAL, solo 17/18,436 tuvieron delta futuro en la dirección del bias parcial.
- El 7.82% NO_DISPONIBLE corresponde a warm-up o ausencia de sesgo vigente.

## Interpretación

Este resultado es esperable en una primera demo:

- `compute_htf_bias` aún no está calibrado.
- El criterio de alineación es estricto: exige coincidencia exacta entre D1/H4/H1.
- No se evalúa gestión post-entrada ni filtros de régimen; es solo una medición de disponibilidad.

## Próximos pasos sugeridos

- Inspeccionar la distribución de direcciones del motor (`BULLISH`/`BEARISH`/`NEUTRAL`) por timeframe.
- Probar valores alternativos de `k` y relajar el criterio de alineación.
- Agregar métricas de cobertura y vacíos por símbolo.

---

# ACTUALIZACIÓN POST-VERIFICACIÓN (2026-08-03, misma sesión)

**Verificado por instrumentación directa del motor** (`_swing_points` + `_label_swings` +
`_bias_from_swings` sobre los buffers reales D1/H4/H1 del cable, 20.000 velas EURUSD M15).
El diagnóstico original NO coincide con lo que muestra el código.

## Diferencias ANTES → DESPUÉS

| Aspecto | ANTES (hallazgo original) | DESPUÉS (verificación) |
|---------|---------------------------|------------------------|
| **Causa del 0 ALIGNED** | "Motor no calibrado, esperable en una primera demo" | **Falla estructural del voto por tramos**: los últimos 4 tramos alternan bull→bear→bull→bear → conteo 2-2 → empate → NEUTRAL perpetuo |
| **H4 / H1** | — (no se distinguía) | **100% NEUTRAL** en 18.436 eventos, con **miles de swings etiquetados**: D1=233, H4=1.268, H1=4.986 swings. El motor SÍ ve estructura; el criterio de empate la anula |
| **D1** | — | 94% NEUTRAL (17.380), 6% BULLISH (1.056), 0% BEARISH |
| **Los 17 "aciertos" de PARCIAL** | "17/18.436 velas tuvieron delta futuro en la dirección del bias parcial" | **Medición defectuosa**: `expected = bias.direction` que es **NEUTRAL** sin aligned → los 17 aciertos son velas con `future_delta == 0` exacto (coinciden con NEUTRAL), NO señal predictiva del bias |
| **Métrica T8 en PARCIAL** | Aparentaba medir predicción | **No mide nada útil**: compara contra una constante NEUTRAL en el 100% de los eventos no-alineados |
| **Tests** | — | 24/25 pasan; **falla `test_sesgo_datos.py::test_validate_m15_parquet_success`**: espera `UTC`, el código expone `UTC-naive` (bug de TZ) |

## Conclusión corregida

- El motor bias **NO es todavía el reflejo de la tesis**: no distingue tendencia de rango con el
  criterio actual de tramos. El fix es del **MOTOR** (`engine/bias/`), no del backtest
  (Ley MOTOR vs BACKTEST, punto 1: nada de decisión en el backtest).
- La medición T8 debe comparar contra la **dirección del TF mayoritario** (o por TF), no contra
  `direction` global que es NEUTRAL sin aligned.

## Próximos pasos corregidos

- [ ] **Motor**: revisar el criterio de empate en `_bias_from_swings` (ventana de tramos,
      mayoría simple vs 2-2, o peso por tamaño de tramo) — decisión de motor en `engine/`.
- [ ] **Backtest T8**: comparar la medición contra la dirección del TF mayoritario, no contra `direction`.
- [ ] **Bug TZ**: alinear `validate_m15_parquet` con el test (`UTC` vs `UTC-naive`).
- [ ] Re-correr tras los fixes y actualizar esta sección con los nuevos números.
