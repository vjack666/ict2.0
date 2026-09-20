# 2026-09-20 — GPT / Replay histórico causal de objetos H4/M15

**Rama de integración aislada:** `gpt/ict-causal-replay-20260920` creada desde `b277f7c9ec9d222c785fcfde23d043d10628e54a`. El punto de control de Hermes sigue en su rama exclusiva de evidencia; **no se modificaron `main`, PR #14 ni PR #15**, y no se tocó el Windows de Rubén. Este commit usa código de GitHub como única fuente, no los ZIP antiguos.

## Por qué se añadió

El inventario 154/582 contiene ocurrencias individuales sin lineage ni lifecycle; no puede alimentarse como secuencias ICT completas. En el repositorio ya existen `MarketState`, lifecycle y `build_historical_event_objects` H4/M15 con padres explícitos. Faltaba un runner de replay cronológico limitado y comprobable que consumiera esos objetos, evitando:
- nacimiento anticipado de OB al usar su vela fuente;
- auto-mitigación en la vela de confirmación;
- que una vela M15 modifique un objeto H4;
- inventar un padre por proximidad;
- interpretar el conteo de inventario como episodios.

## Cambios

`engine/causal_replay.py`: mezcla cronológicamente velas H4/M15 (o TF adicionales si fueron normalizadas), exige hora de CIERRE UTC explícita y monotónica por TF, clona objetos, comprueba IDs únicos y padres con disponibilidad anterior al hijo, publica el objeto en su `tradable_time`, usa `MarketState.advance_bar` únicamente en velas cerradas posteriores al nacimiento de zonas de la autoridad TF. No manipula el productor ni el motor de secuencias o el funnel.

`scripts/audit/run_causal_replay.py`: piloto con datos reales de ZIP EURUSD, SHA256 contra manifiesto existente, controles A/B, ventanas de calentamiento H4=120 días/M15=21 días, reportes JSON y muestra de hasta 20 MarketObjects. No declara P1 ni devuelve operaciones.

`tests/test_causal_replay.py`: seis pruebas aisladas con FakeMS que verifican orden global, frontera de confirmación, autoridad TF, ausencia de futuro, huérfanos, duplicados, timestamp UTC, orden cronológico, datos OHLC y resultados sin PASS falso.

SDD existente `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md` actualizado con alcance y gates. No se crearon SDD duplicados.

## Verificación efectivamente ejecutada

Entorno aislado de desarrollo, solo archivos nuevos: `PYTHONPATH=. python -m pytest -q tests/test_causal_replay.py` → **6 passed**, `python -m compileall -q engine/causal_replay.py scripts/audit/run_causal_replay.py tests/test_causal_replay.py` → OK. Los blob SHA de los archivos publicados fueron comparados con el contenido local probado: módulo `0f90a6518fb4b4a0ae2b4d3abe12ec169945c46c`, test `ef95ee61a9c288c6cabd0711270d3274e060141d`, CLI `6dbc5f680fc278aa9fac39198d93fe04cd25b114`.

**Limitaciones:** las seis pruebas NO ejecutan el MarketState real, el productor histórico real, los CSV de EURUSD ni el funnel completo. La compatibilidad integral del piloto y los resultados A/B deben verificarse por Hermes en Windows antes de solicitar la promoción/merge. La entrada `frames[TF].time` debe ser hora de cierre; el CLI convierte explicitamente la hora de apertura CSV. Los OB que se produjeron con información futura en `build_historical_event_objects` necesitarán FULL/PREFIX independiente del productor antes de usar como datos certificados.

**Gates:** `SCHEDULER_UNIT=PASS`; `REAL_MARKETSTATE_INTEGRATION=PENDING`; `EURUSD_PILOT_A_B=PENDING`; `FULL_PREFIX=PENDING`; `SIX_TF=PENDING`; `SEQUENCES=PENDING`; `FUNNEL=PENDING`; `EPISODES=PENDING`; `GRU_TRAINING=NO`; `LIVE_TRADE=NO`.

## Descarga y trabajo siguiente de Hermes

Solo en `C:\Users\v_jac\Desktop\ICT SYSTEM`, proteger cambios locales; `git fetch origin` y crear worktree local basado en `origin/gpt/ict-causal-replay-20260920`, sin tocar el worktree operativo con cambios sin commit. Ejecutar suite focal y de integración con `MarketState` real, luego piloto A/B; publicar **solo evidencia y ajustes propuestos** en rama exclusiva Hermes (no push a rama GPT). Si el piloto falla, capturar error exacto, proponer corrección y esperar revisión GPT; no declarar causalidad integral por 6 tests aislados. Conservar CLEAN y sus respaldos hasta autorización explícita de Rubén.
