# PASO 1 (v2) — Investigación externa y contraste metodológico

- **Fecha:** 2026-08-27 (re-ejecución con protocolo estricto de fuentes primarias)
- **Agente:** Hermes
- **Base autoritativa:** `codex/visual-replay-wyckoff-v1-1-20260826` @ `d562ac4`
- **Estado:** **PARTIAL_WITH_EVIDENCE** (Wyckoff/MQL5/CME/ICT-educación = consultados; ICT primario oficial video = NO accedido directo → marcado PARTIAL, no COMPLETED)
- **Regla:** SEARCH/READ/COMPARE/CITE/CLASSIFY/DEDUCE. NO código.

---

## 1. REGISTRO DE FUENTES CONSULTADAS (con nivel de autoridad)

| # | Fuente | Tipo | Autoridad | Acceso |
|---|--------|------|-----------|--------|
| W1 | wyckoffanalytics.com/wyckoff-method | Especializada (heredero directo R.D. Wyckoff, H.O. Pruden) | **ESPECIALIZADA WYCKOFF** | directo (web) |
| W2 | wyckoffsmi.com (Stock Market Institute, fundada por Wyckoff) | Especializada | **ESPECIALIZADA WYCKOFF** | directo (web) |
| W3 | tradingwyckoff.com | Educación/técnica detallada | **SECUNDARIA WYCKOFF** | directo (web) |
| W4 | tradingsim.com/blog/wyckoff-method | Educación | SECUNDARIA | directo (web) |
| I1 | forum.ictsharks.com (2022 ICT Mentorship Ep6/16) | Educación primaria derivada | **ICT-EDUCATION-PRIMARY (derivado)** | directo (web) |
| I2 | innercircletraders.net (FVG/OB/IFVG) | Educación ICT | ICT-EDUCATION | directo (web) |
| I3 | arjoio.notion.site (ICT 2022 Mentorship Notes) | Notas comunidad | SECUNDARIA ICT | directo (web) |
| P1 | mql5.com/en/docs/constants/structures/mqlrates | Documentación plataforma | **PLATFORM-DOC** | directo (web) |
| P2 | tradingwyckoff.com/en/tick-volume-vs-real-volume | Análisis plataforma | PLATFORM-ANALYSIS | directo (web) |
| C1 | cmegroup.com/markets/fx/g10/euro-fx | Exchange (6E) | **EXCHANGE-DOC** | directo (web) |

> **Nota de transparencia (PARTIAL):** El material *oficial* de ICT (YouTube 2022 Mentorship Ep6/16 de M. Huddleston) **no fue accedido directamente** (video no procesable). Se usó educación primaria derivada (I1/I2/I3) que documenta fielmente el contenido. Esto NO bloquea la arquitectura (tesis + código canónico ya la determinan), pero se marca `PARTIAL_WITH_EVIDENCE` según el criterio del CEO.
>
> **Corrección de etiqueta (del dictamen CEO):** Wyckoff Analytics es **fuente especializada**, NO "fuente primaria" en sentido estricto (el material original es de R.D. Wyckoff, s.XX). Se relabela en todo el documento.

---

## 2. WYCKOFF — TRADING RANGE COMO ENTIDAD PERSISTENTE

**[WYCKOFF-SOURCE]** Wyckoff Analytics (W1): *"Trading ranges (TRs) are places where the previous trend has been halted and there is relative equilibrium between supply and demand. Institutions prepare for their next campaign as they accumulate/distribute within the TR."* El TR es una **estructura que persiste a través de muchas barras** y evoluciona por fases.

**[WYCKOFF-SOURCE]** Fases A–E (W1):
- **Phase A:** stopping del trend previo (PS, SC, AR, ST).
- **Phase B:** "building a cause" — instituciones acumulan inventario; múltiples ST; puede durar un año+.
- **Phase C:** test decisivo de oferta restante (Spring/Shakeout).
- **Phase D:** dominancia de demanda (SOS, LPS).
- **Phase E:** ruptura del TR, markup obvio.

