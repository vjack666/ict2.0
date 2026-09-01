# Inventario de datos — ICT SYSTEM/data/

Los parquet de forex se trajeron del disco y se organizaron aquí.
**Los .parquet NO se commitean** (binarios masivos; ver `.gitignore`: `data/`).
Este inventario documenta qué hay y de dónde vino, para reproducirlo.

## Estructura

```
data/
├── raw/<SYMBOL>/<SYMBOL>_<TF>.parquet   # OHLC crudo + tick_volume + spread
└── ml/<nombre>.parquet                  # features ya procesadas (SMC-SYSTEMS data/ml, GRID structural_*)
```

`raw/` se organiza por símbolo y timeframe. Conflicto mismo (símbolo,TF):
se queda el archivo de MÁS filas entre las fuentes.

## Símbolos y TFs disponibles (raw)

| Símbolo | TFs |
| --- | --- |
| EURUSD | D1, H1, H4, M1, M3, M5, M15 |
| AUDUSD | D1, H1, H4, M5, M15 |
| GBPUSD | D1, H1, H4, M5, M15 |
| NZDUSD | D1, H1, H4, M5, M15 |
| USDCAD | D1, H1, H4, M5, M15 |
| USDCHF | D1, H1, H4, M5, M15 |
| USDJPY | D1, H1, H4, M5, M15 |
| XAUUSD | D1, H1, H4, M1, M5, M15 |

Columnas raw: `time, open, high, low, close, tick_volume, spread`
(El de GRID SCAPL 2 usaba `timestamp`; se normalizó a `time` al importar.)

## ml/ (features ya procesadas — NO son OHLC crudo)

De SMC-SYSTEMS/data/ml: `v4_<SYM>.parquet` (EURUSD/AUDUSD/GBPUSD/NZDUSD/USDCAD/
USDCHF/USDJPY/XAUUSD), `v4_dataset`, `v4_EURUSD_2023_2024`, `v4_synthetic`.
De GRID SCAPL 2/datasets: `structural_labels`, `structural_ml_train/test/validation/dataset`.

## Fuentes origen (en disco, no en repo)

- `Desktop/GRID SCAPL 2/datasets/mt5_clean/*.parquet` (OHLC crudo)
- `Desktop/legacy_smc_backup/src/_legacy_data/data_raw/*.parquet`
- `Desktop/legacy_smc_backup/src/_legacy_data/data_mt5/*.parquet`
- `Desktop/SMC-SYSTEMS/data/raw/*.parquet`, `Desktop/SMC-SYSTEMS/data/ml/**`

## Reproducir la importación

`python scripts/data/import_forex_data.py` (la ruta antigua queda como wrapper;
lee las fuentes de arriba y puebla data/).

## Nota para el motor

`engine.market_features.build_features(df)` espera columnas `time/open/high/low/close`.
Los raw ya las tienen. `tick_volume` está presente en los raw reales (desbloquea
la columna `volume_confirmed` que antes faltaba por datos sintéticos sin volumen).
