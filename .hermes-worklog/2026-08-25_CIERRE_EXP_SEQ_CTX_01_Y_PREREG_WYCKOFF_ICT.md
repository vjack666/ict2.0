# Cierre científico EXP-SEQ-CTX-01 + Pre-registro EXP-WYCKOFF-ICT-01

**Fecha:** 2026-08-25T13:30 UTC-5
**Agente:** Hermes (Dirección de Laboratorio / Soporte CEO)
**Rama de trabajo:** `reconcile/tna-canonical-sci` (worktree desde TNA `c2e9aec`); motor canónico = TNA (NO se trajo motor de `feature/a5-audit-datos`)
**Modo:** LOCAL (sin nube, sin `delegate_task`). Solo Python sistema `C:/Python314/python.exe`.
**Autoridad:** cierre negativo de EXP-SEQ-CTX-01 + pre-registro prospectivo de siguiente experimento. Decisión de fondo (CEO-support) respaldada por Ruben vía dictamen del usuario.

---

## [INICIO]

**Tarea:** (1) Consolidar y publicar el cierre negativo de `EXP-SEQ-CTX-01` como
`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; (2) No abrir `EXP-SEQ-CTX-02`;
(3) Pre-registrar el siguiente experimento del plan maestro — WYCKOFF × ICT
CONFLICT — con tamaño muestral calculado, no solo `n≥30`.

**Git status al inicio:** rama `feature/a5-audit-datos` (ahead of remote); working
tree con ruido: `data/raw/EURUSD/*.parquet` (M1/M5 modificados — worktree DIRTY),
4 PNG de charts, `docs/briefs/brief_2026-08-25.*`, `.codex/`. Ninguno de esto
forma parte del commit científico.

**Objetivos:**
- [x] Verificar estado real en disco (gate causal, artefactos OOS, vintages).
- [x] Corregir `EXP_SEQ_CTX_01.md` §6.1 (stale `INVALIDATED` → gate ahora PASS).
- [x] Pre-registrar `EXP-WYCKOFF-ICT-01` sin colisión de taxonomía.
- [x] Actualizar `.hermes-index.md` (KPI + bloqueador + evidencia).
- [x] Worklog.
- [x] Commit selectivo SOLO de artefactos científicos (no datos/charts/briefs/.codex).

---

## [HALLAZGOS]

### H1 — Discrepancia GitHub vs PC (confirmada, no bloqueante)
- `main` quedó en 20-ago; `codex/tna-full-prefix-proof-20260822` está 12 commits
  adelante y contiene el cierre TNA + OOS. `main` está atrasada y debe reconciliarse
  antes de cualquier publicación (recomendación del CEO-support respetada: NO pusheo
  automático; el push queda bloqueado hasta auditoría independiente + instrucción
  explícita de Ruben).
- El SDD/bitácora de "24-ago" citados por el usuario NO aparecen en rama visible de
  GitHub; existen solo en checkout local. Confirmado: los artefactos OOS (625 filas /
  397 HOLDOUT) están en commits locales `0405079`, `0fe9f52` ya en el historial.

### H2 — El gate causal YA PASA (corrige la narrativa de GitHub)
- `reports/audits/experiments/seq_ctx_01/gate_causal.json` (generado 2026-08-25T13:35,
  `generator_commit=05bdece…`): `n_checked=120`, `n_violations=0`, **`status=PASS`**,
  `usable_for_inference=true`. Hashes de motor **TNA reales** (worktree
  `reconcile/tna-canonical-sci` desde `c2e9aec`):
  `engine/mtf_navigation.py=66a4008e…` (sha256 66a4008ea77282f51484ce8dcebb3384d52ccd7dbd520befd5c368f2dfa6ab9e),
  `engine/sequential_events.py=70e86170…` (sha256 70e86170bead5dba094f20413e814ea48471e3e24b1125805230c738791e7901).
  Regenerado 2026-08-25T19:15Z, `elapsed_s=272.95`, `commit=c2e9aec…`.
- Por tanto `EXP_SEQ_CTX_01.md` §6.1 (que decía `INVALIDATED 31/120`) es **STALE**:
  la raíz de leakage de la capa H1 (ventana centrada de `_causal_swings`) fue resuelta
  por partición por timestamp (`time <= t`, `precompute_sequences=True/False`); lo
  confirma `seq_ctx_01c_lite_audit.md` §1. Se agregó §7 de reconciliación.

### H3 — Veredicto canónico se mantiene (no edición de historia)
- `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`: canonical `19/110/23`, lite
  `24/177/44`, 3/6 celdas `< n≥30`, sin snapshot, sin IA, `can_trade=false`.
- No confundir con `exp_seq_x_context_state.md` (v3, depth≥2): mostró modulación REAL
  de Context State en tasa de reversión (`FAVORABLE > NEUTRAL ≈ CONTRA`, IC excluye 0
  frente a CONTRA), pero es `AUDIT_ONLY`, requiere réplica, y NO altera el cierre
  negativo canónico.

### H4 — Colisión de taxonomía (flag honesto)
- El usuario/CEO-support llama al siguiente experimento "**B2 — WYCKOFF × ICT
  CONFLICT**". Pero en disco `docs/experimentos/EXP_B_DESIGN.md` ya define
  **B2 = "Valor incremental del filtro HTF"**, y "Sequence × Context State" NO es B9
  (es el ya cerrado `EXP-SEQ-CTX-01`). No existe pre-registro WYCKOFF×ICT previo.
- Decisión: NO reutilizar B2. Se crea id nuevo `EXP-WYCKOFF-ICT-01`, documentado
  explícitamente como no-colisión.

### H5 — n calculado ≫ n≥30 (decisivo para no perseguir 30)
Cálculo a priori de dos proporciones (tasa reversión, base NEUTRAL≈0.46, potencia
0.80, α 0.05 bilateral, varianza no agrupada):
| MDE | n/grupo | n total |
|---|---|---|
| 15 pp | ~170 | ~340 |
| 10 pp | **~389** | **~778** |
| 8 pp | ~610 | ~1.220 |
| 5 pp | ~1.565 | ~3.130 |
Bonferroni (3 contrastes, α≈0.0167) mantiene el orden. La población observable
(canonical ALIGNED=19 incluso pooled) es ~13–80× inferior al n requerido ⇒ cualquier
ampliación post-hoc para "llegar a 30" sería adaptación de universo al resultado
(p-hacking). Se pre-registra cierre `INCONCLUSIVE` si no alcanza n calculado.

---

## [CAMBIOS]

| Archivo | Acción | Commit |
|---|---|---|
| `docs/experimentos/EXP_SEQ_CTX_01.md` | mod (§7 reconciliación + enmienda §6.1 stale) | `pending` |
| `docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md` | new (pre-registro prospectivo) | `pending` |
| `.hermes-index.md` | mod (KPI, bloqueador, evidencia, §Siguiente exp) | `pending` |

**NO incluidos en el commit (ruido clasificado, queda fuera a propósito):**
- `data/raw/EURUSD/EURUSD_M1.parquet`, `EURUSD_M5.parquet` (worktree DIRTY — deuda de
  reproducibilidad; requiere commit autorizado de Ruben, NO lo oculto ni lo incluyo).
- `reports/charts/EURUSD_{D1,H1,H4,M15}_tradingview.png` (gráficos operativos).
- `docs/briefs/brief_2026-08-25.{md,txt}` (briefs diarios).
- `.codex/` (operativos del agente Codex).

---

## [VERIFICACIÓN FINAL]

- [x] `git status --short` inspeccionado: separamos ruido de científico.
- [x] `gate_causal.json` leído en disco: PASS 0/120, `usable_for_inference=true`.
- [x] Veredicto canónico verificado contra `.hermes-index.md` y `seq_ctx_01c_lite_audit.md`.
- [x] `EXP_WYCKOFF_ICT_01_PREREGISTRATION.md` cubre: universo/snapshot, baseline, buckets,
  MDE, potencia, n calculado, DESIGN/VALIDATION/HOLDOUT, corrección múltiples comparaciones,
  reglas PIT, criterio SUPPORTED/FALSIFIED/INCONCLUSIVE, `can_train=false`, `can_trade=false`.
- [x] Sin `delegate_task`/nube; ejecución 100% local.
- [x] Commit selectivo SOLO de los 3 archivos científicos (sin `--no-verify`).

---

## [CONCLUSIÓN]

**Resultado:** EXP-SEQ-CTX-01 cerrado como `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`
(negativo honesto; gate causal ahora PASS pero muestra insuficiente). Siguiente
experimento pre-registrado: `EXP-WYCKOFF-ICT-01` (Wyckoff × ICT conflict), con n
calculado a priori (≈389/grupo p/ MDE 10pp) y cierre `INCONCLUSIVE` si la población
observable no alcanza potencia. Nada de IA, snapshot ni backtest todavía.

**Taxonomía:** se evitó reutilizar `B2` (grupo B = filtro HTF); id nuevo documentado.

**Riesgos / deuda:**
- `main` atrasada 12 commits respecto a TNA; reconciliar antes de publicar (sin push
  automático por política).
- `generator_worktree=DIRTY` (datasets M1/M5 modificados sin commit) ⇒ reproducibilidad
  limpia bloqueada hasta commit autorizado de Ruben.
- H5 obliga a ser realista: con datos actuales, EXP-WYCKOFF-ICT-01 probablemente cierre
  `INSUFFICIENT_N` / `INCONCLUSIVE` salvo que se amplíe universo (EURUSD→multi-símbolo)
  en un addendum pre-registrado separado, sin ajuste post-hoc.

**Siguiente acción:** esperar `go` de Ruben para (a) reconciliar/merge de la rama TNA a
`reconcile/tna-canonical-sci` (merge selectivo, sin motor A5), y (b) autorizar la ejecución de `EXP-WYCKOFF-ICT-01`
(runner local determinista, no LLM loop). Hasta entonces: documentación y pre-registro
congelados.
