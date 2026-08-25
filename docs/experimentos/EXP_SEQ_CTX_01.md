# EXP-SEQ-CTX-01 — SEQUENCE × CONTEXT STATE (H1 20Y)

**Fecha:** 2026-08-23
**Estado:** EN EJECUCIÓN (gate causal previo a matriz)
**Motor:** `engine-seq-v2-causal` (PIT `_build_eq_pools`) ya mergeado en `feature/a5-audit-datos`
**Autoría:** Ruben (objetivo) → Hermes (ejecución) bajo `AGENTS.md` / `autonomy_policy.md`
**Línea de comando (100% local, Python sistema, sin servicio remoto):**

```bash
C:/Python314/python.exe scripts/lab/experiments/exp_seq_ctx_01_gate.py   # Paso A: barrera causal
C:/Python314/python.exe scripts/lab/experiments/exp_seq_ctx_01.py        # Paso B: matriz (solo si gate PASS)
```

---

## 1. Objetivo (Ruben, palabras del director)

> Identificar y validar qué secuencias ICT cambian significativamente su
> comportamiento según el Context State (ALIGNED/NEUTRAL/AGAINST), con
> evidencia PIT, muestra suficiente y sin PnL ni optimización de trading.

No buscamos "ganar dinero" todavía. Buscamos la relación:

```
Secuencia → Context State → comportamiento futuro
```

Ejemplo esperado: `Sweep → BOS → FVG` + `ALIGNED` → favorable fuerte;
+ `AGAINST` → desfavorable. Resultado ideal: una o varias combinaciones con
`n ≥ 30`, efecto consistente y diferencia clara entre contextos, sin look-ahead.

Conclusión buscada: *"esta secuencia contiene información, pero solo bajo
estas condiciones"* → entonces sí merece walk-forward → validación fuera de
muestra → eventualmente IA/backtest.

---

## 2. Por qué este experimento existía y falló antes

| Corrida | Resultado | Causa |
|---|---|---|
| v1 (2026-08-19, ejecución histórica externa) | `INSUFFICIENT_N` | Solo 24 cadenas a depth≥4 → n=5/11/8 por bucket. Ruido. |
| v2 (2026-08-20) | **INVALIDADO** `CAUSALITY_CHECK_FAIL` | `run_sequential` no era PIT-estable: FULL(853)=0 vs PREFIX(853)=39. Raíz: `_build_eq_pools` retroactivo (agrupaba swings futuros). |

Lección → REGLA DE ORO (2026-08-20): el TNA NO cierra con `asof<=decision`.
El gate definitivo es `navigate(full,t) == navigate(prefix,t)`.

**Hoy:** el fix v2 (`_build_eq_pools` fija `form_bar` en la primera barra con
`min_touches`, solo swings conocidos; `used` set) está mergeado. El motor v2
produce 12100 cadenas / 28 COMPLETE (vs 1460/3 de v1) → resuelve `INSUFFICIENT_N`
de raíz y debe pasar el gate causal.

---

## 3. Diseño (corregido)

| Elemento | Valor |
|---|---|
| Dataset | EURUSD Dukascopy CSV 20Y (`datasets/eurusd_dukascopy_20y/`) — **NO** `data/raw/*.parquet` (D1/H4 truncados a 2020+, deuda D4) |
| Motor de secuencia | `run_sequential` v2 causal, `canonical_bos`, `max_active_chains=10_000_000` (indexado PIT requiere todas las cadenas visibles) |
| Unidad de observación | **nodo k de cada `SequentialChain`** (evento/transición), NO barra genérica. `sequence_depth_at(i)` es máximo no decreciente → contaminaría con barras posteriores |
| S (firma) | `direction + stages_present_hasta_k`; `depth=k` es dimensión extra (no identidad) |
| Context State (PIT) | `MTFNavigator.navigate(t, exec_tf="H1")` → D1 bias × H4 location × H1 alignment → **ALIGNED / NEUTRAL / AGAINST** (mapea a FAVORABLE/NEUTRAL/CONTRA del `CONTRATO_CONTEXT_STATE` v1) |
| Outcome (solo futuro) | continuation / reversal / failure a N=20 H1 barras. **Ruptura del RANGO de la secuencia** (no `high[bar_k]` aislado) → evita artefacto 94% continuation de LIQUIDITY_POOL |
| Estadístico | distribución C/R/F por celda; χ² vs marginal; **Cramér's V (effect size)** > solo p (con miles de obs, p engaña); n_min=30; solo celdas pobladas |
| Control | bootstrap agrupado por `chain_id` (una cadena con 6 nodos ≠ 6 obs independientes) |
| Gate causal | `navigate(full,t)==navigate(prefix,t)` sobre muestra ≥50 barras. 0 violaciones o SUSPENDIDO |
| Pregunta 2 | ¿qué componente de CS (D1/H4/H1) explica más la diferencia? (χ² promedio ponderado por firma) |
| **Prohibido** | PnL, stop fijo, entry, OTE, elegir horizonte por el mejor resultado |

