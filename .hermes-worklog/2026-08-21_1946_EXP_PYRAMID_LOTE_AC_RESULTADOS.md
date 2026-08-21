# Bitácora — LOTE EXPERIMENTAL PIRÁMIDE 15 · Resultados A+C y cierre parcial

**Fecha:** 2026-08-21 19:46 UTC
**Autor:** ox-alpha (consolidación de resultados verificados en disco)
**Rama:** feature/a5-audit-datos
**Estado:** ✓ 10/15 EJECUTADOS Y VERIFICADOS — B NO EJECUTADO (diseño reconstruido y congelado post hoc) — PROMOCIÓN: BLOCKED

---

## [INICIO]

- **Tarea:** Consolidar en bitácora los resultados del lote experimental
  (pirámide A/B/C, 15 experimentos planificados) con evidencia verificada en
  disco, y dejar registro del estado real del grupo B.
- **Fuente de verdad:** `reports/audits/experiments/current_batch/EXP_*_audit.json`
  y `EXP_*_raw.json` (10 pares), más `EXP_MASTER_RECONCILIATION.json`.
- **Commit de código de los audits:** `daef67cf212c4432c6e5e3a2b7c6cd404982059b`
  (idéntico en los 10 → protocolo congelado, sin cambios de parámetros).

---

## [FASE 1] — RESULTADOS GRUPO A (aislamiento de componentes)

Gate mecánico uniforme: PASS iff n_closed>=30 AND expectancy(mean_r)>0 AND bootstrap CI95 lower>0.

| Exp | Componente aislado | Datos | Veredicto | Métricas clave (tratamiento) |
|-----|--------------------|-------|-----------|------------------------------|
| A1 | Anclaje secuencial depth≥4 vs FVG-aleatorio (defensa pareja) | EURUSD H1 CSV canónico 2019–2024, hash `2dbb5757…` | **PASS** | n=211, WR 54.98% (Wilson [48.2, 61.5]), meanR +0.2499, CI95 [0.094, 0.408]; baseline WR 43.94%, meanR +0.2336 CI [−0.165, +0.867]; ΔWR +10.59pp, ΔmeanR +0.0163 |
| A2 | TP de liquidez HTF real (vs measured_projection fallback) | EURUSD H1 canónico | **BLOCKED** | No ejecutado: TP HTF real requiere navigator HTF→LTF con deuda PIT FULL-vs-PREFIX sin resolver (bitácora 2026-08-20). No se inventa el TP. |
| A3 | Mismo anclaje depth≥4 en H4 | EURUSD H4 CSV canónico, hash `46a950e0…` | **FAIL** | n=51, WR 49.02%, meanR +0.0539, CI95 [−0.240, +0.350] cruza 0. Baseline meanR −0.1289. El tratamiento no se distingue de cero en H4. |
| A4 | Mismo anclaje depth≥4 en M15 | EURUSD M15 **parquet MT5**, hash `336d6f1d…` | **PASS (provisional)** | n=303, WR 52.48% [46.9, 58.0], meanR +0.1472, CI95 [0.028, 0.279]; baseline meanR −0.0448; ΔWR +4.57pp, ΔmeanR +0.192 |
| A5 | Profundidad d3 / d4 / d5 | EURUSD H1 canónico | **PASS global (d4)** | d3: FAIL (n=390, WR 40.26%, meanR −0.0055 ≈ 0). d4: PASS (=A1). d5: BLOCKED (n=23 <30; WR 39.13%, meanR −0.1457 puntual, CI cruza 0 amplio) |

### Caveats declarados en los audits

- **A4 doble caveat:** origen parquet MT5 (no CSV Dukascopy canónico) Y rango
  efectivo **solo 2022–2024** (nota explícita en el audit), no 2019–2024.
  El PASS es provisional hasta replicar sobre dato canónico.
- **A1/A3/A5 mono-TF una pasada:** PIT-estable dentro del rango; la deuda
  FULL-vs-PREFIX afecta al índice HTF del navigator, NO a este diseño.

---

## [FASE 2] — RESULTADOS GRUPO C (falsificación)

| Exp | Componente | Datos | Veredicto | Métricas clave |
|-----|------------|-------|-----------|----------------|
| C1 | Generalización a GBPUSD | GBPUSD H1 parquet MT5 | **PASS (provisional)** | meanR +0.2584, CI95 [0.094, 0.429], n=196 ≥30. Edge vivo fuera de muestra. |
| C2 | Generalización a XAUUSD | XAUUSD H1 parquet MT5 | **FAIL (provisional)** | meanR +0.1365, CI95 [−0.062, +0.340] cruza 0, n=142. Falsación exitosa: el edge NO transfiere a XAUUSD. |
| C3 | OOS estricto EURUSD 2025 | EURUSD H1 CSV canónico | **BLOCKED** | n=24 < 30. Muestra insuficiente; no concluyente. |
| C4 | Costes reales EURUSD | EURUSD H1 CSV canónico | **PASS** | meanR +0.2331, CI95 [0.079, 0.392], n=211. El edge sobrevive costes. |
| C5 | Walk-forward 4 ventanas | EURUSD H1 CSV canónico | **FAIL** | 2/4 ventanas con edge positivo; pendiente temporal slope=+0.12752. Inestabilidad temporal: alguna ventana cae OOS. |

