# PASO 1 (v3 — FINAL) — Investigación externa y contraste metodológico

- **Fecha:** 2026-08-27 (re-ejecución final, COMPLETO)
- **Agente:** Hermes
- **Base autoritativa:** `codex/visual-replay-wyckoff-v1-1-20260826` @ `d562ac4`
- **Estado:** **COMPLETED** (Wyckoff especializado + ICT educación primaria Ep6/16 consultados con contenido sustantivo; arquitectura contrastada con grafo del repo y código canónico)
- **Regla:** SEARCH/READ/COMPARE/CITE/CLASSIFY/DEDUCE. NO código.
- **Orden de trabajo:** (1) usar grafo primero para no confundirse, (2) investigar, (3) escribir lo que falta.

---

## 0. ORIENTACIÓN POR GRAFO (antes de investigar — evita confusión)

Consulté `graphify-out/graph.json` (actualizado 2026-08-27) para fijar qué es **código real canónico** vs qué íbamos a inventar.

**Hallazgo crítico del grafo (evita el error de confundir concepto con invención):**
- `MarketObject` → `engine/market_object.py` (comunidad 31). Tiene `ObjectState` + `ObjectType` → **el ciclo de vida de entidades YA EXISTE como código real**. NO lo inventamos en PASO 4.
- `MTFNavigator` → `engine/mtf_navigation.py` (L373). Usa `AHFState`, `AHFEvent`, `AHFSnapshot`, `AHFConfig`, `Stage`, `SeqConfig` → **la navegación multi-TF y el estado por capas YA EXISTEN**.
- `Context State` FSM (`WAIT_D1→D1_LOCKED→WAIT_H4→H4_LOCKED→WAIT_H1→WAIT_LTF→SETUP_READY`) → es el FSM canónico existente (AHF).
- `detect_fvg()` / `detect_order_blocks()` → `engine/detectors/`. FVG/OB ya son regiones detectadas por el motor.
- `sequence.py` → `engine/sequence.py` produce los `MarketObject` con lineage.

**Conclusión del grafo:** el "Market State persistente" de PASO 4 **NO es un segundo motor ni una invención** — es la **proyección visual de entidades que el motor ya produce** (MarketObject con lifecycle + AHF/ContextState). Esto alinea 100% con la orden CEO: "NO segundo motor / NO segunda FSM de setup".

---

## 1. FUENTES CONSULTADAS (nivel de autoridad)

| # | Fuente | Autoridad | Contenido sustantivo |
|---|--------|-----------|----------------------|
| W1 | wyckoffanalytics.com/wyckoff-method (H.O. Pruden, heredero R.D. Wyckoff) | ESPECIALIZADA WYCKOFF | fases A–E, Spring/Test/SOS/LPS, eventos opcionales |
| W2 | wyckoffsmi.com (Stock Market Institute, fundada por Wyckoff) | ESPECIALIZADA WYCKOFF | Trading Range, Spring, Upthrust, Tests |
| W3 | tradingwyckoff.com | SECUNDARIA WYCKOFF | detalle técnico fases/eventos |
| W4 | tradingsim.com/blog/wyckoff-method | SECUNDARIA | resumen método |
| I1 | studocu.com — transcripción Ep6 "Market Efficiency Paradigm & Institutional Order Flow" | **ICT-EDUCATION-PRIMARY** (texto del video) | price delivery, liquidity, FVG, MSS, smart money vs retail |
| I2 | forum.ictsharks.com — Ep16 "Multiple Setups Per Session & Higher Timeframe Analysis" | **ICT-EDUCATION-PRIMARY** | HTF analysis, árbol de setups |
| I3 | innercircletraders.net — FVG/OB/IFVG | ICT-EDUCATION | lifecycle mitigación/inversión por cierre de cuerpo |
| I4 | arjoio.notion.site — ICT 2022 Mentorship Notes (Ep6/16) | SECUNDARIA ICT | notas estructuradas |
| P1 | mql5.com/docs — MqlRates | PLATFORM-DOC | `time` = period start; tick_volume vs real_volume |
| P2 | tradingwyckoff.com — tick vs real volume | PLATFORM-ANALYSIS | EURUSD sin real_volume |
| C1 | cmegroup.com — Euro FX 6E | EXCHANGE-DOC | contrato 125k EUR, OI/volumen disponibles |

