# SDD — Capa LTF de Ejecución y Entrada (SMC-SYSTEMS)

**Fecha:** 2026-08-06
**Autor:** Hermes (agente), bajo revisión Ruben (arquitecto)
**Estado:** Fase 1 en ejecución; Fases 2-5 pendientes de OK por fase.

## 0. Contexto y Ley

El HTF está CERRADO al 100% (sesgo T8 + 3 capas A1 + POI anclado B + CHOCH real
T9.7 + BOS vigente único T9.6 + detector de secuencia verificado por auditoría de
funnel: 23 sweep → 22 displace → 19 bos → 19 entry, 10 setups completos/mes).

Este SDD cubre la CAPA LTF: cómo el motor, tras reconocer el setup HTF, EJECUTA
la entrada fina en M5/M1 y gestiona el trade. Todo va al MOTOR (`engine/`).
El backtest (`ict_backtest/`) SOLO consume — nunca decide (Ley arquitectónica:
`engine/` no importa `ict_backtest/`).

Fuente de verdad de requisitos: `docs/auditorias/AUDITORIA_FIDELIDAD_TESIS_ICT_2026-07-17.md`
(ítems 11-24). Esa auditoría marcaba estos gaps LTF; T9 ya cerró POI anclado (7) y
CHOCH real (5 parcial), así que el gap LTF remanente es:

| Ítem tesis | Estado hoy | Gap |
|---|---|---|
| 11 OTE 62-79% | NO EXISTE | hueco menor (tesis 21 §6 no lo obliga) |
| 15 Silver Bullet (NY 10-11/14-15 + retorno M15/M5) | NO EXISTE | módulo dedicado ausente |
| 16 Entry Trigger (retorno/mitigation) | EXISTE (`sequence`) | OK |
| 18 SL estructural mecha sweep | EXISTE (`execution.py` B2) | OK |
| 19 TP liquidez opuesta LTF | EXISTE | OK |
| 22 Trade Management (BE/parciales) | NO EXISTE | falta |
| 23 Temporalidades M5/M1 exec fino | PARCIAL | B2 escrito, backtest no lo consume |
| 24 Narrativa ICT coherente | NO EXISTE | grafo de contexto, fuera de scope LTF |

## 1. Alcance

Cerrar la capa LTF para que el motor pueda, tras un setup HTF válido:
1. Ejecutar entrada fina en M5/M1 (SL mecha sweep, TP RR 1:3). [Fase 1]
2. Gestionar el trade (BE + parciales). [Fase 2]
3. Operar Silver Bullet y PO3 como estrategias intradía dedicadas. [Fase 3]
4. (Opcional) OTE 62-79% como filtro de entrada fina. [Fase 4]
5. Unificar zona horaria de killzone (KZ-2) en backtest/observador/mapa. [Fase 5]

NO es objetivo de este SDD: cambiar el HTF (ya cerrado), ni el detector de
secuencia (ya verificado), ni crear indicadores (prohibido: geometría pura).

## 2. Fase 1 — Exec fino M5/M1 (cerrar B2)

### 2.1 Estado actual (ya escrito)
- `engine/execution.py::fine_execution(ms, t, direction, *, exec_tf="M5", rr=3.0, sweep_ts=None)`
  devuelve `{ok, exec_tf, entry, sl, tp, rr, reason}`.
  - Sin `sweep_ts`: entry/SL/TP desde swings del exec TF (fallback).
  - Con `sweep_ts`: SL = MECHA DEL SWEEP del exec TF (libro 18: SL SIEMPRE en TF
    más fino). Entry = breakout del último swing en exec TF.
  - 14 tests B2 pasan (`test_b2_exec_tf.py`, `test_engine_execution_b2.py`,
    `test_b2_exec_tf_wiring.py`).
- `ict_backtest/canonical.py` YA pasa `sweep_ts` a `fine_execution` (~l298).
- `ict_backtest/run_backtest.py` acepta `exec_tf` pero el backtest real (EURUSD 1
  mes) dio 0 señales — el funnel muere en detección, NO en B2 (verificado por
  auditoría de secuencia: 10 setups completos, pero `run_backtest` con exec_tf=M5
  dio 0 — desajuste entre `evaluate_signals` y `run_sequence_backtest`).

### 2.2 Trabajo Fase 1
1. Diagnósticar por qué `run_backtest` con `exec_tf=M5` da 0 señales mientras
   `evaluate_signals` (que llama al mismo motor) da 10 setups. Hipótesis:
   `run_backtest` no pasa el `sweep_ts` al `fine_execution`, o el recorte de
   ventana descarta el LTF fino.
2. Cablear `run_backtest` para que, tras ENTRY del motor, llame `fine_execution`
   con `exec_tf=M5` y `sweep_ts` real, y simule fill next-open + costs (R6 ya ON).
