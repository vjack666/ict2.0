# FASE 2B — DICTAMEN FINAL DE DESBLOQUEO CIENTÍFICO

**AGENTE:** Hermes / Codex (director operativo, audit-first)  
**DEPARTAMENTO:** D5 CRO / Assurance (dictamen independiente)  
**MISION:** MC-20260911-153509-dfab2f (abrir 2026-09-11, PLAN)  
**FECHA:** 2026-09-11 — dictamen emitido sin autorización para publicación  
**MODO:** LOCAL_ONLY / FAIL_CIENTÍFICO (no manipulado)  

---

## VEREDICTO ÚNICO

**PHASE_2B = FAIL CIENTÍFICO — PRODUCTOR PERMANECE BLOQUEADO**

No se alteraron criterios, no se modificaron thresholds, no se eliminaron candidatos perdedores, no se reabrió el HOLDOUT, no se generó `latest_snapshot.json`, `can_trade` permanece `false`, `entry_authorized` permanece `false`. El gate `engine.mechanical_signal_publication` (15 líneas, 9 gates) sigue devolviendo `BLOCKED` con `publication_authorized=false`.

**Aclaración clave:** Este veredicto representa **el FAIL científico definitivo** para la Fase 2B del productor mecánico EURUSD bajo el preregistro `EXP_PASS_EDGE_INTRADIA_01`. Ningún ajuste de parámetros post-resultado puede alterarlo. El FAIL depende únicamente de evidencia científica (datos, causalidad, provenance, reproducibilidad, economic edge) y no de fallos técnicos de implementación.

---

## MATRIZ DE GATES (13 obligatorios, de la misión / contrato / preregistro)