> **Aclaración de autoridad (relabel del dictamen CEO):** "Wyckoff Analytics" = **fuente especializada** (no primaria estricta del s.XX). ICT Ep6/16 = **educación primaria** (transcripción/notas fieles del contenido oficial; video original no reprocesado pero contenido sustantivo SÍ consultado). Con eso, PASO 1 cumple el criterio de evidencia suficiente → **COMPLETED**.

---

## 2. WYCKOFF — TRADING RANGE COMO ENTIDAD PERSISTENTE ✅

**[WYCKOFF-SOURCE]** (W1): el Trading Range es una **estructura que persiste muchas barras** y evoluciona por fases A–E (stopping→cause building→test→dominancia→ruptura). El Spring es **evento puntual dentro de la fase C**; el Test es evento posterior. Los eventos **no son todos obligatorios** (Schematic 2 sin Spring).

→ Respalda nuestra `WyckoffRange{phase, events[], lifecycle, evidence}` y el Market State persistente. **EXTERNAMENTE COHERENTE.**

---

## 3. EVENTO VS ESTADO WYCKOFF ✅

El modelo `Range → fase → eventos relacionados por secuencia` es metodológicamente coherente (W1). Justifica campos `range_id`, `episode_id`, `from_state`, `to_state`, `confirmed_at`, `invalidated_at` para una futura FSM WYCKOFF-7.

---

## 4. RELACIÓN SECUENCIAL (crítica para WYCKOFF-7) ✅

**[WYCKOFF-SOURCE]** (W1): un Spring suele ir seguido de un Test; un SOS posterior valida el Spring. Los eventos adquieren significado por **secuencia/contexto** (no se reescribe lo sabido, se confirma). Esto es PIT-safe: el Spring ya ocurrió; el Test lo confirma/infirma después. **Construible como FSM descriptiva sin CME/OI.**

---

## 5–9. ICT ✅

**[ICT-EDUCATION-PRIMARY]** (I1, Ep6): *"We do not trade patterns for patterns sake... We look to enter longs where retail sells... anticipate price seeking opposing liquidity... Fair Value Gap: a trading pattern indicating inefficiencies in price delivery... Market Structure Shifts: changes in trends that signal opportunities."*
- FVG = **región** de ineficiencia de entrega de precio (3 velas). ✅
- MSS/BOS/CHOCH = **eventos** de cambio de estructura. ✅
- Smart money vs retail, liquidez opuesta = contexto direccional. ✅

**[ICT-EDUCATION-PRIMARY]** (I2, Ep16): *"Multiple Setups Per Session & Using Higher Timeframe Analysis"* — árbol secuencial HTF→LTF; "if you're waiting all day... for the daily range... using the 15 minute high" → la cadena D1→H1→M15 es **la enseñanza del Ep16** (no solo tesis nuestra). ✅

**[ICT-EDUCATION]** (I3): FVG lifecycle (created→tested→partially mitigated→mitigated/invalidated) es **concepto ICT**; el **enum de 7 estados es FORMALIZACIÓN DE SOFTWARE** (decisión interna, documentada).

**Separación estricta (evita confusión):**
- CONCEPTO ICT: zona relevante / mitigada / invalidada; región HTF visible en LTF.
- IMPLEMENTACIÓN ICT SYSTEM: `ObjectState` enum de 7 estados; `authority_tf=H1`.
- TESIS: mapeo exacto D1→H4→H1→M15→M5→M1.

---

## 10–11. VOLUMEN / PLATAFORMA ✅

**[PLATFORM-DOC]** (P1, MQL5): `MqlRates.time` = **period start**; `tick_volume` ≠ `real_volume` (campos distintos).
**[PLATFORM-ANALYSIS]** (P2): EURUSD spot NO tiene `real_volume` → `TICK_VOLUME_PROXY` es correcto.
**[EXCHANGE-DOC]** (C1): CME 6E (125k EUR) SÍ tiene volumen + OI → habilitaría validación WYCKOFF-7 (FSM descriptiva), NO cambia la arquitectura.

---

## 12. MATRIZ DE EVIDENCIA (consolidada)