3. Verificar con runner_monitor (window_months=1, ~550s) que el backtest ahora
   ENTREGA señales con SL/TP finos y reporta P&L por primera vez.
4. Tests: añadir `test_run_backtest_uses_fine_execution` (assert que el SL de la
   señal viene del exec TF, no de M15).

**Criterio de done Fase 1:** backtest EURUSD 1 mes entrega >0 trades con SL/TP en
M5 anclados a mecha sweep, y el test nuevo pasa. Sin romper los 123 tests motor.

## 3. Fase 2 — Trade Management (BE + parciales)

### 3.1 Requisito tesis (ítem 22)
El motor hoy solo hace hold hasta TP/SL. La tesis pide Break-Even y parciales.

### 3.2 Diseño
- `engine/execution.py::manage_trade(position, ms, t, cfg)` → acciones
  `{"move_be": bool, "partial": float|None}`.
- Regla BE: cuando el precio recorre >= 50% del rango entry→TP en la dirección,
  mover SL a entry + buffer (estructural, no arbitrary).
- Parcial: cerrar 50% en el primer objetivo de liquidez interna (BSL/SSL del exec
  TF), dejar 50% a TP final (liquidez externa).
- El backtest consume `manage_trade` vela a vela tras el fill.

### 3.3 Tests
- `test_trade_management_be`: SL salta a BE tras 50% del recorrido.
- `test_trade_management_partial`: cierra 50% en liquidez interna.

**Done Fase 2:** backtest aplica BE+parcial y los tests pasan.

## 4. Fase 3 — Silver Bullet + PO3 (intradía)

### 4.1 Requisito tesis (ítems 15, 08)
- Silver Bullet: ventana NY AM (10:00-11:00 ET) + sweep SSL/BSL en M15 + FVG en
  M1/M5 tras sweep + retorno POI. (Auditoría midió 122 setups teóricos, 0 con
  displacement — requiere calibrar displacement en M5.)
- PO3 / Power of Three (AMD): acumulación→manipulación→distribución intradía,
  dirección a-favor del HTF.

### 4.2 Diseño
- `engine/sequence.py` ya genera ENTRY por retorno; añadir modo `style="silver_bullet"`
  que exija ventana KZ + FVG M5 post-sweep.
- `signals/po3.py` ya existe (`build_po3_state`, `Po3MotorConfig`); cablearlo al
  motor como estrategia intradía a-favor del HTF (no reimplementar).
- El backtest consume ambos como estrategias adicionales al event-sequence canónico.

### 4.3 Tests
- `test_silver_bullet_window`: solo entra dentro de NY AM.
- `test_po3_cableado`: PO3 respeta sesgo HTF.

**Done Fase 3:** backtest opera Silver Bullet + PO3 con señales reales en datos
EURUSD M5/M15.

## 5. Fase 4 — OTE (retracement 62-79%) [OPCIONAL]

### 5.1 Requisito
Tesis 21 §6 no lo obliga, pero es práctica ICT. Como FILTRO de entrada fina: tras
el retorno a POI, exigir que el toque caiga en 62-79% del rango sweep→BOS.

### 5.2 Diseño
- `engine/execution.py::_ote_zone(sweep, bos)` → (lo, hi) 62-79%.
- `fine_execution` acepta `require_ote=True` y valida entry dentro de la banda.

**Done Fase 4:** entry fina opcionalmente filtrada por OTE; test `test_ote_band`.

## 6. Fase 5 — Unificar Killzone (KZ-2)

### 6.1 Requisito
`detectors/killzones.py` usa horas locales del chart; backtest/observador/mapa
deben coincidir en UTC. "En killzone" debe significar lo mismo en los 4.

### 6.2 Diseño
- Centralizar `KILLZONES_UTC` en un solo módulo (`engine/killzones.py` o
  `ict_backtest/rules.py`) y que detector/backtest/UI importen de ahí.
- Tests: `test_killzone_utc_consistency` en los 3 consumidores.

**Done Fase 5:** los 3 consumidores usan la misma definición UTC.

## 7. Verificación global

Cada fase:
1. Tests nuevos en `tests/test_engine_*` o `tests/test_ltf_*`.
2. Backtest EURUSD window_months=1 con runner_monitor (no SIGTERM).
3. No romper los 123 tests motor existentes.
4. Commits por fase, push tras OK de Ruben.

## 8. Riesgos

- Fase 1 puede revelar que `run_backtest` y `evaluate_signals` divergen en el
  consumo del motor (ya visto: 10 vs 0). Si el bug es profundo, puede requerir
  unificar ambos en un solo consumidor canon (ya existe `evaluate_signals`).
- Fase 3 Silver Bullet depende de calibration de displacement en M5 (auditoría
  midió 0 ejecutables). Puede requerir relajar `require_displacement` para M5.
- Memoria RAM: M1/M5 masivos (1.6M velas). Usar window_months=1 en verificación.
