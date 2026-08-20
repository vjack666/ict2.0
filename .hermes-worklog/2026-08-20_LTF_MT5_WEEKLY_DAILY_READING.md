# Worklog — LTF MT5 weekly/daily reading

**Fecha:** 2026-08-20  
**Objetivo:** avanzar el contrato de cierre LTF end-to-end para la prueba MT5
semanal + diaria, sin ejecución financiera.

## Cambios

1. `engine.daily_motor.build_daily_motor_snapshot()` ahora recibe
   `context_state` y prioriza el `MarketState` serializado de
   `engine.mtf_navigation.MTFNavigator`. El fallback legacy queda identificado
   como `DERIVED_STACK`.
2. `engine.mtf_navigation._asof_index()` normaliza timestamps UTC-naive/aware
   antes de evaluar `as_of(t)`.
3. Se creó `engine/ltf_canonical_feed.py` porque faltaba una interfaz de
   ensamblaje entre los módulos existentes. No crea semántica nueva: reutiliza
   `engine.detectors.fvg`, `engine.detectors.ob`, `engine.relations` y
   `engine.sequential_events`; entrega objetos read-only, lineage, touch y
   Sequence al motor diario.
4. `scripts/brief_lunes.py` usa el mismo Context State y el feed canónico para
   producir semana en curso + lectura diaria M15.
5. Plan y SDD LTF actualizados para reflejar la integración inicial y mantener
   abiertos AHF/POI ITF/histórico.

## Corrida MT5

- símbolo: `EURUSD`
- cuenta: `10011586708`
- servidor: `MetaQuotes-Demo`
- terminal local: `C:\Program Files\FundedNext MT5 Terminal\terminal64.exe`
- actualización: `scripts/update_mt5_ict.py --symbols EURUSD --tfs "D1 H4 H1 M15"`
- resultado: `OK=4 FAIL=0`
- timestamps: D1 `00:00`, H4 `16:00`, H1 `17:00`, M15 `17:00` UTC del
  `2026-08-20`.

## Gates

| Gate | Estado | Motivo |
|---|---|---|
| LTF-1 | IN PROGRESS | PIT/determinismo/tests y Context State conectados; falta evidencia histórica y AHF productivo |
| LTF-2 | INITIAL INTEGRATION | FVG/OB/relations/Sequence/touch conectados; falta POI ITF + lineage completo |
| LTF-3 | PENDING | AHF `navigation_snapshot`, rollback y parent history aún no entran al brief |
| LTF-4 | PENDING | falta corrida histórica D1→H4→H1→M15 y comparación versionada MT5 vs Dukascopy |
| MT5 weekly/daily acceptance | PARTIAL | output reproducible y auditable en parte; no declarar PASS final |

## Evidencia

- `reports/audits/ltf_mt5_weekly_daily_2026-08-20.md`
- `docs/briefs/brief_2026-08-20.md`
- suite: `64 passed, 1 warning`

## Política y límites

La lectura sigue siendo `OBSERVE_ONLY_NO_ORDER`. No se produjeron entry, SL,
TP, fill, sizing, PnL ni órdenes. El feed MT5 difiere del dataset histórico
Dukascopy bid 2006–2025 y esa diferencia queda abierta para LTF-4.