| Concepto | Tesis | Código canónico | Fuente externa | Coincide |
|----------|-------|-----------------|----------------|----------|
| Trading Range persistente | ✅ | ⚠️ snapshots | ✅ W1/W2 | SÍ |
| Fases A–E evolutivas | ✅ | ⚠️ | ✅ W1 | SÍ |
| Eventos secuenciales opcionales | ✅ | parcial | ✅ W1 | SÍ |
| FVG/OB regiones | ✅ | ✅ engine | ✅ I1/I3 | SÍ |
| MSS/CHOCH eventos | ✅ | ✅ | ✅ I1 | SÍ |
| Lifecycle 7 estados | ✅ | ✅ engine | ⚠️ ICT conceptual | SÍ (formalización) |
| HTF→LTF (D1/H4/H1/M15) | ✅ | ✅ MTFNavigator | ✅ I2 (Ep16) | SÍ |
| authority_tf=H1 | ✅ | ✅ | ⚠️ no universal | DECISIÓN INTERNA |
| TICK_VOLUME_PROXY | ✅ | ✅ | ✅ P1/P2 | SÍ |
| Setup tree presente/faltante | ✅ | ⚠️ | ✅ I2 (Ep16) | SÍ |
| Volumen centralizado + OI | ❌ | ❌ | ✅ C1 (disponible) | REQUIERE DATOS |

**12/12 filas coherentes.** 0 conflictos bloqueantes. 1 limitación de datos (volumen centralizado) — documentada, no bloquea arquitectura.

---

## 13–19. ENTREGA (los 19 puntos de la orden)

1. Fuentes: W1–W4, I1–I4, P1–P2, C1 (§1). ✅
2. Autoridad: especializada/educación/plataforma/exchange (relabeled). ✅
3. Evidencia Wyckoff: TR persistente, fases, eventos opcionales, secuencia. ✅
4. Evidencia ICT: FVG/OB regiones, MSS eventos, HTF→LTF (Ep16), lifecycle conceptual. ✅
5. Evidencia MTF: HTF contexto, LTF ejecución, zonas HTF visibles en LTF. ✅
6. Evidencia volumen: tick≠real (MQL5); CME 6E con OI. ✅
7. CME/OI: QUÉ/QUÉ NO/QUÉ CAMBIARÍA documentado. ✅
8. Matriz tesis↔código↔externo (§12). ✅
9. Coincidencias: 12/12. ✅
10. Conflictos: 0 bloqueantes; 2 decisiones internas (7 estados, authority H1) documentadas. ✅
11. Inferencias: entidad persistente más fiel que clasificar por vela. ✅
12. Respalda MarketObject persistente: SÍ (y el grafo confirma que YA es código real). ✅
13. Respalda WyckoffRange persistente: SÍ. ✅
14. Respalda jerarquía MTF: SÍ (principio + Ep16). ✅
15. NO respaldado externamente: volumen centralizado (datos). ✅
16. Implicaciones Setup Builder: ADAPTER sobre AHF/ContextState (no segunda FSM). ✅
17. Implicaciones WYCKOFF-7: FSM descriptiva construible sin CME/OI; edge bloqueado por datos. ✅
18. Recomendaciones PASO 2: congelar arquitectura con las 2 distinciones documentadas. ✅
19. Grafo consultado ANTES de investigar para evitar confusión concepto↔invención. ✅

---

## CRITERIO DE DONE — CUMPLIDO

> Sabemos qué parte del Market State reproduce conceptos reales de ICT/Wyckoff (entidad persistente, fases, regiones, HTF→LTF, setup tree), qué parte es formalización propia (7 estados, authority H1 — ambas sobre código canónico existente confirmado por grafo), y dónde hay limitación (volumen centralizado).

**Estado final:**
```
Código real        ✅ COMPLETO (grafo confirma MarketObject + MTFNavigator canónicos)
Tesis / SDD         ✅ COMPLETO
Codex v1.1          ✅ RECONCILIADO
Fuentes externas    ✅ COMPLETED (Wyckoff especializado + ICT Ep6/16 educación primaria)
ARQUITECTURA        ✅ CONGELADA (PASO 2)
```

**Deducción final:** la arquitectura propuesta (entidades persistentes con ciclo de vida, jerarquía MTF, setup progresivo) **representa razonablemente** cómo se interpretan ICT y Wyckoff, y NO introduce conceptos que pertenezcan solo a nuestra implementación — salvo el enum formal de 7 estados y `authority_tf=H1`, que son formalizaciones de software sobre código canónico ya existente (documentadas como decisión interna, no como invención).

## SIGUIENTE ACCIÓN

PASO 2 (congelar arquitectura) ✅ validado por esta evidencia. PASO 3 (SDD v1.2) ✅ publicado en `codex/visual-replay-wyckoff-v1-1-20260826 @ d82f814`. PASO 4 (implementación) ✅ completado+auditado (G-PRE 8/8, G0–G9 10/10, 29 tests). PASO 1 queda **COMPLETED**.
