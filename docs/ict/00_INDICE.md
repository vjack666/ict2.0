# Biblioteca ICT — Índice (v2 · estándar 10/10)

Colección de reglas ICT (Inner Circle Trader) **operativas y trazables** para SMC-SYSTEMS.  
Cada archivo es un “libro”. La app y los agentes deben poder **citar el contrato §0** y el código.

> **Fuentes externas** (innercircletrader.net, fluxcharts, MQL5, alchemy, etc.) son respaldo.  
> **Fuente de verdad:** código del repo + auditorías + [METRICS_CANON](../METRICS_CANON.md).  
> No sustituyen el ICT Mentorship de pago.

**Estándar de escritura:** [ADR-021](../plan/ADR-021_filosofia_documentacion_ict.md) · plantilla [`_PLANTILLA_LIBRO.md`](_PLANTILLA_LIBRO.md).  
**Aplicación al sistema:** [ROADMAP_BIBLIOTECA_Y_APLICACION](../plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md).

---

## Libros de setup (ICT)

| ID | Libro | Contrato clave | Estado docs |
|----|-------|----------------|-------------|
| 01 | [Killzones](01_KILLZONES.md) | Ventana horaria unificada | ✅ 2.0 · Needs-code TZ |
| 02 | [MSS / CHoCH / BOS](02_MSS_CHOCH.md) | Secuencia BOS→CHOCH→BOS | ✅ 2.0 |
| 03 | [FVG](03_FVG.md) | 3 velas + unfilled | ✅ 2.0 |
| 04 | [Order Blocks](04_ORDER_BLOCKS.md) | Huella + followthrough post-cierre | ✅ 2.0 |
| 05 | [Liquidez / Sweep](05_LIQUIDEZ.md) | Sweep = filtro; unificar fuente | ✅ 2.0 · Needs-code |
| 06 | [Turtle Soup](06_TURTLE_SOUP.md) | Contratrend + sweep + giro | ✅ 2.0 · Needs model split |
| 07 | [Silver Bullet](07_SILVER_BULLET.md) | KZ + sweep + FVG + sesgo | ✅ 2.0 |
| 08 | [**Power of Three (pasado/presente/futuro)**](08_POWER_OF_THREE.md) | **A+M+D complete** | ✅ 2.0 · **Prioridad R1** |
| 16 | [Temporalidad de ejecución](16_TEMPORALIDAD_EJECUCION.md) | HTF→ITF→exec; marco v30 | 📝 1.0 |
| 17 | [Scalping (Silver Bullet) entry/SL/TP](17_SCALPING_ENTRADA_SL_TP.md) | exec M1/M3/M5; TP inmediato | 📝 1.0 · Propuesta v30 |
| 18 | [**Ejecución óptima: 3 capas + SL/Entry por TF**](18_EJECUCION_OPTIMA_TF_SL_ENTRY.md) | **Regla dura**: SL/entry SIEMPRE en exec TF; RR 1:3; 3 killzones | 📝 1.0 · Marco v30 |
| 20 | [**TESIS ICT COMPLETA**](20_TESIS_ICT.md) | Unifica PO3+liquidez+temporalidad+POI | 📝 1.0 · Síntesis |
| 21 | [**Point of Interest (POI)**](21_POI.md) | POI = PD Array en zona correcta + sesgo + respaldo; tiers; stacking MTF; **bonus, no filtro duro** | 📝 1.0 · Marco v30+ |

## Libros de integración / validación

| ID | Libro | Notas |
|----|-------|-------|
| 09 | [Optimizador bayesiano](09_OPTIMIZADOR_BAYESIANO.md) | **Anexo** de validación, no setup ICT |
| 10 | [Sweep + OTE filtros](10_SWEEP_OTE_FILTRO.md) | Ítem D; OTE casi no-op |
| 11 | [Manual vs Auto](11_SWEEP_OTE_MANUAL_VS_AUTO.md) | Política híbrida / automation-ready |
| 13 | [**Backtest profesional**](13_BACKTEST_PROFESIONAL/00_INDICE.md) | Reloj MTF, fill, costos, OOS, **gap G1–G12** · Plan R6 |
| 14 | [Stop Loss Estructural](14_STOP_LOSS_ESTRUCTURAL.md) | SL = mecha sweep, no ATR · aplicado v29 |
| 16 | [Temporalidad de ejecución](16_TEMPORALIDAD_EJECUCION.md) | HTF→LTF→exec; marco v30 | 📝 1.0 |

## Auditoría y SDD (no “libros de setup”, pero del pack ICT)

- `10_AUDITORIA_REFACCION/` — hallazgos #1–#7  
- `13_BACKTEST_PROFESIONAL/` — estándar de veracidad del backtest (2026-07-13)  
- `SDD_ICT_BACKTEST.md`, `SDD_REFACCION_2026-07-11.md`  
- `API_SPEC.md`, `TEST_PLAN.md`  
- `logs/` — corridas Capa 2/3  

---

## Cómo se usa en SMC-SYSTEMS

| Capa | Rol |
|------|-----|
| `detectors/` | Materializa reglas (BOS, CHOCH, OB, FVG, liquidez, KZ) |
| `signals/pipeline.py` | Confluencia / filtros |
| `ict_backtest/` | Misma lógica de checklist que el observador (objetivo) |
| `app_observador` | Cita libros y checklist en pestaña Principal |
| Graphify | Indexa **código**; estos `.md` indexan **teoría** |

Trazabilidad: **regla (§0) → detector → pipeline → backtest → métrica (METRICS_CANON)**.

---

## Orden de lectura recomendado

1. `01` + `02` + `05` (tiempo, estructura, liquidez)  
2. `03` + `04` (zonas)  
3. **`08` PO3** (ciclo completo del trade)  
4. `06` / `07` (variantes contratrend / scalping)  
5. `10` + `11` + `09` (filtros, política, optimización)  
6. **`13` Backtest profesional** (antes de creer cualquier PF)  \
7. **`18` EJECUCIÓN ÓPTIMA** (regla dura: 3 capas HTF/ITF/exec, SL/entry en exec TF, RR 1:3)  \
8. **`20` TESIS ICT COMPLETA** (síntesis unificadora de 01–18)  \
9. **`21` POI** (zona de entrada anclada a narrativa; cierra ontología→biblioteca→código)  \
10. Roadmap de aplicación → código (incl. **R6**)

---

*Biblioteca reescrita 2026-07-12 para calidad 10/10 documental. Los checkboxes de código viven en el roadmap de aplicación.*

---

## Inventario de estrategias materializadas (código ↔ grafo)

- `12_ESTRATEGIAS_COMPLETAS.md` — Inventario real de TODAS las estrategias ICT ya materializadas en código (PO3, Turtle Soup, Silver Bullet, motor event-sequence, pipeline en vivo), anclado al código + grafo. **Creado 2026-07-12:** corrige que el TP/RR YA está implementado en `engine.py` (`fixed2r`/`liquidity`), no es hueco; documenta la fragmentación en 4 islas del grafo (comunidades 0/25/27/197, 0 aristas). [Pendiente revisión Ruben — sin commit.]
