# Reconciliación main/TNA + auditoría parquet + factibilidad EXP-WYCKOFF-ICT-01

**Fecha:** 2026-08-25T15:10 UTC-5
**Agente:** Hermes (Soporte CEO / Lab Chief)
**Rama:** `feature/a5-audit-datos` (58c8e89); `main` reubicado a TNA (c2e9aec)
**Autoridad:** orden de Ruben — NO commit parquet, NO ejecutar EXP-WYCKOFF-ICT-01.
Solo auditoría de procedencia + reconciliación de historia Git + verificación de
factibilidad por conteos. Ejecución 100% local.

---

## [INICIO]

**Tarea (decisión de Ruben, 2026-08-25):**
1. Auditar parquet M1/M5 SIN modificarlos.
2. Reconciliar `main` + rama TNA + commits `d2efedb`/`58c8e89`.
3. Resolver contradicciones doc y correr tests/gates.
4. Congelar commit, dataset y hashes.
5. Comprobación de factibilidad por CONTEOS (sin outcomes).
6. Ejecutar EXP-WYCKOFF-ICT-01 SOLO si alcanza potencia pre-registrada; si no,
   cerrarlo como inviable sin backtest ni entrenamiento.

**Objetivos de este turno:** (1)✓ (2)parcial✓ (3)pendiente- decisión (4)✗
(5)bloqueado por falta de clasificador (6)✗ por decisión.

---

## [HALLAZGOS]

### H1 — Auditoría parquet M1/M5 (READ-ONLY, no modificados)

El blob commiteado de `data/raw/EURUSD/EURUSD_M1.parquet` y `_M5` es un
**puntero Git LFS** (`.gitattributes` tiene el filtro LFS para esas rutas).
El working tree contiene el **parquet real**. Comparación byte-a-byte contra
el objeto LFS en caché local (NO se hizo `git lfs pull`, se preservó el WT):

| Activo | Committed (LFS) | Working tree | Diff valores | Filas nuevas WT |
|---|---:|---:|---:|---:|
| M1 | 5.780.352 filas (2012-01-11→2026-08-24 20:38) | 5.781.437 (→2026-08-25 14:43) | **0 celdas OHLCV distintas** en 5.780.352 solapadas | 1.085 |
| M5 | 336.540 filas (2022-01-02→2026-08-24 20:35) | 336.757 (→2026-08-25 14:40) | **0 celdas OHLCV distintas** en 336.540 solapadas | 217 |

**Conclusión H1:** los parquet WT son **datos nuevos legítimos** (extensión
forward de ~18h, append de barras recientes). NO son regeneración idéntica ni
modificación accidental de histórico (0 diferencias de valor). Coincide con la
hipótesis de "datos nuevos" de Ruben.

**Estado:** se mantienen SIN commitear (Ruben no autorizó aún). Cuando autorice,
deben ir en commit EXCLUSIVO con: origen, periodo, filas, SHA256 del WT
(`c0581064…` M1 / `7caa76f7…` M5), y el delta (+1085/+217 filas). Nunca mezclados
con código/doc.

### H2 — Reconciliación de historia Git

Topología verificada (`git merge-base` / `merge-tree`):
- `main` (f453bf2) es **ANCESTRO** de `origin/codex/tna-full-prefix-proof-20260822`
  (c2e9aec) → fast-forward limpio de 12 commits.
- `feature/a5-audit-datos` (58c8e89) es línea **independiente**: 31 ahead / 12
  behind de TNA. Mis commits `d2efedb`/`58c8e89` **NO** están en TNA.
- `feature/a5` ↔ TNA tiene **21 conflictos reales** (merge-tree --write-tree).

**Acción ejecutada:** fast-forward LOCAL de `main` → TNA (c2e9aec). `main` ya =
TNA localmente. **NO pusheado** (sin autorización de publicar; `origin/main`
sigue 12 atrás).

### H3 — Conflicto crítico de motor (la advertencia de Ruben, confirmada)

Los 21 conflictos incluyen `engine/mtf_navigation.py` y `engine/sequential_events.py`
(ambos modificados INDEPENDIENTEMENTE en TNA y en a5). Hashes de tip en cada punta:

| Archivo | TNA (c2e9aec) | a5 (58c8e89) |
|---|---|---|
| `engine/mtf_navigation.py` | `16853851…` | `43abb663…` |
| `engine/sequential_events.py` | `d16c04da…` | `d21f20b7…` |

Mi `gate_causal.json` (tip a5) registra `generator_commit=05bdece…` e
hashes `2905f8…`/`dc56cc…` que **NO coinciden con ninguna punta**. Es decir: el
gate se validó contra un estado de motor **transitorio** que no existe en ninguna
rama. Un merge ingenuo congelaría un artefacto apuntando a código inexistente →
**reproducibilidad rota**.

TNA además tiene su propio `gate_causal.json` (status PASS) pero SIN campos
`generator_commit`/hashes (versión más delgada).