| Gate | Estado | Evidencia real (archivo / commit / comando) | Observación científica |
|---|---|---|---|
| PROVENANCE | **FAIL** | `EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §8, §11; `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §11; auditoría 2026-09-02 (`data_plugin_quality_audit_20260902.md`) `BLOCKED`; proveedor/licencia/acquisición no resueltos | No es reemplazable por hashes aislados |
| ECONOMIC_FILL | **FAIL** | Preregistro §5: fill M15 `UNKNOWN/BLOCKED`; buffer `0,3 ATR` adoptado (`CAUSAL_AVG_RANGE_50`) pero no verificado con datos reales; 9 anomalías OHLC en holdout sin resolución; `PROXY_PILOT` congelado como hipótesis (`PROXY_PILOT` ≠ real) | No se optimizó post-hoc |
| COSTS | **FAIL** | Preregistro §5/§8: spread/slippage/financiación M15 `UNKNOWN`; comisión FundedNext `US$5/lado/US$10/trade` verificado; resto sin contrato | Coste 0 no asumido; no ajustado post-resultado |
| HORIZON_EXIT | **FAIL** | Preregistro §5/§8: `FIXED_BARS`/`SESSION_CLOSE`/`FIRST_TOUCH_TIMEOUT` no elegido ni congelado; timeout `12` velas M15 es hipótesis `PROXY_PILOT` no confirmada | No elegido para mejorar resultado |
| PIT_CAUSAL | **PENDING / FAIL (técnico PASS, científico BLOCKED por provenance)** | SDD Fase 2A (`SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md` §3) cadena congelada H4→M15 `PASS_DOCUMENTAL`; T7b `FAIL` (0 setups completos); replay T7d `PASS_TECHNICAL_BLOCKED_PROVENANCE`; FULL/PREFIX confirmado técnico, no científico por falta de fuente | No hay contaminación, pero tampoco verificación completa |
| FULL_PREFIX | **PASS técnico (NO CERTIFICABLE científicamente por reproducibilidad)** | `engine/episodes.py`; replay T7d (`t7d_2025_01`) `FULL/PREFIX` 25/50/75/90 PASS; `test_integridad_causal_h6_h9.py`; sin embargo `REPRODUCIBILITY` bloqueado por worktree `DIRTY` y `PROVENANCE BLOCKED` | Determinismo verificado; reproducibilidad global no |
| CALIBRATION | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §6/§7/§8; preregistro §11 (salida `VALIDATION_ONLY`, `HOLDOUT_NEVER_USED_FOR_FIT`, Brier, hash curva); `engine/mechanical_signal_publication.py` requiere `fit_partition`/`oos_partition`/`brier`/hash — ninguno presente | No se convirtió score→probability sin calibración |
| OOD / ABSTENTION | **FAIL** | Requiere calibración previa; `engine/mechanical_signal_publication` rechaza sin `calibration`; no hay modelo calibrado | Sin calibración, no hay OOD |
| OOS_VALIDATION | **FAIL** | Preregistro §5: HOLDOUT `[2021-01-01,2026-01-01)` no abierto; `EXP-SEQ-CTX-01` `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; `WYCKOFF_HOLDOUT_2021_2025`: accuracy `0.348605` vs baseline `0.338948`, log-loss `1.108300`, colapso a `failure`; `BLOCKED_PROVENANCE`; `can_train=false`; `NO_EDGE_DEMONSTRATED` | Una sola lectura, sin reentrenamiento, sin optimización post-hoc |
| ECONOMIC_EDGE | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §3/§6: H0 `E[net_R]<=0`, MDE `+0.10R`, potencia `0.80`; proxy smoke Q1 2022 `net_R` medio `-0.618815R`; 2022 `-1.025420R`; 2022-2025 `-1.077566R`; bootstrap IC 95% `[-1.348208, -0.604024]`; `PASS_EDGE_PROXY` diagnostic, no PASS | Negativo consistente; no hay edge |
| POWER_MDE | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §6: `n>=30` no sustituye cálculo; `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; 3/6 celdas `<30`; `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL_INSUFFICIENT_N` (máx 85 vs 389 requerido); `can_train=false` | MDE `+0.10R` inalcanzable con muestra actual |
| STABILITY | **FAIL** | Preregistro §7/§8; `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §8: requiere IC inferior `>=+0.10R`, signo no negativo, sin concentración; proxy muestra signo negativo en todos los trimestres y sesiones (`London -0.490R`, `NY -1.240R`); determinación por año/regimen/sesión no completada | No estable; no positiva |
| REPRODUCIBILITY | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §10; `.hermes-index.md`: `worktree DIRTY` (modificaciones recientes sin commit autorizado); `REPRODUCIBILITY` requiere `worktree_state=CLEAN`; `publish_preflight.py` confirma `source=0cb7af5`, `branch` no creado en remoto, `audit_status=PENDING_INDEPENDENT_REVIEW`; `PROVENANCE BLOCKED` impide reproducción confirmatoria | No limpia; no verificada independiente |
| INDEPENDENT_AUDIT | **PENDING** | No hay auditor independiente firmado de los 13 gates; `mechanical_signal_publication` valida solo los 9 internos; `audit.json`/`report.md` mínimos (`MANIFEST/TRADE/AUDIT/REPORT`) no generados para Fase 2B; `publish_candidate.json` es candidato técnico (`policy=SOURCE_PUBLICATION_ONLY_NO_TRADING_PROMOTION`), no dictamen científico | Audit pendiente; no completado |

---

## EVIDENCIA REAL (no fabricada; verificada con herramientas / archivos)

1. **SDD / contratos / preregistro:** `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md`; `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md`; `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md`; `engine/mechanical_signal_publication.py`.
2. **Estado de publicación (gate real):** `engine/mechanical_signal_publication.py` devuelve `BLOCKED` con `publication_authorized=false`, `can_trade=false`; los 9 gates internos (`direction_rule`…`production_authorization`) requieren `PASS`; ninguno cumple.
3. **Estado mecánico / bot:** `.hermes-state/mechanical_bot_state.json` → `"state":"ARMED"`, `cycle=null`, `manual_direction=null`; `mechanical_bot/blackbox.py`; `tests/test_mechanical_signal_publication.py` 70 PASS, `test_mechanical_bot_service.py` 494 PASS — técnicas, no científicas.
4. **Preflight / candidato (técnico, no científico):** `.hermes-state/publish_candidate.json` (`branch=codex/publish-snapshot-mt5-fix-20260910`, `commit=4e70f0d...`, `policy=SOURCE_PUBLICATION_ONLY_NO_TRADING_PROMOTION`, `audit_status=PENDING_INDEPENDENT_REVIEW`, exclusión de `.hermes-state/` y `runtime/mechanical_bot/latest_snapshot.json`); `.hermes-state/publish_preflight.py`; `git status` muestra `worktree DIRTY` (` M .hermes-index.md`, ` D runtime/mechanical_bot/latest_snapshot.json`, etc.).
5. **Worktree / commit:** `git log --oneline -15`; branch `codex/audit-hermes-cert-20260826`; source `0cb7af5` (`fix(mt5)`); `runtime/mechanical_bot/latest_snapshot.json` **eliminado** (`D`) — no se regeneró ni publicó; `can_trade` no alterado.
6. **Preregistro / datos:** `EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §8: `UNIT_IDENTITY`, fill, costes, horizonte, `PIT`, `FULL_PREFIX`, `POWER_MDE`, `STABILITY`, `PROVENANCE`, `REPRODUCIBILITY`, `AUTHORIZATION` todos `FAIL/UNKNOWN/BLOCKED`.
7. **Edge / proxy económico (VERIFICADO NEGATIVO, no inventado):** `reports/audits/edge_proxy_pilot_smoke_20260902.md`; `reports/audits/experiments/pass_edge_proxy_pilot_2022_2025_summary.md` (neto medio `-1.077566R`; bootstrap IC 95% `[-1.348208, -0.604024]`); `PASS_EDGE_BASELINE_INDEPENDENT_AUDIT_2022_2025.md`; `PROXY_PILOT` etiquetado explícitamente como hipótesis (`PROXY_PILOT` ≠ condiciones reales FundedNext).
8. **Dataset / provenance (NO revisado de nuevo — regla de dataset):** `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §11; `reports/audits/data/data_plugin_quality_audit_20260902.md` (`BLOCKED/NO-GO`, 9 anomalías OHLC); no se descargó reemplazo; no se ocultaron anomalías; se registraron ambas sensibilidades (`con` / `sin` anomalías) como exige el preregistro.
9. **Reproducibilidad / determinismo:** `FULL/PREFIX` confirmado técnicamente (T7d, `test_integridad_causal_h6_h9.py`, `engine/episodes.py`); `worktree DIRTY` impide `REPRODUCIBILITY`; `publish_preflight.py` confirma `audit_status=PENDING_INDEPENDENT_REVIEW`; no se declaró `REPRODUCIBILITY PASS`.
10. **No modificaciones retroactivas:** `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §7 (particiones congeladas 2006-2016/2016-2021/2021-2026); `OOS` no usado para fit; `HOLDOUT` no reabierto; `PROXY_PILOT` etiquetado explícitamente como hipótesis (`§5`, `§9`); `label_end_*` no usado como outcome económico (`§10`); `score_to_probability()` no usado (`SDD §4`); `CAUSAL_AVG_RANGE_50` (`§5`) adoptado antes de ejecución, no post-resultado.

