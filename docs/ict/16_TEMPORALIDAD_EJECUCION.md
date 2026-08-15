# ICT — Temporalidad de ejecución: jerarquía HTF → LTF → exec

| Campo | Valor |
|-------|-------|
| **ID** | `16_TEMPORALIDAD_EJECUCION.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Autor** | SMC-SYSTEMS (Ruben + agente) |
| **Estado** | Marco de aplicación al motor (v30) |
| **Fuente verdad** | Código repo + innercircletrader.net (Turtle Soup / Silver Bullet) |
| **Relaciona** | `15_INTRADIA_ENTRADA_SL_TP.md`, `17_SCALPING_ENTRADA_SL_TP.md`, `14_STOP_LOSS_ESTRUCTURAL.md` |

---

## §0 Contrato operativo (CITABLE)

> Regla dura unificada en `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`. Este libro la aplica a la jerarquía de temporalidad.

1. Toda operación ICT tiene **3 capas funcionales** (no 2):
   - **HTF** (Bias / sesgo): dirección macro, narrativa, liquidez mayor. Day trading: **H1** (o H4). Scalping: **M15/H1**. Swing: **D1**.
   - **ITF** (Intermediate / zona): dónde reacciona el precio (POIs, BOS, FVG, OB, Breaker). Day trading: **M15**. Scalping: **M5**. Swing: **H4**.
   - **LTF / exec TF** (disparo): entrada, SL y TP finos. Day trading: **M15**. Scalping: **M1/M3/M5**. Swing: **H1**.
2. Lectura **top-down, siempre**: HTF → ITF → exec TF. Nunca de abajo hacia arriba. El HTF manda sobre el LTF.
3. El **sesgo** se lee del HTF. La **estructura/zona** se marca en el ITF. La **entrada, SL y TP** se resuelven en el exec TF (LTF).
4. **SL y entry SIEMPRE en el exec TF.** Nunca en un TF mayor (HTF/ITF). Intradía → SL en M15; scalping → SL en M5/M1 (nunca M15 ni H4).
5. El motor debe permitir `htf`, `itf` y `exec_tf` independientes (hoy solo expone `htf`/`ltf`; ver hueco #1 en libro 18).

---

## 1. El bug que este libro corrige

R4 v28 (ATR) y v29 (SL estructural) corrieron `htf=H4, ltf=M15`. El motor entra en `row["close"]` del LTF (M15) y el TP apunta a la liquidez del LTF. Eso es intradía correcto en teoría, PERO:

- El entry en close de BOS M15 = tarde (no retorno a zona).
- El TP en cluster de liquidez M15 = lejano → hold_limit (v29: 7/11 y 11/13).

El presente de Ruben era CIERTO: el H4 infla el sesgo, y resolver todo en M15 (grueso) infla el TP. La solución no es "usar H4 para el stop" (eso sería peor), es **bajar el exec TF al nivel fino donde ICT realmente ejecuta**: M5/M1 para scalping, y para intradía usar el retorno a la zona M15 en vez del close del BOS.

---

## 2. Jerarquía soportada por el repo (código real)

`ict_backtest/engine.py` `TF_FREQ` (líneas 250-254) soporta M1/M5/M15/H1/H4/D1. **Falta M3** (hueco #2 en libro 18).

`build_signals_from_frames(htf=, ltf=)` (línea 44) hoy acepta HTF y LTF, pero **no un `exec_tf` ni `itf` separados** (hoy `exec_tf == ltf`). La infra para bajar el exec TF existe parcialmente: `checklist_scalping` (rules.py 174) ya pasa `exec_tf` explícito, pero el motor principal aún itera `ltf` y saca el SL de ese row (engine.py 115). Para separar ITF de exec TF (p.ej. scalping ITF=M5, exec=M1) hay que parametrizar `exec_tf` (v30).

O sea: la infra base existe, pero el motor aún no resuelve las 3 capas de forma independiente. El backtest v29 solo corrió H4→M15 (sin ITF explícito).

| Capa | Day trading | Scalping | Swing | En el código |
|------|-------------|----------|-------|-------------|
| HTF (Bias) | H1 / H4 | M15 / H1 | D1 | `bias_by_tf` / `htf` |
| ITF (Zona) | M15 | M5 | H4 | hoy = `ltf` |
| exec TF (Entry+SL) | M15 | M1/M3/M5 | H1 | hoy = `ltf` (no separado) |

---

## 3. Mapeo ICT (fuente: innercircletrader.net + tradingfinder top-down)

| Modelo | HTF (Bias) | ITF (Zona) | exec TF (Disparo) | Killzone |
|--------|-------------|-------------|-------------------|-----------|
| Intradía (Turtle Soup) | H1 / H4 | M15 | M15 | London / NY |
| Scalping (Silver Bullet) | M15 / H1 | M5 | M1 / M3 / M5 | London 03–04, NY AM 10–11, NY PM 02–03 ET |
| PO3 | D1 | H4 | H4 / M15 | London / NY |
| Swing | D1 | H4 | H1 | — |

El humano ICT marca en M15 (parent chart) y ejecuta en M5/M1. El robot v29 marcaba y ejecutaba en M15 (sin ITF explícito). La corrección v30 es parametrizar `itf` y `exec_tf` y resolver SL/entry en el exec TF (ver libro 18).

---

## 4. Cómo el motor debe usar las 3 capas

`build_signals_from_frames` debe:
1. Leer `trend` del HTF para sesgo (ya lo hace, línea 85).
2. Detectar sweep/BOS/CHOCH/FVG en el LTF (ya lo hace vía `detect_market_structure` + `build_features`).
3. **Entry**: retorno a la zona del LTF (FVG/OB) — no close del BOS.
4. **SL**: mecha del sweep del LTF ± buffer (`calc_structural_sl`, ya hecho).
5. **TP**: liquidez opuesta del LTF MÁS CERCANA (`_tp_liquidity` a corregir en v30).

Para scalping: correr con `ltf=M5`, `htf=M15`. El motor no cambia, solo el argumento.

---

## 5. Auditoría de look-ahead por temporalidad

- El sesgo del HTF debe leerse de la vela YA CERRADA del HTF (`.shift(1)` en `_row_at_time`, ya aplicado en auditoría #1).
- El sweep/FVG del LTF debe leerse de la vela cerrada (`.shift(1)`).
- El exec TF (entry) debe ser una vela posterior al sweep confirmado, no la misma.
- Nunca leer el HTF "hacia adelante" para justificar una entrada en el LTF (eso es look-ahead por mal alineo de TF — ya auditado en `AUDIT_BUG_SILVER_TF.md`).

---

## 6. Checklist de aplicación (v30)

- [ ] `run_backtest.py` / scripts v30: permitir `ltf=M5` para scalping.
- [ ] `build_signals_from_frames`: separar "marcar zona LTF" de "disparar exec TF".
- [ ] Intradía (H4→M15): entry en retorno a zona M15, TP cercano M15.
- [ ] Scalping (M15→M5): entry en retorno a FVG M5, TP inmediato M5.
- [ ] Re-medir ambos: hold_limit debe caer, PF debe sostenerse > 1.

---

> **Nota de veracidad**: la jerarquía está en el código (TF_FREQ, build_signals_from_frames, checklist_scalping). Los números de scalping se miden en v30+, no se afirman antes.
