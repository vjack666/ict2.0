# PASO 2 — Congelar arquitectura (Market State + Setup Builder)

- **Fecha**: 2026-08-27
- **Agente**: Hermes (diseño) — sin implementación
- **Base autoritativa**: `codex/visual-replay-wyckoff-v1-1-20260826` @ `d562ac489b88943e3c92cd4b26f200d5e4b3ec29`
- **Estado**: COMPLETED (arquitectura congelada)
- **Regla**: READ/COMPARE/TRACE/CLASSIFY/DEDUCE. Nada de código.

---

## 1. Objetivo

Congelar la arquitectura objetivo que evoluciona el replay Wyckoff v1.1 hacia un
**Market State persistente + Setup Builder**, sin reconstruir lo ya construido.
Basado en la inspección completa de la base autoritativa v1.1 (schema, timeline,
replay, engine/Wyckoff, engine/sequence, engine/market_object, visor).

## 2. Hallazgos de la inspección (evidencia file:line)

1. **`engine/sequence.py` YA crea MarketObjects** para eventos de secuencia
   (SWEEP, BOS, etc.) con lifecycle completo: `_make_event_object` (`:452-482`),
   `_build_expediente` (`:485-510`), `_check_and_apply_invalidation` (`:537-550`).
   Cada vela LTF se envuelve en un `MarketObject(type=CANDLE)` (`:297-317`).
   **PERO no los expone al artifact** — `run_visual_replay` no los serializa.
2. **`engine/Wyckoff` produce snapshots** (no entidades persistentes):
   `WyckoffSnapshot` (`types.py:95-127`) con `range_ref`, `events`, `layers`.
   `wyckoff_timeline.py:171` fuerza `range_id=None, episode_id=None`.
3. **`backtest/schema.py`** valida el artifact v1.1 y **prohíbe** `range_id`/
   `episode_id` (`:284-285`): "basic runtime cannot claim range_id or episode_id".
4. **`backtest/wyckoff_timeline.py`** construye el timeline vela a vela con
   `_delta` de **campos** (`:82-101`), no de entidades.
5. **`backtest/replay.py`** orquesta todo (`run_visual_replay` `:636-807`) y
   serializa el artifact v1.1.
6. **Visor `App.jsx`** muestra markers puntuales (`:124-177`) y el rango actual
   como 3 líneas (`:179-193`), no regiones persistentes con lifecycle.

## 3. Arquitectura objetivo congelada

### Principio rector

**CONSERVAR** el replay causal, timeline, MTF, decision_time, visor y el contrato
temporal. **AÑADIR** una capa nueva de Market State que proyecte MarketObjects
por vela y mantenga entidades vivas en T. **EXTENDER** el visor para regiones
persistentes y Setup Builder.

### 3.1 Capa nueva: `backtest/market_state.py`

**EXTIENDE** `wyckoff_timeline.py`/`replay.py` (NO módulo paralelo). Responsabilidad:
- Proyectar MarketObjects por vela (reutilizando los que `engine/sequence.py` ya
  crea internamente, exponiéndolos al artifact).
- Mantener un **Persistent Market State**: entidades vivas en T con lifecycle
  (CREATED → ACTIVE → PARTIALLY_MITIGATED → MITIGATED/INVALIDATED/EXPIRED/CONSUMED).
- Calcular delta de **entidades** (no solo de campos) entre T-1 y T.

**Reutiliza**: `engine/market_object.py` (ObjectState, _ALLOWED_TRANSITIONS,
to_dict/from_dict), `engine/sequence.py` (MarketObjects ya creados).

### 3.2 Capa nueva: `backtest/setup_builder.py`

**ÚNICA pieza genuinamente nueva**. Responsabilidad:
- Construir **setups** a partir del Market State (condiciones presentes/faltantes).
- Modelar la cadena HTF→LTF (D1 bias → H1 perspectiva → M15 liquidez → M5/M1
  ejecución) como árbol de decisión secuencial (ICT 2022 Model).
- "Si falta un paso, no opero" → condiciones presentes/faltantes.

### 3.3 Cambios en `backtest/schema.py`

- `SCHEMA_VERSION` → **"1.2"**.
- Añadir campo **`market_state`** (entidades vivas en T) y **`setups`** (setups
  construidos).
- Permitir `range_id`/`episode_id` en el snapshot Wyckoff (cuando el FSM
  persistente esté activo), manteniendo el contrato actual
  `RUNTIME_BASIC_NOT_WYCKOFF_7` como default.

### 3.4 Cambios en `backtest/wyckoff_timeline.py` / `backtest/replay.py`

- Proyectar MarketObjects por vela (delta de entidades, no solo de campos).
- Mantener `FSM_CONTRACT = "RUNTIME_BASIC_NOT_WYCKOFF_7"` hasta que WYCKOFF-7
  esté habilitado por datos (CME 6E/OI local).

### 3.5 Cambios en visor `App.jsx`

- Visualizar **regiones persistentes** (FVG/OB/rangos con lifecycle), no solo
  markers puntuales.
- Mostrar el **Setup Builder** (condiciones presentes/faltantes).

## 4. Invariantes preservadas (del SDD v1.1)

- `diagnostic_only=true`, `entry_authorized=false`, `can_trade=false`,
  `can_train=false`, `promotion_authorized=false`.
- Contrato temporal: `bar_open_time = source_time`, `bar_close_time =
  source_time + duración`, `decision_time = bar_close_time`, `available_time =
  bar_close_time`. Una fila solo participa cuando `bar_close_time <= decision_time`.
- `ict_backtest/` no se importa ni se restaura.
- `engine/` calcula; `backtest/` orquesta y serializa; el frontend solo representa.
- Determinismo: `stable_sha256`, `artifact_content_sha256`, `run_id`.
- `TICK_VOLUME_PROXY` (no volumen real; EURUSD no-exchange).
- `authority_tf = H1` (decisión interna de arquitectura).

## 5. Clasificación de arquitectura (del PASO 1)

- **EXTERNAMENTE COHERENTE**: Trading Range persistente, fases A–E, eventos
  secuenciales, FVG/OB regiones, MSS/CHOCH eventos, HTF→LTF, TICK_VOLUME_PROXY,
  Setup Builder.
- **DECISIÓN INTERNA**: lifecycle 7 estados de MarketObject, authority_tf=H1.
- **REQUIERE MÁS INVESTIGACIÓN**: volumen centralizado + OI (depende de datos CME 6E).

## 6. Implicaciones para WYCKOFF-7 y Setup Builder

- **WYCKOFF-7** (FSM persistente por range_id/episode_id): respaldado por Wyckoff
  (rango persistente con fases). Sigue bloqueado por datos (sin CME 6E/OI local).
  La arquitectura debe permitir el FSM persistente aunque el contrato actual sea
  `RUNTIME_BASIC_NOT_WYCKOFF_7`.
- **Setup Builder**: respaldado por ICT (árbol de decisión secuencial, "si falta
  un paso no opero"). Debe modelar condiciones presentes/faltantes y la cadena
  HTF→LTF.

## 7. Criterio de DONE

- ✅ Arquitectura objetivo congelada (sección 3).
- ✅ Invariantes preservadas (sección 4).
- ✅ Clasificación de arquitectura (sección 5).
- ✅ Implicaciones WYCKOFF-7 y Setup Builder (sección 6).
- ✅ Basado en inspección completa de la base autoritativa v1.1 (sección 2).

## 8. Siguiente acción

Esperar aprobación de Ruben para **PASO 3 (SDD)**. NO implementar nada.
