# FASE 2c — Mapeo de columnas agente ↔ motor

Auditoría de fidelidad de integración: ¿las columnas que `analysis/*` (capa de
consenso de ICT SYSTEM) lee vía `.get()` son emitidas por el motor real
(`engine.market_features.build_features`)?

Hecho tras FASE 2b (motor arrancado) y la extensión de `build_features` para
incluir `dealing_range` (FASE 2c).

## Resultado del cruce

Motor emite 52 columnas. Agentes leen ~30 vía `.get()`.

### ✅ Cerradas (motor emite, agente lee)
`atr`, `displacement_bullish/bearish`, `fvg_bullish/bearish`, `fvg_fill_status`,
`fvg_size`, `liquidity_sweep_up/down`, `ob_bullish/bearish`, `ob_distance`,
`premium_discount_zone` (añadida en FASE 2c vía `engine.dealing_range`),
`trend`, `swing_label`, `bsl_price`, `ssl_price`, `sweep_low/high`,
`bos_direction`, `choch_signal`, `pd_type`, `pd_tier`.

### ⚠️ Renombre (motor emite, agente usa nombre distinto)
| Agente lee | Motor emite | Acción |
|---|---|---|
| `recent_sweep_up/down` | `liquidity_sweep_up/down` | Alias en agente o mapeo en pipeline |

### ❌ Faltantes (agente lee, motor NO emite hoy)
`macro_direction`, `market_regime`, `volatility_regime`, `trend_confidence`,
`volume_confirmed`, `divergence`, `directional_efficiency`, `range_compression`.

Estas son de regime / volumen / MTF-bias. El motor TIENE módulos
(`engine/bias/narrative.py`, `engine/multitf_context.py`, `engine/_volume.py`)
que podrían producirlas, pero `build_features` no los invoca. **No se inventaron
columnas**: se dejan como pendientes de integración explícita, no como hueco
silencioso. Mientras tanto los agentes devuelven `NEUTRAL`/`None` en esas vías
(usaron `.get()` defensivo, por eso FASE 2b no crasheó).

## Decisión de ingeniería (FASE 2c)
- `premium_discount_zone` SÍ se integró: `compute_dealing_range` es geometría pura,
  sin look-ahead, y el SPEC §2 la exige como OBLIGATORIA. Extender `build_features`
  para llamarla cumple el contrato sin duplicar lógica.
- Las 8 faltantes se dejan como PENDIENTES documentadas. No se "parchean" con
  columnas sintéticas: requieren decidir si el motor las produce (y con qué
  definición) o si los agentes se adaptan. Eso es trabajo de diseño, no de
  arranque.

## Estado
- Motor → 52 columnas → orquestador → 25 `agent_*` : CICLO CERRADO.
- Fidelidad de columnas: ~22/30 cubiertas; 1 renombre; 8 pendientes.
- El sistema arranca y produce consenso; las 8 pendientes degradan silenciosamente
  esas vías de evidencia hasta integrarse.