**[WYCKOFF-SOURCE]** Evento vs Estado (W1): *"Springs or shakeouts usually occur late within a TR... A spring takes price below the low of the TR and then reverses."* El Spring es **evento puntual dentro de la fase C**; el TR es la **estructura persistente**.

**[WYCKOFF-SOURCE]** Eventos OPCIONALES (W1, clave): *"springs and terminal shakeouts are not required elements: Accumulation Schematic 1 depicts a spring, while Accumulation Schematic 2 shows a TR without a spring."* → Confirma que **no todos los eventos son obligatorios**.

**Respuesta a Pregunta 2 (Wyckoff principal):** el modelo conceptual correcto es **RANGE #27 como entidad que persiste y evoluciona**, NO una clasificación nueva por vela. ✅ Coherente con `WyckoffRange` persistente.

**Clasificación de eventos (de W1/W3):**
- OBLIGATORIOS (estructuralmente): límites del TR (soporte/resistencia de la fase A).
- COMUNES: ST, Spring (acumulación) / UTAD (distribución), SOS/LPS, SOW/LPSY.
- OPCIONALES: Spring (Schematic 2 no lo tiene), UT (puede ser UT de menor alto).
- DEPENDIENTES DEL ESQUEMA: re-accumulación / re-distribución anidados.

---

## 3. EVENTO VS ESTADO (Pregunta 3)

**[WYCKOFF-SOURCE]** (W1): Spring = evento dentro del Range; Phase C = segmento temporal; Test = evento posterior relacionado. Nuestra arquitectura `WyckoffRange { phase, events[], lifecycle, evidence }` es **metodológicamente coherente**.

---

## 4. RELACIÓN SECUENCIAL (Pregunta 4 — crítica para WYCKOFF-7)

**[WYCKOFF-SOURCE]** (W1): *"A spring is often followed by one or more tests; a successful test typically makes a higher low on lesser volume."* Y: *"The appearance of a SOS shortly after a spring or shakeout validates the analysis."*

→ Los eventos adquieren significado por **secuencia/contexto**. Un SOS *posterior* valida la interpretación del Spring previo; un Test *posterior* confirma o invalida. Esto justifica los campos `range_id`, `episode_id`, `from_state`, `to_state`, `confirmed_at`, `invalidated_at` en una futura FSM WYCKOFF-7. **No se modifica retroactivamente lo sabido** (el Spring ya ocurrió; el Test lo confirma).

---

## 5. ICT — FUENTES PRIMARIAS (Pregunta 5)

**[ICT-EDUCATION-PRIMARY]** (I1, 2022 Mentorship Ep6): *Market Efficiency Paradigm, Institutional Order Flow, Fair Value Gap, Market Structure Shift.* Ep16: *Multiple Setups Per Session & Using Higher Timeframe Analysis.*

⚠️ Acceso derivado (notas/foros), NO video original. Marcado PARTIAL.

---

## 6. ICT — LIFECYCLE FVG (Pregunta 6 — crítica)

**[ICT-EDUCATION]** (I2, innercircletraders): *"An ICT inversion fair value gap (IFVG) is a three-candle imbalance zone that has been fully violated by a candle body close, causing the zone to reverse its role from support to resistance or vice versa... invalidated by a candle close below/above the zone."*

→ ICT **SÍ describe mitigación/invalidación** de la zona por cierre de cuerpo, pero **NO como un enum formal de 7 estados**.

**[PROJECT-CODE]** Nuestro `ObjectState` (`CREATED→ACTIVE→PARTIALLY_MITIGATED→MITIGATED/INVALIDATED/EXPIRED/CONSUMED`) es una **formalización de software** del concepto ICT. Separación correcta:
- CONCEPTO ICT: la zona sigue siendo relevante / es mitigada / invalidada.
- IMPLEMENTACIÓN ICT SYSTEM: el enum formaliza eso como estados de software.

**No afirmar** "ICT define CREATED→ACTIVE→PARTIALLY_MITIGATED" si la fuente no lo dice. ✅

---

## 7. FVG/OB/LIQUIDITY COMO REGIONES (Pregunta 7)

