# Nuevo exportador visual de backtest

Esta carpeta es un consumidor nuevo del motor canónico de ICT SYSTEM. Su única
responsabilidad es reproducir un replay cerrado y serializarlo para ICT
Structure Lab; no contiene detectores ni reglas de estrategia.

La cadena es:

    data/raw/<SYMBOL>/*.parquet
            ↓
    engine.market_features
            ↓
    engine.bos.structure
            ↓
    engine.sequence.run_sequence
            ↓
    engine.sequential_outcome
            ↓
    backtest/visual_backtest.json

El entrypoint es scripts/export_visual_backtest.py. El artifact incluye velas
OHLC, Swing, BOS, CHOCH, parent_id, confirmed_index y las operaciones emitidas
por el motor con entrada, SL, TP, salida y resultado cuando existe.

Reglas de frontera:

- No se importa ict_backtest ni se ejecutan runners históricos.
- No se recalculan Swing/BOS/CHOCH en esta carpeta.
- Los eventos se publican en la vela causal (confirmed_index); no se exportan
  etiquetas retrospectivas de calidad/estado que dependan de velas futuras.
- La resolución de un resultado solo escanea velas posteriores a la entrada y
  queda marcada en result_confirmed_index.
- El artifact es observación para el visor. promotion_authorized permanece
  false y no habilita órdenes ni promoción científica.

Ejemplo:

    python scripts/export_visual_backtest.py --symbol EURUSD --timeframe H1 --tfs H1 --output backtest/visual_backtest.json

La ejecución completa sobre datos reales no forma parte de las pruebas unitarias
de este componente; primero deben cumplirse los gates de backtest del proyecto.
