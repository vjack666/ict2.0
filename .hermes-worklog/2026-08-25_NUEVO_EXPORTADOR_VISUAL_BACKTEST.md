# Cierre de implementación — nuevo exportador visual causal

Fecha: 2026-08-25
Alcance: nuevo consumidor en backtest/; sin reutilizar el backtest histórico.

## Decisión

La película de ICT Structure Lab se construye desde las decisiones del motor
canónico. No se implementan detectores alternativos en backtest/.

## Autoridades consumidas

- engine.bos.structure.detect_market_structure — Swing/BOS/CHOCH.
- engine.market_features.build_features — composición de detectores.
- engine.sequence.run_sequence — replay y contratos de entrada.
- engine.sequential_outcome.resolve_outcome — resolución posterior de SL/TP.

## Archivos nuevos

- backtest/replay.py
- backtest/schema.py
- backtest/__init__.py
- scripts/export_visual_backtest.py
- tests/test_visual_backtest.py
- docs/planificacion/SDD_VISUAL_BACKTEST.md

También se actualizan AGENTS.md, .hermes-index.md y este worklog para registrar
la frontera.

## Verificación

Las pruebas sintéticas validan schema, causalidad por prefijo, parentaje y
aislamiento del backtest antiguo. No se ejecutó el replay completo sobre los
parquet reales ni se generó un resultado científico; los gates de backtest
siguen vigentes y promotion_authorized=false.