---

## 4. Pipelines

- **Paso A — `exp_seq_ctx_01_gate.py`**: barrera causal. Si `status != PASS`,
  la matriz no debe correr. Salida `reports/audits/experiments/seq_ctx_01/gate_causal.json`.
- **Paso B — `exp_seq_ctx_01.py`**: matriz S×Context. Lee el gate; si no PASS,
  aborta. Salida `reports/audits/experiments/seq_ctx_01/{matrix,report}.json|.md`.

---

## 5. Disciplina de interpretación

- `SEQUENCE × CONTEXT STATE` = objeto de estudio de distribución.
- `SEQUENCE × CONTEXT STATE` ≠ señal de trading aprobada.
- Veredictos honestos: PASS (efecto + n≥30 + Cramér's V relevante) / NO-EDGE /
  INSUFFICIENT_N / INVALIDATED (leakage). El INCONCLUSIVE evitable no es entregable.
- Robustez posterior: repetir con N=10/40 (no elegir el horizonte ganador).

---

## 6. Bitácora de esta corrida

- 2026-08-23: se construye EXP-SEQ-CTX-01 limpio (no duplica `EXP_SEQUENCE_X_CONTEXT_STATE`
  fallida). Scripts en `scripts/lab/experiments/`, diseño aquí, salida en
  `reports/audits/experiments/seq_ctx_01/`. Limpieza de logs huérfanos
  `.hermes-state/logs/exp_seqxcontext.*.log` realizada (acumulación del 2026-08-20).

### 6.1 Veredicto del gate causal — **INVALIDATED**

`exp_seq_ctx_01_gate.py` sobre H1 20Y (120 barras muestra, determinista):
**31/120 violaciones** → motor NO causal-estable en la ruta del navigator.
EXP-SEQ-CTX-01 **SUSPENDIDO** hasta cerrar la raíz. La matriz
(`exp_seq_ctx_01.py`) está programada para ABORTAR si `gate_causal.json`
no dice `PASS` (barrera cumplida).

### 6.2 Raíz del leakage (confirmada con diff reproducible)

- Campos que divergen: `layers.H1.structure_bias` y `layers.H1.regime`
  (y `regime_stack.H1`), todas en la capa H1. También `n_zones` ±1.
- Test aislado (`exp_seq_ctx_01_diag_root.py`): los swings **altos** (`sh`)
  son idénticos FULL vs PREFIX (274=274). Los swings **bajos** (`sl`) difieren
  en longitud: **FULL=262 vs PREFIX=261** — un swing bajo existe en FULL pero
  no en PREFIX.
- Mecanismo: `_causal_swings` (engine/mtf_navigation.py línea ~256) usa una
  **ventana CENTRADA** `j-left .. j+left+1` que mira `left` barras hacia el
  FUTURO. En PREFIX, cuando `i` está cerca del borde del df truncado, esas
  barras futuras no existen → el swing en `j` no se forma → `sl` diverge →
  `structure_bias` (BEARISH vs MIXED) y `regime` divergen.
- **NO es** el bug de `_build_eq_pools` de secuencias que se arregló en v2
  (ese ya pasa su propio gate). Es deuda distinta, en el motor de navegación
  MTF (capa H1).

### 6.3 Consecuencia y próximo paso

- El diseño del experimento es correcto; el **motor subyacente** tiene leakage
  en H1. No se interpretan números de matriz (anti-p-hacking).
- Fix propuesto (requiere decisión de Ruben — toca infraestructura validada
  funnel/TNA): hacer `_causal_swings` causal estricto, ventana solo-pasado
  `j-2*left .. j` (o `j-left .. j`), y re-correr el gate causal. Revalidar
  funnel 20Y y TNA tras el cambio.
- Alternativa de bajo riesgo (aislar EXP sin tocar motor): correr el EXP con
  `navigate` sobre PREFIX reales por barra (como hacía la v2 del 2026-08-20 con
  `SEC_PIT_WITHIN_RANGE`), asumiendo su propia deuda documentada. No recomendada
  mientras el gate del navigator siga fallando.