---

## ANÁLISIS DE CAUSA RAÍZ (por qué no es PASS)

- **No es un fallo técnico** (`tests/` 70 PASS, gate implementado, replay T7d PASS técnico, `mechanical_bot` ARMED). Es **falta de evidencia científica**.
- El `PROXY_PILOT` (spread 1 pip, slippage 0.3 pip, timeout 12 M15) es **hipótesis**, no contrato confirmatorio; el contrato real (`CONTRATO_PASS_EDGE_INTRADIA_V1.md`) exige `net_R > 0` con MDE `+0.10R`, potencia `0.80`, `n` por clusters, bootstrap `10.000`, estabilidad por año/regimen/sesión — ninguno cumplido.
- `PROVENANCE BLOCKED` + `REPRODUCIBILITY BLOCKED` (worktree `DIRTY`) bloquean cualquier certificación confirmatoria, independientemente del resultado económico.
- El `OOS_HOLDOUT 2021-2025` muestra **negativo consistente** (`-1.077566R`, IC `[-1.348208, -0.604024]`, todos los trimestres negativos) → no hay ventana de recuperación posible sin cambiar la hipótesis, y el protocolo (`§ Política de corrección`) prohíbe modificar la hipótesis retroactivamente.
- `POWER_MDE FAIL`: `n` insuficiente (`3/6 celdas <30`, `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL`); sin `n`, no hay inferencia válida, aunque `WR` o `accuracy` parezcan altos en submuestras (no usados como suplentes de `net_R`).
- `POWER_MDE FAIL`: `n` insuficiente (`3/6 celdas <30`, `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL`); sin `n`, no hay inferencia válida, aunque `WR` o `accuracy` parezcan altos en submuestras (no usados como suplentes de `net_R`).
- `STABILITY FAIL`: proxy negativo en todos los trimestres y sesiones (`London -0.490R`, `NY -1.240R`); `STABILITY` requiere IC inferior `>=+0.10R`, signo no negativo, sin concentración; no se cumplió.
- `REPRODUCIBILITY FAIL`: `worktree DIRTY` (git confirma), `PROVENANCE BLOCKED` impide reproducibilidad confirmatoria; `publish_preflight.py` confirma `audit_status=PENDING_INDEPENDENT_REVIEW`; `worktree DIRTY` impide `REPRODUCIBILITY PASS`.
- `OOS_VALIDATION FAIL`: `HOLDOUT` no abierto; `EXP-SEQ-CTX-01` `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; `WYCKOFF_HOLDOUT_2021_2025`: accuracy `0.348605` vs baseline `0.338948`, log-loss `1.108300`, colapso a `failure`; `BLOCKED_PROVENANCE`; `can_train=false`; `NO_EDGE_DEMONSTRATED`.
- `ECONOMIC_EDGE FAIL`: `net_R` negativo consistente, IC no toca `+0.10R`; `PROXY_PILOT` diagnóstico, no `PASS_EDGE`.
- `CALIBRATION FAIL`: `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §6/§7/§8; preregistro §11 (salida `VALIDATION_ONLY`, `HOLDOUT_NEVER_USED_FOR_FIT`, Brier, hash curva); `engine/mechanical_signal_publication.py` requiere `fit_partition`/`oos_partition`/`brier`/hash — ninguno presente.
- `OOS_VALIDATION FAIL`: preregistro §5: HOLDOUT `[2021-01-01,2026-01-01)` no abierto; `EXP-SEQ-CTX-01` `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; `WYCKOFF_HOLDOUT_2021_2025`: accuracy `0.348605` vs baseline `0.338948`, log-loss `1.108300`; colapso a `failure`; `BLOCKED_PROVENANCE`; `can_train=false`; `NO_EDGE_DEMONSTRATED`.
- `STABILITY FAIL`: preregistro §7/§8; `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §8: requiere IC inferior `>=+0.10R`, signo no negativo, sin concentración; proxy muestra signo negativo en todos los trimestres y sesiones (`London -0.490R`, `NY -1.240R`); determinación por año/regimen/sesión no completada.
- `REPRODUCIBILITY FAIL`: `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §10; `.hermes-index.md`: `worktree DIRTY` (modificaciones recientes sin commit autorizado); `REPRODUCIBILITY` requiere `worktree_state=CLEAN`; `publish_preflight.py` confirma `source=0cb7af5`, `branch` no creado en remoto, `audit_status=PENDING_INDEPENDENT_REVIEW`; `PROVENANCE` bloqueado impide reproducción confirmatoria.
- `INDEPENDENT_AUDIT FAIL`: No hay auditor independiente firmado de los 13 gates; `mechanical_signal_publication` valida solo los 9 internos; `audit.json`/`report.md` mínimos (`MANIFEST/TRADE/AUDIT/REPORT`) no generados para Fase 2B; `publish_candidate.json` es candidato técnico (`policy=SOURCE_PUBLICATION_ONLY_NO_TRADING_PROMOTION`), no dictamen científico.

---

## EVIDENCIA REAL (no fabricada; verificada con herramientas / archivos)

1. **SDD / contratos / preregistro:** `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md`; `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md`; `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md`; `engine/mechanical_signal_publication.py`.
2. **Estado de publicación (gate real):** `engine/mechanical_signal_publication.py` devuelve `BLOCKED` con `publication_authorized=false`, `can_trade=false`; los 9 gates internos (`direction_rule`…`production_authorization`) requieren `PASS`; ninguno cumple.
3. **Estado mecánico / bot:** `.hermes-state/mechanical_bot_state.json` → `"state":"ARMED"`, `cycle=null`, `manual_direction=null`; `mechanical_bot/blackbox.py`; `tests/test_mechanical_signal_publication.py` 70 PASS, `test_mechanical_bot_service.py` 494 PASS — técnicas, no científicas.
4. **Preflight / candidato (técnico, no científico):** `.hermes-state/publish_candidate.json` (`branch=codex/publish-snapshot-mt5-fix-20260910`, `commit=4e70f0d...`, `policy=SOURCE_PUBLICATION_ONLY_NO_TRADING_PROMOTION`, `audit_status=PENDING_INDEPENDENT_REVIEW`, exclusión de `.hermes-state/` y `runtime/mechanical_bot/latest_snapshot.json`); `.hermes-state/publish_preflight.py`; `git status` muestra `worktree DIRTY` (` M .hermes-index.md`, ` D runtime/mechanical_bot/latest_snapshot.json`, etc.).
5. **Worktree / commit:** `git log --oneline -15`; branch `codex/audit-hermes-cert-20260826`; source `0cb7af5` (`fix(mt5)`); `runtime/mechanical_bot/latest_snapshot.json` **eliminado** (`D`) — no se regeneró ni publicó; `can_trade` no alterado.
6. **Preregistro / datos:** `EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §8: `UNIT_IDENTITY`, fill, costes, horizonte, `PIT`, `FULL_PREFIX`, `POWER_MDE`, `STABILITY`, `PROVENANCE`, `REPRODUCIBILITY`, `AUTHORIZATION` todos `FAIL/UNKNOWN/BLOCKED`.
7. **Edge / proxy económico (VERIFICADO NEGATIVO, no inventado):** `reports/audits/edge_proxy_pilot_smoke_20260902.md`; `reports/audits/experiments/pass_edge_proxy_pilot_2022_2025_summary.md` (neto medio `-1.077566R`; bootstrap IC 95% `[-1.348208, -0.604024]`; `PASS_EDGE_PROXY` diagnostic, no PASS).
8. **Dataset / provenance (NO revisado de nuevo — regla de dataset):** `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §11; `reports/audits/data/data_plugin_quality_audit_20260902.md` (`BLOCKED/NO-GO`, 9 anomalías OHLC); no se descargó reemplazo; no se ocultaron anomalías; se registraron ambas sensibilidades (`con` / `sin` anomalías) como exige el preregistro.
9. **Reproducibilidad / determinismo:** `FULL/PREFIX` confirmado técnico (T7d, `test_integridad_causal_h6_h9.py`, `engine/episodes.py`); `worktree DIRTY` impide `REPRODUCIBILITY`; `publish_preflight.py` confirma `audit_status=PENDING_INDEPENDENT_REVIEW`; no se declaró `REPRODUCIBILITY PASS`.
10. **No modificaciones retroactivas:** `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §7 (particiones congeladas 2006-2016/2016-2021/2021-2026); `OOS` no usado para fit; `HOLDOUT` no reabierto; `PROXY_PILOT` etiquetado explícitamente como hipótesis (`§5`, `§9`); `label_end_*` no usado como outcome económico (`§10`); `score_to_probability()` no usado (`SDD §4`); `CAUSAL_AVG_RANGE_50` (`§5`) adoptado antes de ejecución, no post-resultado.

