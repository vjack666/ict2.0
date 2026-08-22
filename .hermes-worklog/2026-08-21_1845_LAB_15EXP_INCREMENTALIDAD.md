# Bitácora — LAB 15 EXP: Incrementalidad HTF (Agente B serial) + cierre A/B/C

**Fecha:** 2026-08-21 18:45–19:23 UTC-5
**Autor:** Hermes (jefe de laboratorio) — Agentes A/C previos (10 JSON), Agente B re-despachado como 5 micro-agentes en SERIE (concurrencia 1) para evitar rate-limit (HTTP 429) que había truncado los intentos paralelos.
**Rama:** feature/a5-audit-datos (commit daef67cf)
**Motor:** run_sequential (structure_mode="lite", depth>=4) + resolve_outcome (SL estructural 2-términos, TP measured_projection, horizonte 200, tie=pessimistic, bootstrap 2000 seed 42, wilson 95%)

---

## Diseño del laboratorio (3 agentes × 5 experimentos = 15)

| Agente | Rol | Pregunta científica |
|---|---|---|
| A — Aislamiento | ¿Qué componente produce el efecto? | 5 exp mono-TF |
| B — Incrementalidad | ¿El contexto HTF aporta información incremental vs baseline LTF? | 5 exp multi-TF |
| C — Falsación | ¿Dónde se rompe el edge fuera de muestra? | 5 exp robustez |

**Contrato estricto aplicado:** invariantes (mismo motor/commit, mismos SL/TP, seed 42, bootstrap 2000), 4 estados (PASS/FAIL/BLOCKED/INVALID), salida raw+audit separada, hipótesis congeladas, dataset hasheado (EURUSD_H1 CSV SHA256=2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022).

**Nota de ejecución B:** los 2 intentos paralelos previos de B fueron truncados por rate-limit (429 / max_iterations) sin escribir JSON. Se re-diseñó como 5 micro-agentes en SERIE (1 a la vez, concurrencia máxima 1) → 5/5 completados y escritos en disco. build_features D1/H4 verificado PIT-estable (0/5 violaciones FULL-vs-PREFIX) → filtros HTF ejecutables sin deuda PIT.

---

## Cuadro de 15 gates (verificado en disco, no en resumen)

### Agente A — Aislamiento
| Exp | Componente | TF | Veredicto | Métrica |
|---|---|---|---|---|
| A1 | Anclaje d≥4 vs FVG-aleat, defensa pareja | H1 | ✅ PASS | n=211, WR 54.98%, meanR +0.250, IC [0.094,0.408] |
| A2 | TP liquidez HTF real | H1 | ⛔ BLOCKED | navigator HTF→LTF con deuda PIT sin resolver |
| A3 | Mismo anclaje H4 | H4 | ❌ FAIL | n=51, meanR +0.054, IC lb −0.24 (cruce 0) |
| A4 | Mismo anclaje M15 | M15 (parquet, origen distinto) | ✅ PASS | n=303, meanR +0.147 |
| A5 | Profundidad d3/d4/d5 | H1 | ✅ PASS(d4)/d3 FAIL/d5 BLOCKED | d4 meanR +0.250; d3≈0; d5 n=23 |

### Agente B — Incrementalidad (HTF vs baseline LTF B1)
| Exp | Filtro | Veredicto gate | meanR (trat) | n | Δexpectancy vs B1 | Incremental |
|---|---|---|---|---|---|---|
| B1 | Baseline LTF (sin HTF) | ✅ PASS | +0.2499 | 211 | control | — |
| B2 | + D1 | ❌ FAIL | +0.1438 | 97 | **−0.1061 R** | no aporta (daña) |
| B3 | + H4 | ✅ PASS | +0.3205 | 80 | +0.0706 R | IC cruza 0 |
| B4 | D1+H4 top-down | ✅ PASS | +0.3528 | 45 | +0.1029 R | IC cruza 0 |
| B5 | Apareado con/sin HTF (D1 OR H4) | ❌ FAIL | +0.1796 | 132 | **−0.0703 R** | no aporta (IC cruza 0) |

### Agente C — Falsación
| Exp | Componente | Veredicto | Métrica |
|---|---|---|---|
| C1 | GBPUSD (parquet MT5) | ✅ EDGE VIVO | meanR +0.258, IC [0.094,0.429] |
| C2 | XAUUSD (parquet MT5) | ❌ EDGE ROTO | meanR +0.137, IC [−0.06,0.34] |
| C3 | EURUSD OOS 2025 | ⛔ BLOCKED | n=24 < 30 |
| C4 | EURUSD + costes reales | ✅ EDGE VIVO | meanR +0.233, IC [0.079,0.392] |
| C5 | Walk-forward 4 ventanas | ❌ INESTABLE | 2/4 con edge; slope +0.13 (decae) |

**Árbitro de protocolo (B1-B5):** leakage_check OK (PIT 0/5 violaciones), parameter_change=false en todos → veredictos válidos, no anulados.

---

## Veredicto por proposición (científico, no por agente)

- **P1 — Existe edge LTF depth≥4 sobre FVG-aleatorio:** ✅ RESPALDADA (A1 PASS, A4 PASS M15, C4 PASS con costes).
- **P2 — El contexto HTF aporta expectancy incremental sobre el baseline LTF:** ❌ **REFUTADA**. B2 daña (−0.11R), B3/B4 mejoran en punto pero IC cruza 0, B5 (prueba más rigurosa, mismo set apareado) reduce (−0.07R, IC incluye 0). Bajo este protocolo exacto, el filtro de sesgo HTF direccional NO mejora el edge LTF depth≥4.
- **P3 — Robustez fuera de muestra:** ⚠️ PARCIAL. Vive en GBPUSD (C1) y con costes (C4); se ROMPE en XAUUSD (C2) e INESTABLE en el tiempo (C5). EURUSD OOS 2025 deshabilitado (C3 n=24).

---

## Conclusión del jefe de laboratorio (honesta)

1. El edge de ICT en EURUSD H1 **vive en el anclaje secuencial LTF depth≥4**, no en el contexto HTF como filtro de sesgo direccional.
2. La tesis "HTF dirige, LTF ejecuta" **queda REFUTADA como filtro de sesgo** en este setup: añadir D1/H4 no mejora (y a veces daña) la expectancy del baseline LTF.
3. El edge es **real pero no universal**: sobrevive costes y GBPUSD, muere en XAUUSD y es inestable temporalmente.
4. **NO se promueve a señal de trading.** Ningún experimento del lab es aprobación de operación. El edge es objeto de estudio; las deudas (TP HTF real A2 BLOCKED, OOS 2025 C3 BLOCKED, inestabilidad C5) siguen abiertas.

**Siguiente paso sugerido (no ejecutado):** cerrar las deudas A2 (TP liquidez HTF real vía navigator PIT-stable) y C3 (OOS 2025 con más barras o rango extendido) antes de cualquier promoción. Luego, si el usuario quiere, activar Agente D (evolución: propone modificación del motor) y Agente E (red-team) sobre el edge LTF aislado.

**Archivos entregados:** 30 JSON (EXP_A1-A5 ×2, EXP_B1-B5 ×2, EXP_C1-C5 ×2) en reports/audits/. Runners/harness de apoyo en scripts/lab/experiments/. Sin commit ni push en esta bitácora (el commit se hace por separado con el índice).
