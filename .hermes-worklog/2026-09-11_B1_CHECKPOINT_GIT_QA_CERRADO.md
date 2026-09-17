# Checkpoint Git/QA — ICT SYSTEM — 2026-09-11

**Misión:** B1 — Diagnóstico causal del FAIL  
**Estado del checkpoint:** COMPLETADO  
**Fecha checkpoint:** 2026-09-11  
**Responsable:** Subagente independiente (deleg_11f8c0b9)  
**Supervisión:** Hermes coordina; departamentos A y F supervisan  

---

## 1. Estado del repositorio

### Branch
```
codex/audit-hermes-cert-20260826
```

### Commit base
```
bbee896 feat(engine): gate mechanical signal publication
```

### Tree
- Working tree DIRTY.
- 6 archivos tracked modificados, +648 / -23 líneas.
- Varios untracked: worklogs de sesión, planes, estados del bot, artefactos de misión.

### Clasificación de cambios

#### Científicos / documentación / gobernanza (válidos)
- `.hermes-index.md` — incorpora misión científica Fase 2B, estado PLAN.
- `docs/REPORT_AUDITORIA_SDD_DIAGNOSTIC_TRAINING_V2_2026-09-10.md` — nuevo.
- `.hermes/plans/2026-09-11_FASE2B_UNLOCK_SCIENTIFIC_MISSION.md` — nuevo.
- Varios `.hermes-worklog/2026-09-11_*.md` — nuevos.
- SDD, contratos, preregistro, `mechanical_signal_publication.py` — sin cambios.

#### Runtime / logs (válidos, no bloquean)
- `.hermes-state/mechanical_bot_blackbox.jsonl`
- `.hermes-state/mechanical_bot_events.jsonl`
- `.hermes-state/mechanical_bot_state.json`
- `reports/mechanical_bot/dashboard.pid`
- `runtime/mechanical_bot/latest_snapshot.json` — eliminado.

#### Estados del bot (válidos, solo observación)
- Estado: ARMED, `execution_enabled=false`, `DIAGNOSTIC_ONLY_NO_VETO`.

#### Artefactos de esta sesión (válidos)
- Misión: `MC-20260911-153509-dfab2f`
- Plan, worklogs, report SDD V2, preflight, candidato, misiones.

#### Basura / no pertinente
- `snapshot-audit-baseline/` — artefactos demo, pueden limpiarse al cerrar sesión.

### Archivos científicos clave verificados (intactos)

| Archivo | SHA-256 | Estado |
|---|---|---|
| `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md` | `78e514969db33c9ba0cbe764b74b5c436a1eb7f20a34a39a31c920d4ed6287a4` | intacto |
| `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md` | `319a13a555b1911e526db912682f2d6d790b3f772c5eae30ed0cb82663bbc40f` | intacto |
| `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` | `2ef7eef384c67543bf40a805b06e5b9e7b3e65495b5cb549db6c466a567033aa` | intacto |
| `engine/mechanical_signal_publication.py` | `1fb88cf10799db16fb0528c21088b7acec8fa549b59a21a8e02dc81886f2eef0` | intacto |
| `reports/audits/experiments/pass_edge_proxy_pilot_2022_2025_summary.md` | `d464b5f53fe9f58480feadd7f1df699910d8db640b177b11e86c7d3ee972f579` | intacto |
| `.hermes-index.md` | `e374839474115caaa179698714a9094523424b0539f7c01dade0b24acad47c72` | intacto |

---

## 2. Dataset y manifiestos

### Datasets canónicos con manifiesto

- `datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json` — 173 entradas M15, 2006-01 a 2020-12.
- `datasets/eurusd_dukascopy_intraday_2021_2025_manifest.json` — 61 entradas M15, 2021-01 a 2026-01.

### data/raw/EURUSD

- Existe: 7 parquet por TF.
- Sin manifiesto histórico versionado.
- Si el motor necesita obligatoriamente estos parquet, se creará `B1_DATA_MANIFEST_V1`.

### Verificación existencia CSV manifiesto 2006-2020

- 180/180 archivos existen en disco.
- 0 faltantes.

---

## 3. Veredicto de reproducibilidad interna

El experimento PASS_EDGE_01 no es reproducible porque:
- Worktree DIRTY.
- Provenance BLOCKED (sin log de adquisición, sin manifiesto único de data/raw/).
- Experimento no materializado (preregistro DRAFT_BLOCKED, sin artefactos).
- Gates pendientes/FAIL.

Esto es correcto para ese experimento, pero **no es el escollo de B1**.

---

## 4. Decisión

Checkpoint aceptado como suficiente para comenzar B1.

- No se intenta dejar el repo artificialmente CLEAN.
- No se dedica más trabajo a PASS_EDGE_01.
- Se congela fuente B1 primero por manifiestos existentes.
- Se deja partir el Objetivo 1 con departamentos independientes.

---

## 5. Datasets elegidos para B1

```
DESIGN:   datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json
          (2006-01-01 → 2020-12-31)

VALIDATION: datasets/eurusd_dukascopy_intraday_2021_2025_manifest.json
            (2021-01-01 → 2021-12-31)

HOLDOUT: 2021-01-01 → 2026-01-01 (congelado, fuera de descubrimiento)
```

Si el motor necesita obligatoriamente `data/raw/EURUSD/*.parquet`, se crea `B1_DATA_MANIFEST_V1` con los bytes exactos usados.

---

## 6. Bloqueos técnicos genuinos (heredados, no generados por esta sesión)

- Provenance de datos BLOQUEADA (sin log de adquisición, sin manifiesto único de data/raw/).
- Reproducibilidad BLOQUEADA por worktree DIRTY y ausencia de experimento materializado.
- Experimento PASS_EDGE_01 no materializado.
- Gates científicos pendientes/FAIL.
- Auditoría independiente pendiente.

Estos bloqueos ya estaban documentados antes de esta sesión; el checkpoint los confirma, no los genera.

---

## 7. Próximo paso

Dejar partir el Objetivo 1 con departamentos independientes:
- B (Dataset Experimental) — principal.
- A (Auditor Causal) — supervisor.
- F (QA/Reproducibilidad) — supervisor.
- E (Red Team) — adversarial.

Cerrar administrativamente y continuar sin esperar confirmación.