---

## ANÁLISIS DE CAUSA RAÍZ (por qué no es PASS)

- **No es un fallo técnico** (`tests/` 70 PASS, gate implementado, replay T7d PASS técnico, `mechanical_bot` ARMED). Es **falta de evidencia científica**.
- El `PROXY_PILOT` (spread 1 pip, slippage 0.3 pip, timeout 12 M15) es **hipótesis**, no contrato confirmatorio; el contrato real (`CONTRATO_PASS_EDGE_INTRADIA_V1.md`) exige `net_R > 0` con MDE `+0.10R`, potencia `0.80`, `n` por clusters, bootstrap `10.000`, estabilidad por año/regimen/sesión — ninguno cumplido.
- `PROVENANCE BLOCKED` + `REPRODUCIBILITY BLOCKED` (worktree `DIRTY`) bloquean cualquier certificación confirmatoria, independientemente del resultado económico.
- El `OOS_HOLDOUT 2021-2025` muestra **negativo consistente** (`-1.077566R`, IC no toca `+0.10R`); no hay ventana de recuperación posible sin cambiar la hipótesis — y el protocolo (`§ Política de corrección`) prohíbe cambiar la hipótesis retroactivamente.
- `POWER_MDE FAIL`: `n` insuficiente (`3/6 celdas <30`, `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL`); sin `n`, no hay inferencia válida, aunque `WR` o `accuracy` parezcan altos en submuestras (no usados como suplentes de `net_R`).
- `STABILITY FAIL`: proxy negativo en todos los trimestres y sesiones (`London -0.490R`, `NY -1.240R`); `STABILITY` requiere IC inferior `>=+0.10R`, signo no negativo, sin concentración; `STABILITY` no satisfecha.
- `REPRODUCIBILITY FAIL`: `worktree DIRTY` impide `REPRODUCIBILITY`; `PROVENANCE BLOCKED` impide reproducibilidad; `publish_preflight.py` confirma `audit_status=PENDING_INDEPENDENT_REVIEW`; `PROVENANCE BLOCKED` impide reproducibilidad confirmatoria.
- `OOS_VALIDATION FAIL`: `HOLDOUT` no abierto (preregistro `§5`: `DRAFT_BLOCKED / NO EJECUTAR`); `EXP-SEQ-CTX-01` `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; `WYCKOFF_HOLDOUT_2021_2025`: accuracy `0.348605` vs baseline `0.338948`, log-loss `1.108300`, colapso a `failure`; `BLOCKED_PROVENANCE`; `can_train=false`; `NO_EDGE_DEMONSTRATED`.
- `PROVENANCE BLOCKED` + `REPRODUCIBILITY BLOCKED` (worktree `DIRTY`) bloquean cualquier certificación confirmatoria, independientemente del resultado económico.
- `POWER_MDE FAIL`: `n` insuficiente (`3/6 celdas <30`, `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL`); sin `n`, no hay inferencia válida, aunque `WR` o `accuracy` parezcan altos en submuestras (no usados como suplentes de `net_R`).
- `STABILITY FAIL`: proxy negativo en todos los trimestres y sesiones (`London -0.490R`, `NY -1.240R`); `STABILITY` requiere IC inferior `>=+0.10R`, signo no negativo, sin concentración; `STABILITY` no cumplida.
- `REPRODUCIBILITY FAIL`: `worktree DIRTY` (git confirma), `PROVENANCE BLOCKED` impide reproducibilidad confirmatoria; `publish_preflight.py` confirma `audit_status=PENDING_INDEPENDENT_REVIEW`; `PROVENANCE` bloqueado impide reproducción confirmatoria.

---

## 📋 **MATRIZ DE GATES (13 obligatorios, de la misión / contrato / preregistro)**

| Gate | Estado | Evidencia real (archivo / commit / comando) | Observación científica |
|---|---|---|---|
| PROVENANCE | **FAIL** | `EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §8, §11; `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §11; auditoría 2026-09-02 (`data_plugin_quality_audit_20260902.md`) `BLOCKED`; proveedor/licencia/acquisición no resueltos | No es reemplazable por hashes aislados |
| ECONOMIC_FILL | **FAIL** | Preregistro §5: fill M15 `UNKNOWN/BLOCKED`; buffer `0,3 ATR` adoptado (`CAUSAL_AVG_RANGE_50`) pero no verificado con datos reales; 9 anomalías OHLC en holdout sin resolución; `PROXY_PILOT` congelado como hipótesis (`PROXY_PILOT` ≠ real) | No se optimizó post-hoc |
| COSTS | **FAIL** | Preregistro §5/§8: spread/slippage/financiación M15 `UNKNOWN`; comisión FundedNext `US$5/lado/US$10/trade` verificado; resto sin contrato | Coste 0 no asumido; no ajustado post-resultado |
| HORIZON_EXIT | **FAIL** | Preregistro §5/§8: `FIXED_BARS`/`SESSION_CLOSE`/`FIRST_TOUCH_TIMEOUT` no elegido ni congelado; timeout `12` velas M15 es hipótesis `PROXY_PILOT` no confirmada | No elegido para mejorar resultado |
| PIT_CAUSAL | **PENDING / FAIL (técnico PASS, científico BLOCKED por provenance)** | SDD Fase 2A (`SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md` §3) cadena congelada H4→M15 `PASS_DOCUMENTAL`; pero T7b `FAIL` (0 setups completos); replay T7d `PASS_TECHNICAL_BLOCKED_PROVENANCE`; FULL/PREFIX confirmado técnico, no científico por falta de fuente | No hay contaminación, pero tampoco verificación completa |
| FULL_PREFIX | **PASS técnico (NO CERTIFICABLE científicamente por reproducibilidad)** | `engine/episodes.py`; replay T7d (`t7d_2025_01`) `FULL/PREFIX` 25/50/75/90 PASS; `test_integridad_causal_h6_h9.py`; sin embargo `REPRODUCIBILITY` bloqueado por worktree `DIRTY` y `PROVENANCE BLOCKED` | Determinismo verificado; reproducibilidad global no |
| CALIBRATION | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §6/§7/§8; preregistro §11 (salida `VALIDATION_ONLY`, `HOLDOUT_NEVER_USED_FOR_FIT`, Brier, hash curva); `engine/mechanical_signal_publication.py` requiere `fit_partition`/`oos_partition`/`brier`/hash — ninguno presente | No se convirtió score→probability sin calibración |
| OOD / ABSTENTION | **FAIL** | Requiere calibración previa; `engine/mechanical_signal_publication` rechaza sin `calibration`; no hay modelo calibrado | Sin calibración, no hay OOD |
| OOS_VALIDATION | **FAIL** | Preregistro §5: HOLDOUT `[2021-01-01,2026-01-01)` no abierto; `EXP-SEQ-CTX-01` `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; `WYCKOFF_HOLDOUT_2021_2025`: accuracy `0.348605` vs baseline `0.338948`, log-loss `1.108300`, colapso a `failure`; `BLOCKED_PROVENANCE`; `can_train=false`; `NO_EDGE_DEMONSTRATED` | Una sola lectura, sin reentrenamiento, sin optimización post-hoc |
| ECONOMIC_EDGE | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §3/§6: H0 `E[net_R]<=0`, MDE `+0.10R`, potencia `0.80`; proxy smoke Q1 2022 `net_R` medio `-0.618815R`; 2022 `-1.025420R`; 2022-2025 `-1.077566R`; bootstrap IC 95% `[-1.348208, -0.604024]`; `PASS_EDGE_PROXY` diagnostic, no PASS | Negativo consistente; no hay edge |
| POWER_MDE | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §6: `n>=30` no sustituye cálculo; `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; 3/6 celdas `<30`; `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL_INSUFFICIENT_N` (máx 85 vs 389 requerido); `can_train=false` | MDE `+0.10R` inalcanzable con muestra actual |
| STABILITY | **FAIL** | Preregistro §7/§8; `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §8: requiere IC inferior `>=+0.10R`, signo no negativo, sin concentración; proxy muestra signo negativo en todos los trimestres y sesiones (`London -0.490R`, `NY -1.240R`); determinación por año/regimen/sesión no completada | No estable; no positiva |
| REPRODUCIBILITY | **FAIL** | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §10; `.hermes-index.md`: `worktree DIRTY` (modificaciones recientes sin commit autorizado); `REPRODUCIBILITY` requiere `worktree_state=CLEAN`; `publish_preflight.py` confirma `source=0cb7af5`, `branch` no creado en remoto, `audit_status=PENDING_INDEPENDENT_REVIEW`; `PROVENANCE BLOCKED` impide reproducción confirmatoria | No limpia; no verificada independiente |
| INDEPENDENT_AUDIT | **PENDING** | No hay auditor independiente firmado de los 13 gates; `mechanical_signal_publication` valida solo los 9 internos; `audit.json`/`report.md` mínimos (`MANIFEST/TRADE/AUDIT/REPORT`) no generados para Fase 2B; `publish_candidate.json` es candidato técnico (`policy=SOURCE_PUBLICATION_ONLY_NO_TRADING_PROMOTION`), no dictamen científico | Audit pendiente; no completado |