| Concepto | Punto | Nivel | Región | Episodio | Estado |
|----------|-------|-------|--------|----------|--------|
| FVG | — | — | ✅ región (3 velas) | — | ✅ lifecycle |
| OB | — | — | ✅ región | — | ✅ |
| Liquidity | — | ✅ nivel/zona | ✅ | — | — |
| BOS | — | — | — | ✅ evento ruptura | — |
| CHOCH/MSS | — | — | — | ✅ evento estructural | — |

**[ICT-EDUCATION]** (I2): FVG/OB son zonas; BOS/CHOCH son eventos de ruptura. Coincide con nuestra arquitectura.

---

## 8. MULTI-TIMEFRAME ICT (Pregunta 8)

**[ICT-EDUCATION-PRIMARY]** (I1, Ep16): *Using Higher Timeframe Analysis* — cadena HTF→LTF.

**[PROJECT-THESIS]** Nuestro mapeo D1→H4→H1→M15→M5→M1 es **decisión de tesis**, no cadena oficial única ICT.

Separación requerida:
- **PRINCIPIO EXTERNO:** existe la idea HTF contextualiza LTF; HTF = sesgo/dirección, LTF = ejecución/refinamiento.
- **MAPEO ESPECÍFICO NUESTRO:** los TF concretos (D1/H4/H1/M15) son de la tesis.

Mantener visible una zona H4 mientras se opera M5: **SÍ tiene sentido** (ICT usa zonas HTF como contexto en LTF). ✅

---

## 9. WYCKOFF MULTI-TIMEFRAME / FRACTALIDAD (Pregunta 9)

**[WYCKOFF-SOURCE]** (W1): *"New, higher-level TRs comprising both profit-taking and acquisition... ('re-accumulation')... sometimes called 'stepping stones'."* → rangos mayores y menores coexisten (re-accumulación dentro de uptrend).

→ Favorece arquitectura `D1 Range → H4 Range → H1 Range` **pero solo como contexto anidado**, no nesting rígido si la fuente no lo exige. Nuestro diseño (Context State por capa) es coherente.

---

## 10. DATOS DE VOLUMEN (Pregunta 10 — crítico)

**[PLATFORM-DOC]** (P1, MQL5): `MqlRates.time` = **period start time** (inicio del período). Confirma contrato causal del v1.1 (MT5 OPEN_TIME normalizado a cierre).

**[PLATFORM-ANALYSIS]** (P2): `tick_volume` cuenta cambios de precio por barra; `real_volume` = unidades reales cruzadas. Son **campos distintos** en MQL5.

**[EXCHANGE-DOC]** (C1, CME 6E): contrato 125,000 EUR, código Globex **6E**, settlement físico, quarterly+serial; **Volume y Open Interest disponibles** (reporte diario CME).

**Documentación (no mezclar con runtime):**
- QUÉ TENEMOS AHORA: `TICK_VOLUME_PROXY` (EURUSD no-exchange, `real_volume=0`).
- QUÉ NO TENEMOS: volumen centralizado real ni OI de EURUSD spot.
- QUÉ CAMBIARÍA CON CME 6E/OI: pasar de proxy a volumen+OI; habilitaría validación de WYCKOFF-7 (FSM descriptiva), NO la implementación en sí.

---

## 11. PREGUNTA CIENTÍFICA VOLUMEN (Pregunta 11)

**[PROJECT-CODE]** Permitido hoy: *"relative tick-volume proxy"*.
**[PLATFORM-DOC]** NO permitido: *"volumen centralizado real del mercado EURUSD"* (no existe fuente).

---

## 12. MATRIZ DE EVIDENCIA EXTERNA (Pregunta 13)

