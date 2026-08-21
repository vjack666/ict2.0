# Evidencia — lectura LTF MT5 semanal + diaria

**Fecha de corrida:** 2026-08-20 (America/Guayaquil)  
**Commit base:** `d60c340` + cambios locales de esta iteración  
**Estado de gate:** `PARTIAL — no declarar PASS`

## Feed utilizado

- Símbolo: `EURUSD`
- Terminal: `C:\Program Files\FundedNext MT5 Terminal\terminal64.exe`
- Cuenta: `10011586708`
- Servidor reportado por MT5: `MetaQuotes-Demo`
- El conector no expone un campo broker independiente; no se etiqueta
  `FundedNext` como broker. `FundedNext` es solo el path del terminal local.
- Actualización: `scripts/update_mt5_ict.py`, `OK=4 FAIL=0`
- Barras finales observadas:
  - D1: `2026-08-20 00:00:00+00:00`
  - H4: `2026-08-20 16:00:00+00:00`
  - H1: `2026-08-20 17:00:00+00:00`
  - M15: `2026-08-20 17:00:00+00:00`

## Resultado semanal y diario

La salida versionada queda en [`docs/briefs/brief_2026-08-20.md`](../../docs/briefs/brief_2026-08-20.md).

- Semana en curso: `2026-08-17T00:00:00+00:00` →
  `2026-08-20T17:00:00+00:00`, 357 velas M15.
- OHLC semanal: open `1.15619`, high `1.17106`, low `1.15614`, close
  `1.16721`.
- Context State: `BULLISH`, location `PREMIUM`, fuente
  `engine.mtf_navigation.MTFNavigator`.
- Wyckoff D1: fase `DISTRIBUTION`, `phase_state=COUNTERTREND`,
  `authority_tf=D1`, `ict_alignment=CONFLICT`. Esta capa agrega contexto y no
  cambia el `direction_hint` ICT.
- Snapshot diario: D1/H4/H1/M15 con `asof_time` independiente.
- Sequence canónica: disponible, `200 refs`, profundidad máxima `4`.
- Zonas canónicas M15: `411` objetos consumidos por el snapshot; marcadores
  legacy siguen separados y no promocionan estado.
- Retest/touch canónico: `OBSERVED` en el conjunto de objetos elegibles.
- Estado final: `WAIT_LTF_CONFIRMATION`; la estructura M15 no confirma la
  dirección heredada. No se generó entry, orden, SL, TP, fill ni sizing.

## Pruebas ejecutadas

- Suite completa: `64 passed, 1 warning`.
- Pruebas dirigidas de motor, navegación y feed canónico: `16 passed`.
- PIT del feed canónico: el futuro añadido después de `decision_time` no cambia
  la lista de objetos.
- PIT del navegador: timestamps naive/UTC se normalizan antes de comparar
  `as_of(t)`.

## Diferencias y limitaciones

- Las auditorías históricas usan `datasets/eurusd_dukascopy_20y` (Dukascopy bid,
  2006–2025); esta corrida usa el feed MT5 `MetaQuotes-Demo`. Los precios,
  sesiones y objetos no deben suponerse idénticos.
- El brief ya consume `MarketState` real y el adaptador canónico FVG/OB/
  Sequence, pero todavía no inyecta un `navigation_snapshot` de AHF ni resuelve
  POI ITF completo con refs propios.
- LTF-3 y LTF-4 permanecen abiertos; por eso esta evidencia demuestra avance
  operativo, no cierre final de LTF Reading.
