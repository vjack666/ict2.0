# Auditoría de eliminación de ict_backtest

**Fecha:** 2026-08-25
**Checkout auditado:** C:\Users\v_jac\Desktop\ICT SYSTEM
**Estado:** SAFE_ALREADY_DELETED

## Veredicto

No se ejecutó ningún borrado porque ict_backtest/ ya no existe en el checkout
operativo ni está versionado en el estado actual. La eliminación fue realizada
deliberadamente por el commit 425fb53:

LIMPIEZA: elimina ict_backtest/ (backtest desechable, no se usa mas)

Ese commit eliminó 80 archivos y 8.818 líneas. La evidencia histórica muestra
que la dependencia era ict_backtest → engine; el motor no dependía del backtest.

## Controles ejecutados

1. Test-Path ict_backtest → ausente.
2. git ls-files para ict_backtest → sin rutas actuales.
3. Historial Git → eliminación deliberada en 425fb53.
4. Imports Python actuales (from/import ict_backtest, __import__, import_module)
   → cero.
5. engine/, detectors/, tools/, runtime/, scripts/daily/, scripts/audit/,
   audits/codigo/ y workflows → no dependen ejecutablemente de ict_backtest.
6. Lectura diaria actual: scripts/daily/brief_lunes.py consume
   engine.market_features, engine.daily_motor, engine.ltf_canonical_feed,
   engine.mtf_navigation, engine.Wyckoff, engine.plan y
   scripts.opening_readiness.
7. Funnel y auditorías actuales consumen engine.detectors,
   engine.sequential_events, engine.mtf_navigation, engine.lineage y
   audits.codigo; no consumen el backtest histórico.
8. Graphify confirmó que las referencias actuales a ict_backtest son
   documentales o históricas, no dependencias de código.

## Qué permanece en el motor

La lógica útil vive en rutas canónicas del motor, entre ellas:

- engine/_util.py
- engine/market_features.py
- engine/bos/structure.py
- engine/sequence.py
- engine/plan_driver.py, engine/plan_emitters.py y engine/plan_fsm.py
- engine/htf_pd_index.py
- engine/trade_mgmt.py
- engine/turtle_soup.py y engine/silver_bullet.py
- engine/zone_authority.py

El consumidor nuevo del visor es backtest/. No se debe restaurar ict_backtest/.

## Referencias clasificadas

- Referencias operativas corregidas: registry, governance, protocolo,
  ingeniería, cumplimiento, alertas, auditoría independiente, AGENTS.md,
  analysis/ict_agent.py y docs/CIERRE_FASE2.md.
- Referencias históricas conservadas: docs/ict/*, auditorías de Fase 0 y
  worklogs que documentan la carpeta antigua y el motivo de su eliminación.
  No son instrucciones operativas para restaurarla.

## Límites

No se ejecutaron lecturas diarias, funnel de 20 años, backtests ni experimentos.
La eliminación no afecta la lectura diaria ni los gates porque ya consumen
engine/ y audits/codigo/. Tampoco se modificaron los datos parquet ni los
gráficos existentes del workspace.
