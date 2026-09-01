# EXP-WYCKOFF-ICT-01 — WYCKOFF × ICT CONFLICT (pre-registro prospectivo)

**Fecha de pre-registro:** 2026-08-25 (congela ANTES de cualquier ejecución)
**ID:** `EXP-WYCKOFF-ICT-01`
**Estado:** PRE-REGISTRADO / NO EJECUTADO
**Autoría:** Ruben (pregunta) → Hermes (pre-registro) bajo `AGENTS.md` / `autonomy_policy.md`
**Policy:** distribución observacional; `can_train=false`, `can_trade=false`; no backtest, no promoción.

> ⚠️ **Nota de taxonomía (no colisión):** este experimento **NO** reutiliza el
> `B2` del grupo B de `EXP_B_DESIGN.md` (donde `B2 = "Valor incremental del
> filtro HTF"`). El plan maestro del laboratorio tampoco numera "Sequence ×
> Context State" como `B9`; ese experimento es el ya cerrado `EXP-SEQ-CTX-01`.
> Este id es nuevo y específico para la pregunta Wyckoff × ICT.

---

## 1. Pregunta científica (congelada)

> ¿El contexto **Wyckoff** (fase de acumulación / distribución / transición /
> neutral, y específicamente el **conflicto** PRO_TREND vs COUNTERTREND) aporta
> **INFORMACIÓN INCREMENTAL** sobre la distribución de outcomes de las
> secuencias ICT, por encima de lo que ya explica el Context State ICT
> (`ALIGNED` / `NEUTRAL` / `AGAINST`)?
>
> O, por el contrario, el contexto Wyckoff **solo repite** la misma información
> que el Context State ICT (redundancia, no incrementalidad).

No se busca edge operativo. Se busca responder si Wyckoff merece entrar en el
stack de features del laboratorio o si es redundante respecto a ICT.

---

## 2. Universo y snapshot (prospectivo)

- **Símbolo:** EURUSD (Dukascopy 20Y canónico). Sin otros símbolos salvo que se
  pre-registre ampliación OOS en un addendum separado.
- **Dataset:** `datasets/eurusd_dukascopy_20y/` (H1/H4/D1). **NO** `data/raw/*.parquet`
  (D1/H4 truncados a 2020+, deuda D4 documentada).
- **Motor de secuencia:** `engine/sequential_events.run_sequential`
  (`structure_mode=canonical_bos`, PIT-estable v2, commit fijado en ejecución).
- **Context State ICT:** `engine.mtf_navigation.MTFNavigator.navigate(t, exec_tf="H1")`
  → `ALIGNED / NEUTRAL / AGAINST` (PIT, gate causal FULL-vs-PREFIX `PASS`).
- **Contexto Wyckoff:** `engine/Wyckoff/` — `WyckoffSnapshot` con clasificación
  `PRO_TREND / COUNTERTREND / TRANSITION / NEUTRAL` (ver
  `docs/tesis/PLAN_LTF_ENTRY_LAYER.md` WYCKOFF-3). El **conflicto** es la
  señal `PRO_TREND` vs `COUNTERTREND` dentro del mismo TF de ejecución.
- **Ancla:** barra `STRUCTURE` de cada cadena, deduplicada por `structure_bar`.
- **Unidad de observación:** nodo k de `SequentialChain` (evento/transición), no
  barra genérica.
- **Outcome:** movimiento firmado del close en `+6 / +12 / +24 / +48` barras H1
  y/o tasa de `continuation / reversal / failure` (rango de la secuencia).
- **Snapshot fijado:** el rango temporal se congela en el pre-registro y NO se
  ajusta tras ver resultados.

---

## 3. Baseline

- **Baseline A (solo ICT):** distribución de outcome estratificada por
  `Context State ICT ∈ {ALIGNED, NEUTRAL, AGAINST}` (igual población de
  secuencias, mismos horizontes, mismo motor).
- **Baseline B (solo Wyckoff):** distribución estratificada por
  `Wyckoff ∈ {ACC, DIST, TRANSITION, NEUTRAL, CONFLICT}`.
- El efecto incremental de Wyckoff se mide **dentro de cada nivel de Context
  State ICT** (modelo anidado), no como una comparación global suelta.

---

## 4. Buckets

- **Eje ICT:** `ALIGNED / NEUTRAL / AGAINST`.
- **Eje Wyckoff:** `ACCUMULATION / DISTRIBUTION / TRANSITION / NEUTRAL /
  CONFLICT(PRO_TREND vs COUNTERTREND)`.
- Celda de interés primaria: `ICT_ALIGNED × WYCKOFF_CONFLICT` vs
  `ICT_ALIGNED × WYCKOFF_NON_CONFLICT`, y análogamente en `AGAINST`.
- Sin EMA, ATR como sesgo, OTE, entry, stop, PnL ni optimización.

---

## 5. Efecto mínimo relevante (MDE) y potencia — **n calculado, no solo n≥30**

`n≥30` es un **piso administrativo**, no garantía de potencia. Cálculo de
tamaño muestral a priori para **dos proporciones** (tasa de reversión),
asignación igualitaria, aproximación normal (varianza no agrupada), potencia
objetivo **0.80**, α **0.05** bilateral, tasa base NEUTRAL ≈ 0.46 (de
`exp_seq_x_context_state.md` v3):

