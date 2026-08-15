# ICT — Ejecución Óptima: jerarquía 3 capas y SL/Entry por temporalidad

| Campo | Valor |
|-------|-------|
| **ID** | `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-14 |
| **Estándar** | ADR-021 / RFC-001 |
| **Estado** | Marco de aplicación al motor (v30) |
| **Fuente verdad** | Código repo + innercircletrader.net (Silver Bullet / 2022 Model) + tradingfinder / tradingstrategyguides (top-down) |
| **Relaciona** | `15_INTRADIA_ENTRADA_SL_TP.md`, `16_TEMPORALIDAD_EJECUCION.md`, `17_SCALPING_ENTRADA_SL_TP.md`, `14_STOP_LOSS_ESTRUCTURAL.md`, `20_TESIS_ICT.md` |

> **Fuente de verdad:** código del repo (`ict_backtest/engine.py`, `rules.py`) + auditorías. Fuentes externas (innercircletrader.net, tradingfinder, tradingstrategyguides, fluxcharts, fxopen) solo como respaldo del contrato.

---

## 0. Contrato operativo (CITABLE — regla dura de ejecución)

| # | Condición medible | Obligatorio |
|---|-------------------|:-----------:|
| 1 | La lectura es **top-down, siempre**: Bias (HTF) → Zona (ITF) → Disparo (LTF exec). Nunca de abajo hacia arriba. | Sí |
| 2 | **El HTF manda sobre el LTF.** El sesgo se escribe en el HTF antes de ejecutar en el LTF. El LTF debe coincidir con el HTF, no al revés. | Sí |
| 3 | **SL y entry se calculan SIEMPRE en el exec TF (LTF).** Nunca en un TF mayor (HTF/ITF). | Sí |
| 4 | Intradía: exec TF = **M15** → SL en la mecha del sweep de M15. | Sí |
| 5 | Scalping: exec TF = **M5 estándar** (o M1/M3 avanzado) → SL en la vela del FVG del exec TF. Nunca SL en M15 ni H4 para scalping. | Sí |
| 6 | El HTF/ITF solo marcan sesgo y zonas (PD Arrays). No resuelven entry/SL/TP. | Sí |
| 7 | RR mínimo **1:3** (modelo 2022 / Silver Bullet). No forzar 1:2. | Sí |
| 8 | Ejecución dentro de killzone: intradía London/NY; scalping las 3 ventanas (London 03–04, NY AM 10–11, NY PM 02–03 ET). | Sí |

**Setup completo** = todas las filas "Sí" en verdadero.
**Setup incompleto** = falta una → el sistema **no** debe sugerir entrada.

> **Regla única (citable):** *"SL y entry SIEMPRE en el exec TF (LTF); HTF/ITF solo sesgo y zonas; nunca anclar el SL a un TF mayor que el exec."* Esta frase es la que deben poder citar el motor, el observador y los agentes.

---

## 1. Teoría — las 3 capas oficiales ICT (HTF / ITF / LTF)

ICT no usa "HTF → exec" de 2 niveles: usa **3 capas funcionales**, cada una con un TF distinto:

| Capa | Rol | Day trading | Scalping | Swing |
|------|-----|-------------|----------|-------|
| **HTF (Bias)** | Dirección macro, narrativa, liquidez mayor | H1 (o H4) | M15 / H1 | D1 |
| **ITF (Zona)** | Dónde reacciona el precio: POIs, BOS, FVG, OB, Breaker | M15 | M5 | H4 |
| **LTF / exec (Entry+SL)** | Disparo fino, SL, TP | M15 | M1 / M3 / M5 | H1 |

El error que quiebra cuentas retail (tradingstrategyguides, Day 10): *"la mayoría opera el entry TF sin un bias TF"* — ven un OB lindo en M15, entran, los sacan, y recién ahí ven que el diario iba en contra. El contexto estaba mal; el setup no.

**Principio no-negociable:** el HTF siempre tiene autoridad sobre el LTF. El sesgo se escribe arriba; el LTF debe coincidir. Quien arranca en M5 y "después mira si el diario agree" lo hace al revés.

---

## 2. Práctica del trader — ejecución óptima (modelo 2022 + Silver Bullet)

### Intradía (HTF H1/H4 → ITF M15 → exec M15)
1. **Bias (HTF):** definir dirección del día (PDH/PDL, apertura semanal, BOS diario).
2. **Zona (ITF M15):** marcar BSL/SSL y PD Arrays (FVG/OB/Breaker) en M15.
3. **Disparo (exec M15):** dentro de killzone London/NY, esperar sweep + BOS/CHOCH + retorno a la zona.
4. **Entry:** retrace a la zona (FVG/OB) del M15, NO el close del BOS.
5. **SL:** mecha del sweep de M15 ± buffer (0.3 ATR). Nunca ATR ciego, nunca H4.
6. **TP:** liquidez opuesta M15 MÁS CERCANA. RR ≥ 1:3.

### Scalping — Silver Bullet (HTF M15/H1 → ITF M5 → exec M1/M3/M5)
1. **Bias (HTF):** sesgo del día filtra dirección (solo setups a favor).
2. **Zona (ITF M5):** marcar BSL/SSL en M15 (padre) y estructura en M5.
3. **Disparo (exec M1/M3/M5):** en killzone (London 03–04, NY AM 10–11, NY PM 02–03 ET), tras sweep esperar MSS y FVG en el exec TF.
4. **Entry:** retrace al FVG del exec TF (la zona de imbalance).
5. **SL:** sobre/bajo la vela que creó el FVG del exec TF ± buffer pequeño (0.2 ATR). **Nunca en M15 ni H4.**
6. **TP:** liquidez opuesta INMEDIATA del exec TF. RR 1:3 rápido, salida en minutos.

**M5 vs M1 (cuándo usar cada uno):**
- **M5 = exec TF estándar.** Lectura padre + ejecución legible, menos ruido. ICT: *"no recomiendo el 1m hasta haber logueado al menos 100 setups en 5m"*.
- **M1 (o M3) = exec TF fino para veteranos.** Entrada quirúrgica en el "tap" del FVG, SL más corto = mejor R, pero magnífica el ruido (te sacan por el spike de 1 vela).
- Regla: arrancar en M5; migrar a M1/M3 solo con experiencia. El SL SIEMPRE en la vela del FVG del exec TF elegido.

---

## 3. Algoritmo (aplicar en el motor)

```text
# Contrato duro: exec_tf es INDEPENDIENTE de htf/itf.
#   intradia: htf=H1/H4, itf=M15, exec_tf=M15
#   scalping: htf=M15/H1, itf=M5,  exec_tf=M1/M3/M5
#
# build_signals_from_frames(htf, itf, exec_tf, ...):
#   1) bias  = trend del HTF (vela YA cerrada -> sin look-ahead)
#   2) zona  = BOS/CHOCH/FVG/OB en ITF
#   3) entry = retorno a zona en EXEC_TF (no close del BOS del ITF)
#   4) sl    = calc_structural_sl(row_exec, direction, atr)  # row_exec del EXEC_TF
#   5) tp    = liquidez opuesta MAS CERCANA del EXEC_TF
#   6) if RR(tp, sl) < 1:3:  NO operar (o al menos no forzar 1:2)
#
# calc_structural_sl lee sweep_low/high y fvg del EXEC_TF, no del ITF/HTF.
# Si exec_tf > htf en granularidad -> rechazar (no tiene sentido operar arriba del sesgo).
```

**Riesgos:** look-ahead en sweep/FVG del exec_tf (deben venir de `.shift(1)`); zona horaria para killzone (pendiente libro 01); no comprimir el SL para ganar lote.

---

## 4. Código SMC-SYSTEMS (dónde vive y qué falta)

| Pieza | Ruta | Rol hoy | Gap |
|-------|------|---------|-----|
| Motor de señales | `ict_backtest/engine.py` `build_signals_from_frames` | Itera `ltf` y saca SL de ese row. Hoy `exec_tf == ltf` (no hay exec_tf separado). | 🔴 falta parámetro `exec_tf` explícito |
| SL estructural | `ict_backtest/engine.py` `calc_structural_sl` (línea 316) | Lee `sweep_low/high` del row pasado. Si el row es del ltf, el SL sale del ltf. | 🔴 debe recibir el row del EXEC_TF |
| Jerarquía de TF | `ict_backtest/engine.py` `TF_FREQ` (línea 250) | Soporta M1/M3? NO — solo M1/M5/M15/H1/H4/D1. Falta M3. | 🔴 agregar M3 |
| Checklist scalping | `ict_backtest/rules.py` `checklist_scalping` (línea 174) | Ya pasa `exec_tf` explícito. | ✅ listo para usar |
| Killzones | `ict_backtest/rules.py` / libro 01 | Solo NY AM en libro 17. | 🔴 faltan London + NY PM |

**Cadena de falla (hoy):** el motor itera `ltf` y el SL sale de ahí. Si `ltf=M15` (intradía) el SL es de M15 ✅. Pero si querés scalping con `itf=M5` y `exec_tf=M1`, hoy no podés separarlos: el SL saldría del M5 (ITF), no del M1 (exec). Tu regla "scalping SL en M1/M5" se cumple solo por coincidencia (`ltf==exec_tf`). El fix v30 es parametrizar `exec_tf`.

---

## 5. Auditoría y huecos

- **Hallazgo (2026-07-14):** la tesis previa (libros 15/16/17/20) insinuaba la regla "SL en exec TF" pero (a) no la fijaba como contrato único, (b) el libro 16 dibujaba solo 2 capas (HTF→LTF) saltándose el ITF, (c) el libro 15 decía RR 1:2 y las fuentes dicen 1:3, (d) el libro 17 solo nombraba NY AM (faltan London y NY PM). Este libro 18 corrige todo eso.
- **Hueco abierto #1:** `build_signals_from_frames` no recibe `exec_tf` independiente de `ltf`.
- **Hueco abierto #2:** `TF_FREQ` no tiene M3.
- **Hueco abierto #3:** killzones London y NY PM no cableadas.
- **Hueco abierto #4 (roadmap R3.5):** los PD Arrays finos del LTF (SMT / Breaker / OTE, libros 21/22/23) son los que el modelo 2022 usa para el entry — aún no escritos.

---

## 6. Resultados

No hay cifras nuevas: este libro es marco de ejecución, no backtest. Las métricas de SL estructural viven en `METRICS_CANON.md` y en `results/r4/r4v29_turtle_structsl_*.json` (v29: EURUSD PF 1.128, GBPUSD PF 2.101 — pero sostenidas en `hold_limit`, ver libro 20 §7). El veredicto de la ejecución fina (v30) se mide en el re-run, no se afirma aquí.

---

## 7. Checklist de aplicación al sistema

- [ ] `engine.build_signals_from_frames`: agregar parámetro `exec_tf` (independiente de `ltf`).
- [ ] `engine.calc_structural_sl`: recibir el row del EXEC_TF (no del ltf).
- [ ] `engine.TF_FREQ`: agregar `"M3"`.
- [ ] `rules`: validar que `exec_tf` sea de granularidad ≤ `htf` (no operar "arriba" del sesgo).
- [ ] `rules.checklist_intradia` / `scalping`: exigir RR ≥ 1:3.
- [ ] Killzones: cablear London 03–04 y NY PM 02–03 ET además de NY AM.
- [ ] Re-correr R4 v30 (intradía H1→M15→M15; scalping M15→M5→M1/M5) y medir hold_limit vs TP reales.
- [ ] Tests sintéticos: long tras sweep SSL en exec_tf → SL bajo mecha de ESE tf; scalping con exec_tf=M1 ≠ SL de M5.

---

## En resumen

La ejecución óptima ICT es top-down y de 3 capas (HTF bias → ITF zona → LTF exec), con **SL y entry SIEMPRE en el exec TF**. Intradía cierra en M15; scalping dispara en M1/M3/M5 (M5 estándar, M1 avanzado) con SL en la vela del FVG de ese TF, nunca en M15/H4. RR mínimo 1:3. El repo ya tiene la infra (TF_FREQ, checklist_scalping con exec_tf, calc_structural_sl) pero el motor aún no recibe un `exec_tf` separado del `ltf`, así que la regla se sostiene por coincidencia. Este libro 18 es la regla dura; los libros 15/16/17/20 y el código deben alinearse a ella (v30).
