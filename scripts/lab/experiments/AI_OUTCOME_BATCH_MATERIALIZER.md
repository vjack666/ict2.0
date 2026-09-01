# Materializador IA por lotes

## Propósito

`ai_outcome_batch_materializer.py` es una utilidad `LOCAL_ONLY` del CAIO. Lee
artefactos JSON ya existentes del Episodes/Funnel y del backtest canónico; no
ejecuta el motor, no lee `data/raw`, no usa MT5 y no crea datos sintéticos.

## Comando

```powershell
C:\Python314\python.exe -m scripts.lab.experiments.ai_outcome_batch_materializer `
  --funnel reports/audits/experiments/ai/visual_backtest_2025_01_h200_funnel.json `
  --backtest reports/audits/experiments/ai/visual_backtest_2025_01_h200_prefix.json `
  --output reports/audits/experiments/ai/2025_01_batch_materialized `
  --partition month `
  --max-episodes-per-batch 256
```

Opcionalmente acepta `--a7-report` y `--research-gate`. Esos archivos no se
inventan ni se rellenan automáticamente.

## Garantías

- `candles`, `events`, `trades` y `episodes` se recorren elemento a elemento;
  nunca se carga el backtest JSON completo.
- Las velas se conservan solo como un índice compacto de timestamps; los
  trades se consultan desde un SQLite temporal en disco; los episodios en RAM
  están limitados por `--max-episodes-per-batch`.
- Cada lote se entrega a
  `scripts/lab/experiments/ai_outcome_dataset.py`, conservando su validación de
  causalidad, horizonte y split temporal.
- Las features vienen de `episode.features_at_t`; las etiquetas vienen del
  `trade.outcome` del backtest. No hay replay, relabeling ni mezcla con MT5.
- Se escriben hashes SHA-256 de los artefactos de entrada y de cada lote,
  `diagnostics.jsonl`, conteos por split, `can_trade=false` y un manifiesto
  inmutable. Una salida existente nunca se sobrescribe.

## Evidencia local ejecutada

Sobre los artefactos mensuales existentes: 6.205 velas indexadas, 6.805 eventos
validados, 1 trade, 1 episodio, 1 fila materializada y 1 partición. El resultado
es `BLOCKED` para entrenamiento porque provenance está `BLOCKED`, no se entregó
A7 ni `research_gate`; esto es correcto y no se transforma en `PASS`.

Pruebas focales y regresión: `22 passed`. Suite completa: `441 passed`.

## Límites

- Esta utilidad reduce memoria y permite construir un dataset por partes; no
  convierte una muestra pequeña en evidencia científica suficiente.
- Un mes con una sola fila no puede entrenar ni validar generalización.
- El manifiesto por lotes no es un `DatasetSnapshot` certificado y no habilita
  `ai_outcome_train.py` hasta que exista un conjunto combinado con provenance,
  A7, splits completos y autorización científica válidas.
- `status=PASS` no es una autorización de trading; `can_trade` permanece falso.
- No se ejecutó una corrida histórica completa de 20 años.
