# Bitácora 2026-08-20 — Funnel 20Y cerrado por Grok (gate de CI) + análisis

**Fecha:** 2026-08-20 08:38 UTC-5
**Responsable:** Hermes (análisis) + Grok (ejecución pesada en nube)
**Rama:** main (local detrás 1 commit de origin/main `887aa2ee` al escribir esto)

---

## [CONTEXTO]

Ruben pidió cerrar el Funnel 20Y con validación de gate (no re-procesar 20Y, su laptop
no da abasto). Grok ya había corrido el funnel el 2026-08-19 (commit `e90d75d` +
`5ccff88` anti-OTE) pero el `status: COMPLETE` era auto-declarado por su runner en
`/tmp`, y ningún CI del repo validaba `mtf_seq_funnel.json`.

Hermes auditió el JSON el 2026-08-19 y encontró:
- Conteos reales (vienen de detectores canónicos: `detect_fvg`, `detect_order_blocks`,
  `relate_fvg_ob STRICT`, `run_sequential`, `MTFNavigator`).
- Discrepancias explicables: `sample_every=100` (forzado por runner) vs `2500` (default
  módulo); `precompute_sequences=False` (batch runner) vs `True` (módulo). No eran
  edición manual, sino parámetros del runner de Grok.
- `status: COMPLETE` / `ok_rate` los escribe el runner, no el módulo del repo.

Hermes pidió a Grok: commitear runners + añadir assert de CI + validar JSON existente
(sin re-correr 20Y).

---

## [ENTREGA DE GROK] — verificada contra código

Commit `887aa2ee` "ci(funnel): gate mtf_seq_funnel.json + commit Grok 20Y runners".

**(a) Scripts en `scripts/` (verificado: existen en origin/main):**
- `scripts/grok_run_funnel_20y_full.py` — orquestador FVG/OB + Sequence + MTF dense,
  checkpoints cada etapa, `sample_every=100` forzado, escribe `status: COMPLETE`.
- `scripts/grok_mtf_batches.py` — MTF por lotes con `RESUME_FROM` (reanudable).

**(b) Workflow `.github/workflows/hermes-fvg-ob-funnel.yml` (verificado: tiene assert):**
Nuevo paso "Validate mtf_seq_funnel report" con assert:
```python
assert data.get('status') == 'COMPLETE'
assert set(data['fvg_ob']) >= {'H1','H4','D1'}
for tf in ('H1','H4','D1'):
    assert item['audit_status'] == 'GateStatus.PASS'
    assert item['causal_links'] == item['relation_count']
assert data['sequence']['H1']['audit_status'] == 'PASS'
assert mtf['audit_status'] == 'PASS'
assert mtf['n_samples'] > 1000
assert mtf['ok_rate'] >= 1.0
```

**(c) Assert sobre JSON actual → PASS (declarado por Grok):**
```
MTF_SEQ_FUNNEL_REPORT: PASS
  status=COMPLETE  H1=PASS rel=702 causal=702  H4=PASS rel=206  D1=PASS rel=58
  sequence=PASS chains=1460 complete=3  mtf=PASS n_samples=1239 ok_rate=1.0
```

---

## [ANÁLISIS DE HERMES] — honesto, con evidencia

### Lo que SÍ es real y válido
1. **El funnel 20Y corrió de verdad** en la nube de Grok sobre datos reales
   (124.377 barras H1 / 32.133 H4 / 6.258 D1, dukascopy 20Y).
2. **Los conteos son del detector canónico del repo** (no inventados):
   - FVG/OB H1: 22.477 FVG · 2.799 OB · 702 relaciones STRICT causales.
   - FVG/OB H4: 6.497 · 862 · 206.
   - FVG/OB D1: 1.543 · 214 · 58.
   - Sequence H1: 1.460 cadenas, 3 COMPLETE, 29 depth≥4.
   - MTF dense: 1.239 samples, ok_rate 1.0 (integridad de navegación, no win rate).
3. **El assert de Grok valida el artifact existente** (causal_links == relation_count
   confirma lineage causal estricto; ok_rate 1.0 confirma navegación sin error de
   anti-lookahead). Esto es evidencia fuerte de población.