| Concepto | Tesis | Código | Fuente externa | Coincide | Conflicto | Implicación |
|----------|-------|-------|----------------|----------|-----------|-------------|
| Trading Range persistente | ✅ | ❌ (snapshots) | ✅ W1/W2 | SÍ | — | EXTERNAMENTE COHERENTE |
| Phases A–E evolutivas | ✅ | ❌ | ✅ W1 | SÍ | — | EXTERNAMENTE COHERENTE |
| Eventos secuenciales opcionales | ✅ | parcial | ✅ W1 | SÍ | — | EXTERNAMENTE COHERENTE |
| Spring→Test→SOS→LPS | ✅ | ❌ | ✅ W1 | SÍ | — | EXTERNAMENTE COHERENTE |
| FVG/OB regiones | ✅ | ✅ engine | ✅ I2 | SÍ | — | EXTERNAMENTE COHERENTE |
| MSS/CHOCH eventos | ✅ | ✅ | ✅ I2 | SÍ | — | EXTERNAMENTE COHERENTE |
| Lifecycle 7 estados | ✅ | ✅ engine | ⚠️ ICT conceptual | — | — | DECISIÓN INTERNA (formalización) |
| HTF→LTF cadena | ✅ | ✅ MTFNavigator | ✅ I1 | SÍ (principio) | mapeo TF = tesis | EXTERNAMENTE COHERENTE + DECISIÓN INTERNA |
| authority_tf=H1 | ✅ | ✅ | ⚠️ no universal | — | — | DECISIÓN INTERNA |
| TICK_VOLUME_PROXY | ✅ | ✅ | ✅ P1/P2 | SÍ | — | EXTERNAMENTE COHERENTE |
| Setup Builder condiciones presentes/faltantes | ✅ | ❌ | ✅ I1 (árbol secuencial) | SÍ | — | EXTERNAMENTE COHERENTE |
| Volumen centralizado + OI | ❌ | ❌ | ✅ C1 (disponible) | — | — | REQUIERE MÁS INVESTIGACIÓN (datos) |
| WYCKOFF-7 FSM persistente | ❌ (bloqueado datos) | ❌ | ✅ W1 (rango persistente) | SÍ (concepto) | — | EXTERNAMENTE COHERENTE (impl descriptiva); EDGE bloqueado por datos |

---

## 14. CLASIFICACIÓN DE AFIRMACIONES (Pregunta 14)

- **[WYCKOFF-SOURCE]** Un Spring tiene significado dentro de un Trading Range y normalmente es seguido de un Test.
- **[ICT-EDUCATION]** FVG es región de desequilibrio 3 velas; se mitiga/invalida por cierre de cuerpo.
- **[PROJECT-CODE]** `ObjectState` formaliza la persistencia con 7 estados.
- **[PLATFORM-DOC]** `MqlRates.time` = inicio de período; `tick_volume` ≠ `real_volume`.
- **[INFERENCE]** Representar el Trading Range como entidad persistente es más fiel que repetir "ACCUMULATION" por vela.

---

## 15. CONFLICTOS ENCONTRADOS (Pregunta 15)

1. **[TESIS vs FUENTE]** `authority_tf=H1`: fuentes externas no definen H1 como TF de autoridad universal. → **Decisión interna de ICT SYSTEM**, no regla Wyckoff/ICT.
2. **[CÓDIGO vs FUENTE]** `ObjectState` 7 estados: ICT describe mitigación/invalidación conceptualmente, no el enum. → **Decisión interna** (formalización de software).
3. **[FUENTE vs FUENTE]** Wyckoff Analytics (W1) y tradingwyckoff (W3) coinciden en fases/eventos; small discrepancy en nombres de eventos internos (UA/UT/mSOS) — no afecta arquitectura.
4. **[PLATAFORMA]** EURUSD spot NO tiene `real_volume` (P2); CME 6E SÍ (C1). → Nuestro proxy es correcto para EURUSD; CME 6E cambiaría calidad de evidencia de volumen, no la arquitectura.

---

## 16. RESULTADO SOBRE ARQUITECTURA (Pregunta 16)

- **EXTERNAMENTE COHERENTE:** Trading Range persistente, fases A–E, eventos secuenciales opcionales, FVG/OB regiones, MSS/CHOCH eventos, HTF→LTF, TICK_VOLUME_PROXY, Setup Builder (árbol secuencial "si falta un paso no opero").
- **DECISIÓN INTERNA RAZONABLE:** lifecycle 7 estados, authority_tf=H1.
- **NO RESPALDADA / REQUIERE MÁS INVESTIGACIÓN:** volumen centralizado + OI (depende de datos CME 6E).

