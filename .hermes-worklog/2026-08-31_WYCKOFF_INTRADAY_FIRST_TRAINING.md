# Primer entrenamiento Wyckoff intradía H1→M15 + ICT

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex / CAIO con auditoría CRO.
- **DEPARTAMENTO:** D3 IA, D4 Datos y D5 Assurance.
- **TAREA:** construir y entrenar por primera vez un corpus intradía de
  2006–2010 usando Wyckoff H1/M15 combinado con confirmaciones ICT M15.
- **MODO:** `LOCAL_ONLY`.

## STATUS

`DIAGNOSTIC_ONLY_COMPLETED` — el ajuste fue ejecutado y es reproducible a
nivel de artefacto. No es `TRAINING_ELIGIBLE`, no demuestra edge y no autoriza
Shadow MT5 ni órdenes.

## Cambios controlados

1. Se reutilizó `OutcomeClassifier` y su softmax determinista; se añadió el
   perfil explícito `INTRADAY_FEATURE_NAMES`, sin segunda registry ni política.
2. Se creó el addendum de preregistro
   `docs/experimentos/EXP_WYCKOFF_ICT_INTRADAY_ADDENDUM.md` porque el
   preregistro original era H1/H4/D1 y prohibía IA.
3. Se descargó M15 histórico bid de Dukascopy por meses en un dataset separado;
   MT5 no fue leído para el entrenamiento.
4. Se materializaron features cerradas: Wyckoff H1/M15 y BOS, CHOCH,
   displacement, FVG y sweep ICT en M15.
5. La etiqueta quedó congelada en +12 velas M15 (3 horas), comparando el
   movimiento firmado del close contra la mediana del rango de las 20 barras
   previas.

## Evidencia de datos

- 60 archivos mensuales, 125.169 velas M15.
- Rango observado: 2006-01-01 22:00 UTC a 2010-12-31 21:45 UTC.
- 0 timestamps duplicados; 0 filas OHLC/volumen inválidas.
- 3 huecos no intradía continuos de fuente, conservados sin rellenar:
  2008-12-25, cambio de año 2008/2009 y 2009-08-18/19.
- Fuente: EURUSD spot bid Dukascopy; volumen conservado como campo del
  proveedor, sin interpretarlo como volumen centralizado.

## Resultado del entrenamiento

- Corpus: 53.761 candidatos, 53.761 IDs únicos.
- Clases: `continuation=15.232`, `reversal=16.249`, `failure=22.280`.
- Split temporal 60/20/20: TRAIN 32.256, VALIDATION 10.752, TEST/OOS 10.753.
- TRAIN: accuracy `0.428912`, log-loss `1.075941`.
- VALIDATION: accuracy `0.398624`, log-loss `1.087645`.
- TEST/OOS diagnóstico: accuracy `0.402678`, log-loss `1.090112`.
- Artefacto final post-commit: `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_train_postcommit_32a3a2e.json`.
- Corpus: `reports/audits/experiments/ai/wyckoff_intraday_2006_2010.jsonl`.
- Hash del artefacto final: `283fecb7f4b99348afcc840757f7468ea381359bf8a14db10c1acf13f2c58fa3`.
- Hash del corpus: `7a610960d3035282db7a0e620b66c4312c66137c1b5f52ff3badab7237da9922`.
- Código fuente del artefacto final: commit `32a3a2e89cb03de62e4dd78f1aa597925ccf36a7`.
- Verificación: hash del artefacto autoconsistente; corpus idéntico al primer
  ajuste; métricas idénticas; features sin campos futuros detectables; orden
  temporal estricto; `fit_executed=true`. El artefacto inicial se conserva como
  evidencia de la salvaguarda anti-sobrescritura, pero no es el artefacto final
  por haber sido generado antes del commit.

## Interpretación

La cadena técnica ya funciona: datos M15 → contexto H1 → Wyckoff H1/M15 →
ICT M15 → outcome → softmax. Las métricas no son una señal de rentabilidad;
el desempeño OOS diagnóstico cercano a 40% no justifica promoción. La
calibración, abstención, drift, comparación contra baselines y HOLDOUT
2021–2025 siguen pendientes.

## Siguiente acción

Auditar provenance/licencia/reproducción del dataset, crear el bloque HOLDOUT
2021–2025 sin usarlo para ajustar este modelo y ejecutar la comparación
pre-registrada ICT-only vs Wyckoff-only vs Wyckoff+ICT. Mantener
`shadow_mode=true` y `can_trade=false`.