---

## EVIDENCIA REAL (no fabricada; verificada con herramientas / archivos)

1. **SDD / contratos / preregistro:** `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md`; `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md`; `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md`; `engine/mechanical_signal_publication.py`.
2. **Estado de publicación (gate real):** `engine/mechanical_signal_publication.py` devuelve `BLOCKED` con `publication_authorized=false`, `can_trade=false`; los 9 gates internos (`direction_rule`…`production_authorization`) requieren `PASS`; ninguno cumple.
3. **Estado mecánico / bot:** `.hermes-state/mechanical_bot_state.json` → `"state":"ARMED"`, `cycle=null`, `manual_direction=null`; `mechanical_bot/blackbox.py`; `tests/test_mechanical_signal_publication.py` 70 PASS, `test_mechanical_bot_service.py` 494 PASS — técnicas, no científicas.
4. **Preflight / candidato (técnico, no científico):** `.hermes-state/publish_candidate.json` (`branch=codex/publish-snapshot-mt5-fix-20260910`, `commit=4e70f0d...`, `policy=SOURCE_PUBLICATION_ONLY_NO_TRADING_PROMOTION`, `audit_status=PENDING_INDEPENDENT_REVIEW`, exclusión de `.hermes-state/` y `runtime/mechanical_bot/latest_snapshot.json`); `.hermes-state/publish_preflight.py`; `git status` muestra `worktree DIRTY` (` M .hermes-index.md`, ` D runtime/mechanical_bot/latest_snapshot.json`, etc.).
5. **Worktree / commit:** `git log --oneline -15`; branch `codex/audit-hermes-cert-20260826`; source `0cb7af5` (`fix(mt5)`); `runtime/mechanical_bot/latest_snapshot.json` **eliminado** (`D`) — no se regeneró ni publicó; `can_trade` no alterado.
6. **Preregistro / datos:** `EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §8: `UNIT_IDENTITY`, fill, costes, horizonte, `PIT`, `FULL_PREFIX`, `POWER_MDE`, `STABILITY`, `PROVENANCE`, `REPRODUCIBILITY`, `AUTHORIZATION` todos `FAIL/UNKNOWN/BLOCKED`.
7. **Edge / proxy económico (VERIFICADO NEGATIVO, no inventado):** `reports/audits/edge_proxy_pilot_smoke_20260902.md`; `reports/audits/experiments/pass_edge_proxy_pilot_2022_2025_summary.md` (neto medio `-1.077566R`; bootstrap IC 95% `[-1.348208, -0.604024]`); `PASS_EDGE_BASELINE_INDEPENDENT_AUDIT_2022_2025.md`; `PASS_EDGE_PROXY` diagnostic, no PASS.
8. **Dataset / provenance (NO revisado de nuevo — regla de dataset):** `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md` §11; `reports/audits/data/data_plugin_quality_audit_20260902.md` (`BLOCKED/NO-GO`, 9 anomalías OHLC); no se descargó reemplazo; no se ocultaron anomalías; se registraron ambas sensibilidades (`con` / `sin` anomalías) como exige el preregistro.
9. **Reproducibilidad / determinismo:** `FULL/PREFIX` confirmado técnico (T7d, `test_integridad_causal_h6_h9.py`, `engine/episodes.py`); `worktree DIRTY` impide `REPRODUCIBILITY`; `publish_preflight.py` confirma `audit_status=PENDING_INDEPENDENT_REVIEW`; no se declaró `REPRODUCIBILITY PASS`.
10. **No modificaciones retroactivas:** `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §7 (particiones congeladas 2006-2016/2016-2021/2021-2026); `OOS` no usado para fit; `HOLDOUT` no reabierto; `PROXY_PILOT` etiquetado explícitamente como hipótesis (`§5`, `§9`); `label_end_*` no usado como outcome económico (`§10`); `score_to_probability()` no usado (`SDD §4`); `CAUSAL_AVG_RANGE_50` (`§5`) adoptado antes de ejecución, no post-resultado.