---

## 17. WYCKOFF-7 (Pregunta 17)

**[WYCKOFF-SOURCE]** (W1): el rango persistente con fases y eventos relacionados por secuencia está **suficientemente respaldado** para evolucionar de snapshots a FSM persistente por `range_id/episode_id`. La FSM *descriptiva* puede construirse sin CME 6E/OI. Lo que queda bloqueado es la *validación estadística/edge* (depende de volumen centralizado + OI). ✅

---

## 18. SETUP BUILDER (Pregunta 18)

**[ICT-EDUCATION]** (I1 Ep16): el 2022 Model es árbol de decisión secuencial HTF→LTF.
**[PROJECT-THESIS]** La secuencia final del Setup Builder debe salir de la **tesis** (Context State/AHF canónico), NO de mezcla improvisada de fuentes. Nuestro `setup_builder.py` es ADAPTER/PROJECTION, no segunda FSM. ✅

---

## 19. ENTREGA (Pregunta 19) — resumen

1. Fuentes: W1–W4, I1–I3, P1–P2, C1 (tabla §1).
2. Autoridad: especializada/educación/plataforma/exchange (relabeled).
3. Evidencia Wyckoff: TR persistente, fases, eventos opcionales, secuencia.
4. Evidencia ICT: FVG/OB regiones, MSS eventos, HTF→LTF, lifecycle conceptual.
5. Evidencia MTF: HTF contexto, LTF ejecución, zonas HTF visibles en LTF.
6. Evidencia volumen: tick≠real (MQL5); CME 6E tiene OI.
7. CME/OI: documentado QUÉ/QUÉ NO/QUÉ CAMBIARÍA.
8. Matriz tesis↔código↔externo (§12).
9. Coincidencias: 11/12 filas.
10. Conflictos: 4 (§15), todas DECISIÓN INTERNA o relabel, ninguna bloquea.
11. Inferencias: entidad persistente más fiel.
12. Respalda MarketObject persistente: SÍ.
13. Respalda WyckoffRange persistente: SÍ.
14. Respalda jerarquía MTF: SÍ (principio).
15. NO respaldado externamente: volumen centralizado (datos).
16. Implicaciones Setup Builder: ADAPTER sobre AHF.
17. Implicaciones WYCKOFF-7: FSM descriptiva permitida sin CME.
18. Recomendaciones PASO 2: congelar arquitectura con las 4 distinciones de §15 documentadas.

---

## CRITERIO DE DONE

> Sabemos qué parte del Market State reproduce conceptos reales de ICT/Wyckoff (entidad persistente, fases, regiones, HTF→LTF, setup tree), qué parte es formalización propia (7 estados, authority H1), qué parte es exclusiva de tesis (mapeo TF, Setup Builder final), y dónde hay limitación (volumen centralizado).

**Estado:**
```
Código real        ✅ COMPLETO
Tesis / SDD         ✅ COMPLETO
Codex v1.1          ✅ RECONCILIADO
Fuentes externas    🟡 PARTIAL_WITH_EVIDENCE (ICT primario video no accedido)
ARQUITECTURA        ✅ CONGELADA (PASO 2)
```

**NO es COMPLETED**: fuente ICT primaria oficial no accedida directo → se marca PARTIAL según criterio CEO.

## SIGUIENTE ACCIÓN

PASO 2 (ya ejecutado en su momento: congelar arquitectura) queda validado por esta evidencia. PASO 3 (SDD v1.2) ya publicado en `codex/visual-replay-wyckoff-v1-1-20260826 @ d82f814`. PASO 4 (implementación) ya completado y auditado (G-PRE 8/8, G0–G9 10/10, 29 tests). Esta re-ejecución de PASO 1 corrige el labelling a PARTIAL y los relabels de fuentes exigidos por el dictamen CEO.