4. **Anti-indicadores aplicado**: `dealing_range.py` EQ50-only (sin OTE/Fib), commit
   `5ccff88` (verificado en sesión previa).

### Lo que NO es lo que parece (advertencias)
1. **El badge de GitHub del commit `887aa2ee` dice "failure".** Esto NO es del assert
   de mtf_seq_funnel. El workflow corre primero `audits.codigo.fvg_ob_funnel` (funnel
   simple) que requiere datos CSV 20Y que NO están en CI (son LFS/M1/M5 parquet, no
   dukascopy CSV). Ese paso falla → el job se detiene con `set -euxo pipefail` → el
   assert de mtf_seq_funnel (que está al final) **nunca corre en GitHub Actions**.
   => El "PASS" lo declaró Grok corriendo el assert localmente, no un run verde de CI.
2. **`status: COMPLETE` es del runner de Grok, no del módulo del repo.** El módulo
   `audits/codigo/mtf_seq_funnel.py` escribe `audit_status` del FunnelAudit (PASS/FAIL)
   pero NO `status`/`ok_rate`. El runner los añade. Esto es legítimo (es el pipeline
   real de Grok) pero el gate "duro" del repo sigue sin dispararse en CI.
3. **ok_rate 1.0 = integridad de navegación MTF, NO edge/PnL.** No confundir con win rate.
4. **Sequence H1: 3 COMPLETE de 1.460.** Coherente con SEQUENCE×CONTEXT STATE (n bajo en
   depth alto). No es fallo, es el dato real.

### Deuda técnica registrada
- **D1 (CI frágil):** el workflow `hermes-fvg-ob-funnel.yml` mezcla "generar funnel
  simple" (requiere datos) con "validar mtf_seq_funnel" (artifact ya commiteado).
  Si el paso de generación falla por falta de datos, el assert never runs. Fix sugerido:
  separar en dos jobs, o hacer el assert `if: always()` / job independiente que solo
  valide el artifact commiteado (sin regenerar).
- **D2 (runner efímero):** los scripts de Grok usan `CKPT=/tmp/funnel_ckpt.json` y
  `ROOT=/home/workdir/ict2.0` hardcodeado. No portables a tu laptop. Si quieres correr
  TNA/localmente, necesitas adaptarlos o escribir uno nuevo.
- **D3 (motor O(n²) no resuelto):** `mtf_navigation.navigate` sigue O(n²) en el repo
  (1954 ms/bar medido). El funnel de Grok lo sorteó usando `precompute_sequences=False`
  + `sample_every=100` (1.239 samples, no 139k). Pero TNA 20Y full requiere navegar
  todas las barras → se colgará en tu laptop sin el parche O(n) + paralelismo.

---

## [ESTADO]

- Funnel 20Y: CERRADO y validado por assert de Grok (evidencia fuerte de población).
  NO validado por run verde de CI de GitHub (badge failure por datos faltantes).
- Anti-indicadores: DONE (EQ50-only).
- TNA 20Y: PENDIENTE (motor local, requiere parche O(n) + 20 cores).
- SEQUENCE×CONTEXT STATE (re-correr con más n): PENDIENTE (Grok, motor rápido).
- Backtest: BLOQUEADO hasta cerrar A0-A9 + Funnel + TNA.

## [SIGUIENTE ACCIÓN]

Retomar parche de `engine/mtf_navigation.py` a O(n) + paralelizar `navigate` con
multiprocessing (20 cores de la laptop). Validar con regresión bit-exact (baseline de
200 snapshots). Luego TNA 20Y local. SEQUENCE×CONTEXT STATE delegado a Grok con más n.

---

## [HALLAZGOS]

- El funnel de Grok es reproducible (scripts en repo) y validado por assert, pero el
  CI de GitHub no lo valida por falta de datos en el paso previo. Deuda D1.
- `ok_rate 1.0` del funnel ≠ win rate. Es navegación MTF limpia.
- El motor original sigue O(n²): TNA 20Y full no corre en laptop sin optimizar.
