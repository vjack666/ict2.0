# Bitácora 2026-08-20 — Funnel 20Y Grok CLOSED + gate CI

**Fecha:** 2026-08-20  
**Responsable:** Grok (nube) bajo directiva de Ruben / auditoría Hermes  
**Rama:** main  
**Plan aprobado:** SÍ — pesados→Grok; cerrar trazabilidad sin re-procesar 20Y  

---

## OBJETIVO

Cerrar el Funnel 20Y (FVG/OB + Sequence + MTF dense) con evidencia reproducible y gate de CI, sin re-correr el dataset completo en PC local.

**Objetivos:**
- [x] Corrida 20Y completa en nube (conteos canónicos)
- [x] Anti-OTE en `dealing_range` (EQ50 only)
- [x] Runners en `scripts/` (no /tmp efímero)
- [x] Assert CI sobre `mtf_seq_funnel.json`
- [x] Preflight assert PASS sobre artifact existente

---

## HALLAZGO DE TRAZABILIDAD (auditoría Hermes)

- `status: COMPLETE` y `ok_rate` los escribe el runner Grok, no solo `audits/codigo/mtf_seq_funnel.py`.
- El workflow `hermes-fvg-ob-funnel.yml` validaba únicamente `fvg_ob_funnel.json`.
- **Brecha:** artifact real sin gate de repo → cerrado añadiendo assert + scripts versionados.
- **No** se re-procesó 20Y; el gate valida el JSON ya publicado.

---

## RESULTADOS EMPÍRICOS (dataset Dukascopy EURUSD 20Y)

### FVG/OB STRICT (detectores canónicos)

| TF | bars | FVG | OB | relaciones | causal_links | audit |
|----|-----:|----:|---:|-----------:|-------------:|-------|
| H1 | 124377 | 22477 | 2799 | 702 | 702 | GateStatus.PASS |
| H4 | 32133 | 6497 | 862 | 206 | 206 | GateStatus.PASS |
| D1 | 6258 | 1543 | 214 | 58 | 58 | GateStatus.PASS |

### Sequence H1 (canonical_bos)

- n_chains: **1460**
- COMPLETE: **3**
- by_depth: `{1:767, 2:575, 3:86, 4:29, 7:3}`
- audit: **PASS**

### MTF navigation dense (`sample_every=100`)

- n_samples: **1239**
- ok_rate: **1.0** (integridad de navegación, **no** win rate)
- audit: **PASS**

### Gate assert (preflight local = CI)

```text
MTF_SEQ_FUNNEL_REPORT: PASS
  status=COMPLETE
  fvg_ob H1/H4/D1 GateStatus.PASS + causal_links==relation_count
  sequence H1 PASS
  mtf n_samples>1000 ok_rate>=1.0
```

---

## ANTI-INDICADORES

| Norma | Acción |
|-------|--------|
| No EMA como bias | Cumplido (structure/BOS) |
| No ATR como bias | Cumplido |
| No OTE / Fib 62–79% | `engine/dealing_range.py` → solo DISCOUNT\|EQ\|PREMIUM |
| Contrato Context State | `docs/CONTRATO_CONTEXT_STATE.md` location = EQ50 |

---

## ARCHIVOS

| Path | Tipo |
|------|------|
| `reports/audits/mtf_seq_funnel.json` | artifact 20Y |
| `reports/audits/mtf_seq_funnel_20Y.md` | resumen |
| `scripts/grok_run_funnel_20y_full.py` | runner full |
| `scripts/grok_mtf_batches.py` | runner MTF batches |
| `docs/SCRIPTS_FUNNEL_20Y.md` | reproducibilidad |
| `.github/workflows/hermes-fvg-ob-funnel.yml` | + Validate mtf_seq_funnel |
| `engine/dealing_range.py` | anti-OTE |
| `docs/CONTRATO_CONTEXT_STATE.md` | normativo |

Commits relevantes: `5ccff888`, `e90d75d`, `8efcb145`, `887aa2ee`, + este.

---

## POLICY (sin cambio)

```text
Funnel  =  auditoría de población / lineage / navegación
Funnel  ≠  edge, PnL, entry
ok_rate 1.0  =  integridad MTF, no win rate
EMA / ATR / OTE  ≠  bias normativo
Backtest  =  BLOQUEADO hasta A0-A9 + Funnel + TNA
```

---

## PRÓXIMO

1. Confirmar workflow verde en GitHub Actions (assert sobre JSON en repo).
2. TNA-BEHAVIORAL / full behavioral gates (pesado → Grok si hace falta).
3. n de sequence depth≥4 sigue bajo (COMPLETE=3) — no declarar edge.
4. EXP SEQUENCE×CONTEXT STATE: hipótesis ABIERTA (n insuficiente).

---

**Estado:** ✅ FUNNEL 20Y CERRADO CON GATE  
**Verificado assert:** PASS  
**Registrado por:** Grok
