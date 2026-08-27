# FASE 4.1 — Corrección de fidelidad al grafo (M3 Setup State)

- **Fecha:** 2026-08-27
- **Agente:** Hermes
- **Disparador:** Dictamen CEO tras revisar push `5344ed5→afc44dd` con grafo como mapa
- **Base:** `codex/visual-replay-wyckoff-v1-1-20260826` @ worktree `5623a7b`

---

## 1. HALLAZGO DEL CEO (verificado por código, no por fe)

El CEO revisó el grafo y siguió las dependencias hasta `engine/ahf.py`. Encontró
que mi G-PRE3 ("No segunda FSM de setup = PASS") estaba mal sustentado:

- `backtest/setup_builder.py` decía "NOT a second setup FSM" pero `_derive_setup()`
  re-derivaba estados (`H1_PASS ≈ bias H1 != UNKNOWN`; `LTF_CONFIRMATION ≈ existen
  zones`; `invalidacion: []` siempre) — duplicación parcial de la lógica AHF.
- `test_setup_state_does_not_recompute_ahf` solo validaba campos del dict, no que
  `estado == AHFSnapshot.state`.
- `market_state.py` lifecycle solo ACTIVE→PARTIALLY_MITIGATED (terminales delegados).
- Ambigüedad contractual: touch por `main_tf` sobre zonas de cualquier `origin_tf`.
- Reproducibilidad: run `17cd0145` + `verify_6tf_acceptance.py` NO estaban en el push.

**La regla de oro se aplicó:** la evidencia de código vence mi afirmación previa.
El CEO tenía razón en lo sustantivo. FASE 4 NO estaba 100% cerrada.

---

## 2. CORRECCIÓN (FASE 4.1, acotada)

### M3 — Setup State proyecta AHFSnapshot canónico (commit `5623a7b`)
- `setup_builder.build_setup_state` elimina `_derive_setup`; ahora recibe
  `ahf_snapshots` (lista de `AHFSnapshot` del funnel) y los TRADUCE:
  `state / active_tf / confirmed_context / history[-1].invalidation_reason`.
- `backtest/replay.py` instancia `AdaptiveHierarchicalFunnel(frames, AHFConfig())`
  UNA vez por run, corre `run_timeline(decision_times)`, y serializa un dict
  PLANO (`ahf_snapshot`) en `timeline[i]["ict"]["context"]` (sin `history` O(n²)
  para no inflar memoria — regresión corregida tras detectar 2.3GB en run M15).
- `test_setup_state_does_not_recompute_ahf` ahora compara `SetupState(T)` vs
  `AHFSnapshot(T)` punto a punto y FALLA si difieren.

### SDD v1.2 — decisiones contractuales (commit `5623a7b`)
- §6.1 Semántica lifecycle HTF/LTF: el `main_tf` es lente de observación; el
  `origin_tf` es sello de capa. Touch por `main_tf` es válido. Transiciones
  terminales las emite el motor canónico; `market_state` las respeta (proyección).
- §6.2 Setup State = traducción pura de AHFSnapshot; `_derive_setup` removido.

### Puntos del CEO NO abordados en este commit (documentados como faltantes):
- (c) Terminal transitions "reales" en `market_state`: el motor canónico ya las
  emite en `ObjectState`; `market_state` las respeta. El lifecycle COMPLETO se
  observa cuando los datos canónicos lo producen (la prueba de 2 estados es
  correcta para muestras donde el motor solo alcanza PARTIALLY_MITIGATED). No se
  inventan transiciones.
- (d) Filtro visual de relevancia MTF en el visor: mejor de UX, marcado 🟡 por el
  CEO. Queda como mejora posterior; no bloquea la fidelidad AHF.

---

## 3. VERIFICACIÓN

- `pytest tests/test_setup_builder.py tests/test_market_state.py tests/test_schema_v12.py` → **20 passed**.
- Run `16b23e50` (H1+D1+H4, 536 velas): **536 setups, 0 discrepancias vs AHFSnapshot**.
  Estados reales: `SETUP_READY`, `WAIT_H1`, `WAIT_H4`, `WAIT_LTF` (no aproximación).
- Run `17cd0145` (6 TF completo, 192 velas): gate 8/8 PASS (verify_6tf_acceptance.py).
- Reproducibilidad: `scripts/verify_6tf_acceptance.py` + ambos run JSON copiados a
  `reports/audits/experiments/fase4_6capas/` en esta rama de auditoría.

---

## 4. RECLASIFICACIÓN FASE 4 (post-4.1)

```
M1 — MarketObject → replay        ✅ PASS
M2 — Persistent Market State      🟢 AVANZADO (lifecycle completo depende de motor canonico)
M3 — Setup State / AHF            ✅ CORREGIDO (proyecta AHFSnapshot, 0 discrepancias)
M4 — Schema 1.2                   ✅ PASS
M5 — Visor persistente            🟡 PASS funcional (falta filtro relevancia MTF)
Causalidad / FULL-PREFIX           ✅ evidencia fuerte
6TF                                ✅ evidencia reportada + reproducible
Lifecycle completo                🟡 parcial (motor canonico lo gobierna)
Reproducibilidad prueba 6TF        ✅ artefactos publicados en esta rama
```

**FASE 4 = CERRADA de verdad** salvo el filtro visual MTF (mejora de UX, no bloqueo
de fidelidad). El hallazgo principal del CEO se corrigió: ya no hay duplicación
parcial de FSM; el grafo confirma que Setup State es proyección del AHF canónico.

## 5. SIGUIENTE ACCIÓN

Esperar autorización de publicación (push de `5623a7b` a origin en la rama Codex;
esta rama de auditoría ya commitea evidencia reproducible). Filtro visual MTF = tarea
posterior opcional.
