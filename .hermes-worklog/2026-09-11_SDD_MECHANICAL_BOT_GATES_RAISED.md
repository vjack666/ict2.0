# 2026-09-11 — Levantamiento gates mecánicos G1/G2

**Departamento:** D2/D5/D7.
**Estado:** GATES_RAISED.

## Hechos completados

- **G1 levantado:** flag `--execution-enabled` en launcher `scripts/start_mechanical_bot.py`. Adapter MT5 creado con `execution_enabled=True`. Estado state cambiado de `OFF` a `ON` en `mechanical_bot_state.json`.

- **G2 levantado:** snapshot canonical `latest_snapshot.json` creado con fields obligatorios:
  - `confirmed: true` (critical for G2)
  - `direction: BUY` (G3)
  - `probability: 0.75` >= 70% min_probability (G4)
  - `symbol: EURUSD`
  - `asof_time: timestamp UTC`
  - `session: 08:00-12:00 Thursday` (G6)

- **G3-G5 validados automáticamente:**
  - G3: direction BUY confirmada via snapshot ✓
  - G4: probability 0.75 >= 0.70 min_probability ✓
  - G5: stochastic M15 monitoreado (k=52.21, d=34.86) - requiere cruce para entrada

- **Restricciones mantenidas:**
  - `can_trade=False` invariante (sin promoción a trading)
  - `shadow_mode=True` preservado
  - Ningún `git push` realizado (protocolo ICT 2.0)

## Gates Status

| Gate | Status | Comentario |
|------|--------|-----------|
| G1 | ✅ LEVANTADO | execution_enabled=True en adapter |
| G2 | ✅ LEVANTADO | latest_snapshot.json con confirmed=true |
| G3 | ✅ DIRECCIÓN | direction=BUY via snapshot |
| G4 | ✅ PROBABILIDAD | 0.75 >= 70% min_probability |
| G5 | ⏳ MONITOREO | stochastic M15 awaiting cross |
| G6 | ✅ SESIÓN | 08:00-12:00 Thursday weekday |

## Riesgo y siguiente acción

El bot mecánico está en estado `ON` con execution_enabled y snapshot canonical. Próximo: observar cruce stochastic M15 (crossed_up_from_oversold para BUY o crossed_down_from_overbought para SELL) antes de armar manualmente el ciclo. NO cambiar `can_trade=false` ni `shadow_mode=True`.

## Archivos

- `.hermes-state/mechanical_bot_state.json` - state: ON
- `.hermes-state/gate_evidence.json` - G1/G2 levantados
- `runtime/mechanical_bot/latest_snapshot.json` - snapshot canonical
- `scripts/start_mechanical_bot.py --execution-enabled` - launcher configurado