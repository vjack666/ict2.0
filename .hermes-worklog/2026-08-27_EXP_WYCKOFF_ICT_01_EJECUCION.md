# EXP-WYCKOFF-ICT-01 — Ejecución científica (arranque autorizado)

- **Fecha:** 2026-08-27
- **Agente:** Hermes
- **Autorización:** Ruben ("a y despues b" → (a) push FASE 4.2 + (b) arrancar EXP-WYCKOFF-ICT-01)
- **Pre-registro:** `docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md`
- **Certificación previa:** `COUNTS_REPRODUCED_PROVENANCE_MISMATCH` (H1=515<778, JSON DIRTY)

---

## 1. QUÉ SE HIZO

EXP-WYCKOFF-ICT-01 estaba pre-registrado pero NO ejecutado limpiamente. La
certificación previa bloqueó por procedencia (`generator_worktree=DIRTY`). La
" siguiente acción pendiente" era regenerar el JSON desde un checkout limpio y
repetir R1/R2/R3. Eso es exactamente lo ejecutado:

1. **Script del experimento** (`scripts/lab/experiments/exp_wyckoff_ict_01.py`,
   nuevo, commit `a7ccd75`): aplica el veredicto mecánico §9 del pre-registro
   (SUPPORTED / FALSIFIED / INSUFFICIENT_N / INVALID) sobre `feasibility_counts_v2.json`.
   `can_train=false`, `can_trade=false`, no re-corre motor (reusa JSON).
2. **Worktree limpio** `.hermes-cert/exp-wyckoff-clean` @ `a7ccd75` (0 líneas
   sucias) para regenerar los conteos con procedencia `CLEAN`.
3. **Generador v2** (`wyckoff_feasibility_counts.py`, commit `e9c9be9`, ya
   validado por auditoría externa) ejecutado sobre dataset Dukascopy 20Y
   (H1/H4/D1, NO data/raw). 198s. Resultado: `generator_worktree=CLEAN`,
   `generator_commit=a7ccd75`.
4. **Veredicto mecánico** ejecutado sobre JSON limpio → `INSUFFICIENT_N`.

## 2. RESULTADOS (reproducidos, procedencia CLEAN)

Celdas primarias ICT × (CONFLICT vs NON_CONFLICT), n_required=389/grupo:

```
H1  ALIGNED:  CONFLICT=17  NON=29     (max 29  << 389)
H1  AGAINST:  CONFLICT=23  NON=85     (max 85  << 389)
H4  ALIGNED:  CONFLICT=1   NON=2
H4  AGAINST:  CONFLICT=6   NON=21
D1  ALIGNED:  CONFLICT=0   NON=1
D1  AGAINST:  CONFLICT=1   NON=0
```

- H1 total observado = 515; n requerido total = 778.
- Máx celda primaria = 85 (H1 AGAINST NON) << 389.
- PIT gate (FULL==PREFIX) = PASS (reusa gate_wyckoff_pit.json, 0/120).
- Invarianza a redistribución (R3): con total 515 es imposible llenar dos
  celdas a 389 → fallo estructural, no artefacto de distribución.

## 3. VEREDICTO

**`INSUFFICIENT_N`** — cierre negativo honesto, sin forzar PASS (pre-registro §9).
La población observable de secuencias `canonical_bos` es ~13-80× inferior al n
necesario para potencia 0.80 (MDE 10pp). Wyckoff NO puede evaluarse como
feature incremental sobre este universo con estos gates mecánicos.

## 4. SALVAGUARDAS RESPETADAS

- `can_train=false`, `can_trade=false`.
- Sin backtest, sin IA, sin descarga/modificación de datasets.
- Sin ampliar universo post-hoc para llegar a n≥30.
- Sin outcomes (solo conteos de factibilidad + veredicto de procedencia).
- Repo principal NO tocado (solo worktree limpio temporal, ya removido salvo
  lock de permiso).

## 5. ARTEFACTOS

- `reports/audits/experiments/wyckoff_ict_01/feasibility_counts_v2.json` (CLEAN)
- `reports/audits/experiments/wyckoff_ict_01/exp_wyckoff_ict_01_report.json` (INSUFFICIENT_N)
- `scripts/lab/experiments/exp_wyckoff_ict_01.py` (runner veredicto mecánico)

## 6. CONCLUSIÓN Y SIGUIENTE

EXP-WYCKOFF-ICT-01 ejecutado y cerrado honestamente: **INSUFFICIENT_N**.
Wyckoff queda como feature NO demostrada (redundante o insuficiente sobre este
universo). No se promueve a WYCKOFF-7. No hay edge, no hay IA, no hay trading.

Siguiente movimiento (si Ruben lo autoriza): reconsiderar universo (más
símbolos / TF menores) en addendum OOS separado, o cerrar la línea Wyckoff como
"no incremental respecto a ICT" bajo los gates actuales. Eso requiere nueva
autorización y pre-registro de ampliación.
