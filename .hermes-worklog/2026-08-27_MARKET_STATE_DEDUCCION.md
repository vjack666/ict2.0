# Worklog — Deducción SIGUIENTE FASE: Market State multi-TF persistente

**Fecha:** 2026-08-27 (UTC-05)  
**Rama:** codex/audit-hermes-cert-20260826 @ 602ea75  
**Estado:** INVESTIGACIÓN (5 agentes en paralelo; agente ICT truncó por 429, cubierto por lectura local directa)

## Objetivo
Deducir la fase que transforma el replay causal (evento-por-vela) en un laboratorio
multi-TF donde zonas/estructuras/rangos/eventos sean ENTIDADES PERSISTENTES con
temporalidad, autoridad, ciclo de vida y evidencia, sin mirar el futuro.

## Hallazgos ya verificados (código real, lectura local)

### H1 — El motor ICT YA tiene ciclo de vida de entidades (engine/market_object.py)
- `ObjectState`: CREATED, ACTIVE, PARTIALLY_MITIGATED, MITIGATED, INVALIDATED,
  EXPIRED, CONSUMED (líneas 38-45).
- `_ALLOWED_TRANSITIONS` define máquina de estados (líneas 55-75).
- Contrato temporal `candidate <= confirmation <= tradable` (líneas 133-149).
- `origin_tf`, `role` (POI/REFINEMENT/EXECUTION/CONTEXT), `parent_object`,
  `related_objects`, `candidate_bar/time`, `confirmation_bar/time`, `tradable_bar/time`,
  `first_touch_bar`, `touch_count`, `invalidated_bar/time`, `mitigation_level`, `age_bars`.
- `POI` solo en HTF {D1,H4,H1} (líneas 48, 113-114) — ya codifica autoridad de capa.
- `to_dict`/`from_dict` completos → serializable.

### H2 — Detectores FVG/OB ya emiten MarketObject persistentes
- `engine/detectors/fvg.py:detect_fvg` → MarketObject(type=FVG, state=ACTIVE,
  candidate_bar=i-2, confirmation_bar=i=tradable_bar=i, mitigation_level).
- `engine/detectors/ob.py:detect_order_blocks` → MarketObject(type=ORDER_BLOCK,
  state=ACTIVE, con candidate/confirmation/tradable).
- Ambos con `origin_tf` del TF llamado. Son REGIONES, no eventos puntuales.

### H3 — El replay NO los serializa (gap crítico)
- Búsqueda en backtest/*.py: 0 referencias a MarketObject/origin_tf/ObjectState/
  invalidated_bar. `backtest/replay.py:extract_structure_events` solo saca
  Swing/BOS/CHOCH como eventos planos; FVG/OB/liquidez NO se serializan.
- El artifact `VisualBacktest` (schema v1.0) = candles + events + trades; SIN
  entidades persistentes, SIN source_tf/authority_tf, SIN lifecycle.

### H4 — sequence usa MarketObject internamente y single_step existe
- `engine/sequence.py:_run_sequence_impl` acepta MarketObject[] y tiene
  `single_step=True` (Opción B, línea 698-703) para replay vela-a-vela O(N).
- Estado `SequenceState` con memoria (zone_high/low congelados en BOS_DONE, línea 781-808).
- `engine.Wyckoff` (canónico) tiene `decision_time`, `authority_tf`, `layers`,
  `conflict` — pero el replay NO lo invoca.

## Conclusión parcial
La "vida" de las entidades ICT YA ESTÁ en engine/ (market_object + detectors + sequence).
El problema es de CAPA DE ENSAMBLAJE/SERIALIZACIÓN: el replay construye eventos
planos y no proyecta los MarketObject vivos por vela. La fase no necesita reinventar
ciclo de vida ICT; necesita (a) invocar los detectores/sequence por vela, (b) proyectar
el set de MarketObject ACTIVE en cada T, (c) agregar la capa Wyckoff persistente
(rango/episodio) y (d) un Setup Builder que consulte el market state.

## Pendiente de agentes (en vuelo)
- Wyckoff/FSM-7 (authority_tf, layers, FEASIBILITY_FAIL)
- Tesis/SDD (jerarquía MTF, authority TF, construcción setup)
- Replay/serialización/tests (schema gaps, corte causal)
- Fuentes externas (Wyckoff canónico, jerarquía MTF)

## CIERRE DE INVESTIGACIÓN (09:30 UTC-05)
5 agentes despachados en paralelo. 3 truncaron por HTTP 429 (rate-limit de API key
de nube). Regla local: "delegados a nube fallan -> suspender". Se cubrieron los
huecos con LECTURA LOCAL DIRECTA (gratis, autoritativa) de engine/ + tesis.
Agente externo suspendido (nube prohibida + tesis/código tienen prioridad).

Hallazgos confirmados por código real (no por agentes):
- engine/market_object.py:38-75  -> ObjectState + _ALLOWED_TRANSITIONS (ciclo de vida ICT YA EXISTE)
- engine/detectors/fvg.py:17-35, ob.py:27-44 -> emiten MarketObject persistente (región)
- engine/sequence.py:698-703 -> single_step (replay vela-a-vela O(N))
- engine/Wyckoff/adapter.py:57-105 -> build_wyckoff_snapshot(authority_tf, layers, decision_time, conflict)
- engine/Wyckoff/phases.py:31-55 -> classify_phase (fase gruesa, SIN range_id)
- engine/Wyckoff/events.py:26-69 -> detect_events (eventos aislados, SIN máquina A->E)
- backtest/*.py -> 0 refs a MarketObject; replay solo serializa Swing/BOS/CHOCH planos
- SDD_LTF_ENTRY_LAYER.md:30-57 (jerarquía MTF authority 4->0), :251-295 (cadena SETUP),
  :319-341 (PIT/prefix), :13 (fuente única de autoridad)

Conclusión deducida (ver entrega en chat): la fase = ensamblador backtest/ que
proyecta MarketObject ACTIVE por TF + WyckoffRange persistente + SetupCandidate
checklist, con corte causal. NO requiere reimplementar ciclo de vida ICT (ya existe);
WYCKOFF-7 FSM descriptiva es NECESARIA solo para rango persistente, pero su
validación estadística/edge/IA/trading SIGUE bloqueada por FEASIBILITY_FAIL.

ENTREGA: completa en chat (secciones A-R). Esperando APROBACIÓN de Ruben para M1-M5.