| MDE absoluto (Δ tasa reversión) | n por grupo (crudo) | n total (2 grupos) |
| ---: | ---: | ---: |
| 0.15 (15 pp) | ~170 | ~340 |
| 0.10 (10 pp) | **~389** | **~778** |
| 0.08 (8 pp) | ~610 | ~1.220 |
| 0.05 (5 pp) | ~1.565 | ~3.130 |

Con corrección **Bonferroni** para los ~3 contrastes principales
(α = 0.05/3 ≈ 0.0167) el requerimiento por grupo se mantiene en el mismo orden
(~390–1.600 según MDE).

**Límite de datos (hecho verificado en EXP-SEQ-CTX-01):** incluso agrupando
20Y de EURUSD, `canonical_bos` alcanzó solo `ALIGNED=19` / `AGAINST=110` /
`NEUTRAL=23` y `lite` `24/177/44`. Es decir, **la población observable es ~13–80×
inferior al n necesario para potencia 0.80 incluso con un MDE de 10 pp**, y ~100×
para un MDE de 5 pp.

**Consecuencia pre-registrada:** si el snapshot no alcanza el n calculado por
celda, el experimento cierra como **`INSUFFICIENT_N` / `INCONCLUSIVE`**, NO se
amplía el universo post-hoc para llegar a 30, y no se declara edge. El pre-
registro fija el MDE y el n_required explícitos antes de correr.

---

## 6. Bloques temporales (DESIGN / VALIDATION / HOLDOUT)

Congelados sin ajuste a resultados:

| Bloque | Ventana | Uso |
| --- | --- | --- |
| DESIGN | 2006-01-01 → 2015-12-31 | descripción inicial (no tuning) |
| VALIDATION | 2016-01-01 → 2020-12-31 | estabilidad cronológica |
| HOLDOUT | 2021-01-01 → 2025-12-31 | evaluación final, umbrales congelados |

Cada bloque exige que el horizonte `+48` quede dentro de su límite; se excluyen
eventos cuyo outcome cruce el límite del bloque. No hay entrenamiento de
parámetros: OOS = evaluación cronológica de una especificación congelada.

---

## 7. Corrección por múltiples comparaciones

- Contraste primario: incrementalidad de Wyckoff **dentro** de ICT ALIGNED y
  dentro de ICT AGAINST (2 celdas de interés) + Baseline B global = hasta 3
  contrastes.
- Corrección **Bonferroni** (α_familiar = 0.05 → α_contraste ≈ 0.0167) o, en
  su defecto, reporte de **FDR (Benjamini-Hochberg)** con declaración previa.
- Los contrastos exploratorios adicionales (otros ejes Wyckoff) se etiquetan
  como `EXPLORATORY` y no alimentan el veredicto primario.

---

## 8. Reglas PIT (point-in-time)

- `MTFNavigator.navigate(full, t) == navigate(prefix_through_t, t)` debe ser
  `PASS (0 violaciones)` sobre la muestra del experimento (reusa
  `gate_causal.json` vigente, ya `PASS 0/120`).
- Contexto Wyckoff debe derivarse **solo** de barras con `close_time <= t`
  (ventana solo-pasado); si `engine/Wyckoff/` usa ventana centrada, se corrige
  a solo-pasado antes de ejecutar (misma lección de `_causal_swings`).
- Outcome = futuro puro (`bar_k+1 .. bar_k+h`); prohibido elegir el horizonte
  ganador tras ver resultados.

---

## 9. Criterio de veredicto (mecánico, calculado por código)

El veredicto lo calcula el script de auditoría, no la opinión:

- **SUPPORTED** (Wyckoff aporta incremental): en ≥1 celda de interés primaria,
  Δ(outcome | Wyckoff dentro de ICT-fijo) con IC95 bootstrap (cluster por
  `chain_id`) que **excluye 0**, tras corrección por comparaciones múltiples,
  Y n por celda ≥ n_required calculado en §5.
- **FALSIFIED** (Wyckoff es redundante): el modelo anidado no mejora sobre el
  baseline solo-ICT (Δ no significativo en ninguna celda primaria tras
  corrección), con n suficiente.
- **INCONCLUSIVE / INSUFFICIENT_N**: n por celda < n_required, o inestabilidad
  de signo entre bloques, o holdout subpotenciado. **Cierre negativo honesto;
  no se fuerza PASS.**
- **INVALID**: cualquier leakage PIT, cambio de protocolo post-result, o
  violación de `can_train=false`.

---

## 10. Restricciones duras

- `can_train = false` — no prepara datos para IA.
- `can_trade = false` — no entra en el motor productivo ni en señales.
- No modifica `engine/`, `agents/`, `analysis/`, `orchestration/` fuera de lo
  estrictamente necesario para leer contexto Wyckoff de forma solo-lectura.
- No se ejecuta vía loop de agente LLM (fallos documentados: HTTP 429 /
  max_iterations). Runner determinista local.

---

## 11. Artefactos previstos

- `scripts/lab/experiments/exp_wyckoff_ict_01.py` (matriz + gate PIT).
- `reports/audits/experiments/wyckoff_ict_01/{matrix,audit,report}.{json,md}`.
- Manifest con `total_rows`, hashes de `engine/mtf_navigation.py`,
  `engine/sequential_events.py`, `engine/Wyckoff/*`, `generator_commit`,
  `generator_worktree`.

La ejecución es local y no modifica datasets. Veredicto permitido:
`SUPPORTED / FALSIFIED / INCONCLUSIVE`. Nada de IA, snapshot ni backtest hasta
una decisión explícita de Ruben con evidencia reproducible.