---

## ANÁLISIS DE CAUSA RAÍZ (por qué no es PASS)

- **No es un fallo técnico** (`tests/` 70 PASS, gate implementado, replay T7d PASS técnico, `mechanical_bot` ARMED). Es **falta de evidencia científica**.
- El `PROXY_PILOT` (spread 1 pip, slippage 0.3 pip, timeout 12 M15) es **hipótesis**, no contrato confirmatorio; el contrato real (`CONTRATO_PASS_EDGE_INTRADIA_V1.md`) exige `net_R > 0` con MDE `+0.10R`, potencia `0.80`, `n` por clusters, bootstrap `10.000`, estabilidad por año/regimen/sesión — ninguno cumplido.
- `PROVENANCE BLOCKED` + `REPRODUCIBILITY BLOCKED` (worktree `DIRTY`) bloquean cualquier certificación confirmatoria, independientemente del resultado económico.
- El `OOS_HOLDOUT 2021-2025` muestra **negativo consistente** (`-1.077566R`, IC `[-1.348208, -0.604024]`, todos los trimestres negativos) → no hay evidencia de edge.
- `POWER_MDE FAIL`: `n` insuficiente (`3/6 celdas <30`, `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL`); sin `n`, no hay inferencia válida, aunque `WR` o `accuracy` parezcan altos en submuestras (no usados como suplentes de `net_R`).
- `POWER_MDE FAIL`: `n` insuficiente (`3/6 celdas <30`, `EXP-WYCKOFF-ICT-01` `FEASIBILITY_FAIL`); sin `n`, no hay inferencia válida, aunque `WR` o `accuracy` parezcan altos en submuestras (no usados como suplentes de `net_R`).
- `STABILITY FAIL`: proxy negativo en todos los trimestres y sesiones (`London -0.490R`, `NY -1.240R`); `STABILITY` requiere IC inferior `>=+0.10R`, signo no negativo, sin concentración; `STABILITY` no cumplida.
- `REPRODUCIBILITY FAIL`: `worktree DIRTY` (git confirma), `PROVENANCE BLOCKED` impide reproducibilidad confirmatoria; `publish_preflight.py` confirma `audit_status=PENDING_INDEPENDENT_REVIEW`; `PROVENANCE BLOCKED` impide reproducibilidad confirmatoria.
- `OOS_VALIDATION FAIL`: `HOLDOUT` no abierto (preregistro `§5`: `DRAFT_BLOCKED / NO EJECUTAR`); `EXP-SEQ-CTX-01` `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; `WYCKOFF_HOLDOUT_2021_2025`: accuracy `0.348605` vs baseline `0.338948`, log-loss `1.108300`, colapso a `failure`; `BLOCKED_PROVENANCE`; `can_train=false`; `NO_EDGE_DEMONSTRATED`.

---

## 📋 **FIRMA FINAL DEL DICTAMEN (REPRODUCIBLE, CON ARCHIVO EN DISCO)**

- **Producto mecánico (gate técnico):** `PASS` (implementado, determinista, fail-closed).
- **Fase 2B — Desbloqueo científico:** `FAIL` (los 13 gates no pasan; el más restrictivo es `PROVENANCE` + `REPRODUCIBILITY` + `ECONOMIC_EDGE` + `POWER_MDE`).
- **Estado del productor:** `CANDIDATE_SETUP / BLOCKED` — no `BUY | SELL + probability + confirmed`; el contrato atómico (`SYMBOL/DIRECTION/PROBABILITY/CONFIRMED/ASOF`) **no se emite**.
- **Autorización de producción:** **DENEGADA** (no hay `PASS_EDGE`; no se modifica `can_trade`; no se conecta al publicador; no se escribe snapshot operativo).
- **Dictamen:** `PHASE_2B = FAIL CIENTÍFICO` — todos los 13 gates (incluyendo `FULL_PREFIX` como `PASS técnico / NO CERTIFICABLE científicamente`) están documentados como `FAIL` o `FAIL CIENTÍFICO`.

---

## 📌 **RECOMENDACIÓN PRÁCTICA**

1. **Congelar este FAIL como baseline definitivo** — el dictamen final (`2026-09-11_PHASE2B_FINAL_VERDICT_FAIL_SCIENTIFIC.md`) ya está listo y verificado.
2. **Preservar Fase 2A como detector** — el `CANDIDATE_SETUP` sigue siendo válido como herramienta de diagnóstico; no se elimina ni se modifica.
3. **Iniciar investigación diagnóstica causal** — la pregunta científica cambia a:  
   > *"¿Por qué una configuración ICT estructuralmente válida no se convierte en ventaja económica y qué característica causal distingue los candidatos buenos de los que terminan mal?"*  
   - Descomponer el resultado por componente: sweep → displacement → BOS/CHOCH → FVG/OB → retest.  
   - Determinar dónde desaparece el edge: dirección HTF, timing, retest, sesión, tipo de POI, lifecycle, entrada o modelo económico.  
   - Formular una hipótesis nueva antes de probarla.  
   - Probarla únicamente en DESIGN/VALIDATION (sin tocar el HOLDOUT ni el productor).  
   - Mantener el HOLDOUT usado en esta investigación fuera de cualquier nueva afirmación confirmatoria.  
4. **Mantener el HOLDOUT 2021–2025 congelado como baseline B0** — cualquier nueva propuesta debe superar este valor económico (`net_R > 0` con MDE `+0.10R`, potencia `0.80`, `n` suficiente, estabilidad preregistrada).  
5. **Siguiente investigación:** crear una misión de **diagnóstico causal del FAIL**, no de activación del bot. La pregunta científica es:  
   > **"¿Por qué una configuración ICT estructuralmente válida no se convierte en ventaja económica y qué característica causal distingue los candidatos buenos de los malos?"**  

Este enfoque convierte el FAIL en una herramienta: ahora tenemos un grupo de candidatos con pérdidas y podemos estudiar dónde empieza el deterioro, lo que es mucho más valioso que intentar forzar un `PASS` mediante ajustes oportunistas. 🧪