---

## [FASE 3] — ESTADO DEL GRUPO B (incrementalidad) — HALLAZGO CRÍTICO

- EXP_B1..B5: **0 JSON en disco**. Reconciliación: BLOCKED por ausencia de artefactos.
- Dos despachos previos fallaron por infraestructura (HTTP 429 rate-limit;
  luego max_iterations del loop del agente). Ninguno escribió resultados.
- **Hallazgo de esta revisión (19:46 UTC): el diseño congelado de B1–B5 NUNCA
  fue persistido a disco.** No existe en `docs/experimentos/`, ni en
  `.hermes-index.md`, ni en worklogs, ni en la reconciliación (que solo lista
  estados, no hipótesis). El diseño vivía únicamente en el contexto conversacional
  de una sesión anterior.
- **Consecuencia metodológica:** re-despachar un agente para "ejecutar B" sin
  spec persistida obligaría a INVENTAR las hipótesis después de ver resultados
  de A/C — violación directa de la regla de oro del repo ("un gate rojo no se
  convierte en verde cambiando el criterio después de ver el resultado").
  B requiere PRE-REGISTRO en disco antes de cualquier ejecución.

---

## [FASE 4] — LECTURA CIENTÍFICA DEL LOTE (10 experimentos)

1. **El edge existe y es selectivo:** anclaje secuencial depth≥4 en STRUCTURE,
   EURUSD H1 (A1: +10.6pp WR sobre FVG random, IC bootstrap fuera de cero).
   La profundidad es UMBRAL, no continuo: d3 no aporta nada (meanR ≈ 0),
   d4 sí, d5 indeterminado por n.
2. **El edge es de probabilidad de acierto, no de magnitud:** ΔmeanR +0.016
   marginal; lo que separa tratamiento de baseline es WR (55% vs 44%) y la
   mediana de R (+1.0 vs −1.0).
3. **Dónde sobrevive:** costes reales (C4), GBPUSD (C1, provisional por origen),
   M15 (A4, provisional por origen+rango corto).
4. **Dónde se rompe:** H4 (A3), XAUUSD (C2), y el tiempo (C5: 2/4 ventanas,
   pendiente de decay +0.128). El fenómeno es LTF-específico y posiblemente
   régimen-dependiente.
5. **Preguntas abiertas:** P2 (aporte incremental HTF) BLOQUEADA sin diseño;
   P3 (robustez OOS) INCOMPLETA (C3 sin n, C5 inestable); P4 (scope live M15/M5)
   NO_TESTED.

## Proposiciones (según reconciliación)

| Proposición | Estado |
|---|---|
| P1 baseline edge | CONDITIONAL_PASS |
| P2 HTF incremental value | BLOCKED |
| P3 OOS robustness | INCOMPLETE |
| P4 M15/M5 live scope | NOT_TESTED |

**Promoción: BLOCKED.** GEN-000 permanece como motor activo. No se promovieron
señales, parámetros ni candidatos. `policy = STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL`.

---

## [FASE 5] — DEUDAS Y BLOQUEADORES REGISTRADOS

1. **EXP-B-DESIGN-01 (ALTA):** el diseño original B1–B5 no fue persistido a
   tiempo. Se creó `docs/experimentos/EXP_B_DESIGN.md` como reconstrucción
   explícita post hoc. Debe revisarse y congelarse formalmente antes de ejecutar
   B; no puede presentarse como preregistro original. Continúa siendo bloqueante
   del gate de fase.
2. **PIT FULL-vs-PREFIX (ALTA, preexistente):** bloquea A2 y cualquier uso del
   navigator HTF→LTF. Excepción Y vigente: rama `engine-seq-v2-causal` PIT-stable
   solo para diagnóstico, no para declarar edge.
3. **Procedencia de datos (MEDIA):** A4/C1/C2 provisionales por origen parquet
   MT5; A4 además rango 2022–2024. Requiere unificación canónica Dukascopy.
4. **Trazabilidad de rutas (RESUELTA):** el reconciliador y la documentación
   ahora apuntan a `reports/audits/experiments/current_batch/`; no quedan
   referencias operativas a la antigua raíz.
5. **Suite de tests:** 90 passed, 1 failed
   (`test_sequential_outcome.py::test_sweep_nodes_carry_wick_extremes_backward_compatible`).
   Deuda separada del motor secuencial; no afecta este lote.
6. **Doc+JSON regenerados por otro proceso** (`docs/experimentos/EXP_SEQUENTIAL_EXPECTANCY_DEPTH4_LITE_H1.md`,
   `sequential_expectancy_depth4_lite_H1.json`): números distintos al commit
   (WR 54.5% vs 54.98%). Pendiente de decisión de inclusión en commit.

---

## Verificación

```text
10 pares audit/raw leídos de reports/audits/experiments/current_batch/
code_commit idéntico daef67cf… en los 10 audits
dataset hashes registrados por experimento (2dbb5757…, 46a950e0…, 336d6f1d…)
```

## Decisión

Cierre parcial del lote con A+C (10/15). B queda NO-EJECUTADO con causa raíz
documentada (diseño original no persistido, no fallo de hipótesis). Próximo paso
obligatorio: revisar y congelar formalmente `docs/experimentos/EXP_B_DESIGN.md`,
manteniendo su caveat post hoc, antes de ejecutar B.

---

## [ACTUALIZACIÓN] — RESULTADOS POSTERIORES VERIFICADOS EN HISTORIAL

**Fecha de corte:** 2026-08-21 21:42 UTC
**Fuente:** commits `7befab4`, `30120b2` y `793d8ad` sobre la rama `g0-pit-evidence`
**Alcance:** esta actualización documenta evidencia posterior visible en el repositorio; no implica que esos artefactos estén integrados en `feature/a5-audit-datos`.

### D2 — Réplica OOS completa

- **Estado:** `PASS` mecánico.
- **Pregunta:** ¿el resultado de A1 se replica en una era temporal no usada?
- **Dataset:** EURUSD H1 Dukascopy canónico, 2006-01-01 → 2018-12-31, 81.217 barras; hash igual al snapshot A1.
- **Resultado:** 385 operaciones cerradas, WR 50,65%, mean R +0,1306, IC95 bootstrap [+0,0222; +0,2436]; `leakage_check=OK`, sin cambio de parámetros.
- **Lectura:** evidencia directa de replicación temporal positiva bajo el protocolo congelado; sigue siendo objeto de estudio y no autoriza promoción.
- **Artefacto:** `reports/audits/experiments/current_batch/EXP_D2_audit.json` en `7befab4`.

### B — Diagnósticos de incrementalidad HTF

Los diagnósticos fueron ejecutados sobre EURUSD H1 Dukascopy canónico 2019–2024 (36.934 barras), con 2.000 remuestreos. Todos quedaron explícitamente como `promotion=BLOCKED`; la rama `g0-pit-evidence` no prueba aún el navigator FULL-vs-PREFIX completo.

| Experimento | Comparación | n | Delta WR | IC95 | Veredicto |
|---|---|---:|---:|---|---|
| B1 | HTF ALIGNED − HTF AGAINST | 86 / 95 | +7,72 pp | [−6,845; +22,289] pp | **FAIL**: IC cruza 0 |
| B2 | HTF ALIGNED − ALL | 86 / 211 | +4,33 pp | [−8,035; +16,302] pp | **FAIL**: IC cruza 0 |
| B4 | LOCATION FAVORABLE − OTHER | 75 / 136 | +1,59 pp | [−12,157; +15,746] pp | **FAIL**: IC cruza 0 |
| B5 | HTF ALIGNED − LTF ALIGNED | 86 / 17 | +12,24 pp | [−13,613; +36,936] pp | **BLOCKED**: LTF n<30 |

**Lectura:** hay puntos estimados favorables a HTF en B1/B2/B5, pero no hay evidencia confirmatoria con los gates definidos. B5 está además subpotenciado. Los artefactos son diagnósticos no promocionables, no sustituyen una corrida válida en `engine-seq-v2-causal`.

### Preflight y estado de integración

- El preflight de `7befab4` dejó B1/B2/B4/B5 bloqueados por requerir `engine-seq-v2-causal` y B3 bloqueado por ausencia del snapshot EURUSD M15 Dukascopy canónico.
- El commit posterior `793d8ad` publicó diagnósticos B no promocionables en `g0-pit-evidence`; no cambia el estado de producción ni reemplaza GEN-000.
- La rama actual de esta bitácora continúa siendo `feature/a5-audit-datos`; su reconciliación local permanece en 10/15 artefactos observados, promoción `BLOCKED`.

### Decisión actualizada

1. Conservar D2 como evidencia OOS PASS reproducible.
2. No declarar incrementalidad HTF: B1/B2/B4 fallan sus intervalos y B5 está bloqueado por muestra.
3. Mantener el gate PIT FULL-vs-PREFIX como prerrequisito antes de promover o interpretar B operativamente.
4. Resolver primero la integración/validación en `engine-seq-v2-causal` y la disponibilidad de M15 canónico antes de cerrar B3.
