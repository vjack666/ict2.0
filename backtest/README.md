# Replay visual causal ICT + Wyckoff v1.1

`backtest/` es un consumidor de solo lectura del motor canónico. Normaliza la
disponibilidad temporal, conserva warmup, llama a `engine/` y produce un run
reproducible para el visor; no contiene reglas de estrategia ni importa
`ict_backtest`.

```text
Parquet locales (OPEN_TIME o CLOSE_TIME explícito)
  -> prefijos de velas cerradas + warmup
  -> engine.market_features / bos / MTFNavigator / sequence / outcome
  -> engine.Wyckoff.build_wyckoff_snapshot
  -> backtest/runs/<run_id>/{visual_backtest.json,manifest.json}
  -> backtest/viewer (React/Vite, solo lectura)
```

## Exportar un run real

```powershell
python scripts/export_visual_backtest.py `
  --symbol EURUSD `
  --timeframe M15 `
  --tfs D1 H4 H1 M15 M5 M1 `
  --data-dir "C:\ruta\a\data\raw" `
  --start 2026-08-17 `
  --end 2026-08-21 `
  --warmup-bars 200 `
  --timestamp-semantics open `
  --wyckoff `
  --wyckoff-authority-tf H1 `
  --wyckoff-layers D1 H4 H1 M15 `
  --multitf-context
```

La fecha de `--end` incluye ese día completo. La semántica temporal nunca se
infiere: MT5 usa apertura de barra y el motor recibe una copia con
`time=bar_close_time`. M5/M1 quedan como evidencia observacional y no cambian
la autoridad H1.

## Abrir el visor

```powershell
npm ci --prefix backtest/viewer
npm run build --prefix backtest/viewer
python scripts/serve_visual_backtest.py --run-dir backtest/runs/<run_id>
```

Abrir `http://127.0.0.1:4173/`. El servidor solo permite lectura del build y
del run seleccionado.

## Límites

Todos los artefactos validan `diagnostic_only=true`, `entry_authorized=false`,
`can_trade=false`, `can_train=false` y `promotion_authorized=false`. El runtime
Wyckoff vigente es básico (`RUNTIME_BASIC_NOT_WYCKOFF_7`): este visor no prueba
edge, no completa WYCKOFF-7 y no autoriza trading o promoción.