**Decisión:** NO auto-merge. El motor canónico causal debe ser UNO (recomendado:
la línea TNA `engine-seq-v2-causal` dedicada, que ya pasó TNA FULL/PREFIX), y el
gate debe **re-ejecutarse contra ese motor exacto** grabando sus hashes reales
antes de cualquier freeze. Requiere tu `go` para ejecutar el merge con estrategia
explícita (tomar motor TNA + re-correr gate) — fuera de alcance de este turno.

### H4 — Factibilidad por conteos de EXP-WYCKOFF-ICT-01: BLOQUEADA

El pre-registro exige contexto Wyckoff por barra (buckets PRO_TREND/COUNTERTREND/
TRANSITION/NEUTRAL/CONFLICT) para unirlo a los anchors de `run_sequential`.

Inspección de `engine/Wyckoff/`:
- `classify_alignment(phase, ict_direction, events)` existe y devuelve
  `WyckoffPhaseState`, pero es **clasificación por snapshot** consumida por
  `daily_motor`/`brief_lunes`. **No hay pipeline que emita una serie por-barra
  Wyckoff sobre 2012–2026 H1** para jointear a los nodos de secuencia.
- `WYCKOFF-3` (PLAN_LTF_ENTRY_LAYER) está `IN PROGRESS`: "PRO_TREND/COUNTERTREND y
  conflicto probados; transición/neutral requieren cobertura ampliada".
- No está cableado en `run_sequential` ni `MTFNavigator`.

**Conclusión H4:** una "comprobación de factibilidad por conteos" NO es posible en
el codebase actual sin construir primero un adaptador de bucketing Wyckoff
por-barra — y ese adaptador depende de resolver H3 (el motor diverge entre a5 y
TNA). Es trabajo nuevo real, no un conteo rápido. Por tanto, la factibilidad
queda **BLOQUEADA** hasta (a) elegir motor canónico y (b) construir el
clasificador por-barra (lite, sin outcomes).

---

## [CAMBIOS]

| Acción | Detalle |
|---|---|
| `main` ← fast-forward a TNA | local `main` = c2e9aec (ff, ancestro). NO push. |
| Audit parquet | read-only; sin modificación de WT ni `git lfs pull`. |
| Temp script | `scripts/_tmp_parquet_audit.py` creado para el audit; se elimina al cerrar. |
| Worklog | este archivo. |

**NO commiteado:** parquet M1/M5, charts, briefs, `.codex/`, ni el worklog.

---

## [VERIFICACIÓN]

- [x] Parquet: comparación byte-a-byte vs caché LFS (0 diffs de valor, +1085/+217 filas nuevas).
- [x] `main` ancestor de TNA → ff ejecutado y verificado localmente.
- [x] `merge-tree --write-tree` lista 21 conflictos; motor en el núcleo.
- [x] Hashes de motor en punta TNA vs a5 divergen; gate apunta a estado transitorio.
- [x] Wyckoff: clasificador por snapshot, sin serie por-barra → factibilidad bloqueada.
- [x] Sin ejecución de EXP-WYCKOFF-ICT-01, sin backtest, sin entrenamiento.

---

## [CONCLUSIÓN]

**Riesgo real identificado (como anticipó Ruben):** ejecutar sobre una historia
Git y un dataset NO reconciliados. Este turno lo convierte en hallazgo verificado:
- Dataset: parquet son forward-append legítimo (no se tocaron).
- Historia: `main` ya = TNA local; pero `feature/a5` y TNA tienen 21 conflictos,
  con el motor causal en el centro y `gate_causal.json` apuntando a código que no
  existe en ninguna punta.
- Factibilidad EXP-WYCKOFF-ICT-01: **BLOQUEADA** por falta de clasificador Wyckoff
  por-barra (y depende a su vez de resolver el motor).

**Siguiente acción (requiere `go` de Ruben):**
1. Decidir motor canónico para el freeze (recomendado: TNA `engine-seq-v2-causal`).
2. Merge deliberado `feature/a5` + TNA con esa regla; resolver los 21 conflictos
   (docs/workflows triviales; engine con estrategia explícita).
3. Re-ejecutar `gate_causal.py` contra el motor fusionado, grabar hashes reales.
4. Construir adaptador Wyckoff por-barra (lite) y correr **solo conteos** de
   `EXP-WYCKOFF-ICT-01`: n por celda `(ICT × Wyckoff)`. Si ninguna celda se
   acerca al n calculado (~389/grupo p/ MDE 10pp), **cerrar como INVIABLE** sin
   backtest ni entrenamiento.
5. Solo si la factibilidad pasa, ejecutar el experimento completo.

**Estado:** `COMPLETED_WITH_DOCUMENTED_DEBT` — auditoría y reconciliación parcial
hechas; motor y factibilidad siguen bloqueados y requieren decisión.
