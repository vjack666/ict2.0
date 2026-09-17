# FASE 2B — CERRADA / ARCHIVADA (2026-09-11)

**Decisión:** FASE 2B concluida como experimento terminado.  
**Resultado doctoral:** `FAIL CIENTÍFICO` (edge económico no demostrado, calibration/stability/power/OOS en FAIL, auditoría independiente pendiente, productor operable bloqueado).  
**No se alteró el productor.** `mechanical_bot/`, `engine/mechanical_signal_publication.py`, `core.py` y `service.py` intactos. `can_trade=false` permanente. `entry_authorized=false`. Sin snapshot operativo.

## MATRIZ DE GATES (archivada como ciencia, no como error)

| Gate | Estado final | Observación |
|---|---|---|
| FULL/PREFIX técnico | ✅ PASS técnico | Determinismo verificado (T7d, episodes, test_integridad_causal_h6_h9). Científicamente no certificable por reproducibilidad global (worktree DIRTY + provenance). |
| PIT_CAUSAL | ⛔ BLOQUEADO científicamente | Cadena H4→M15 documentada; T7b FAIL (0 setups completos); T7d PASS_TECHNICAL_BLOCKED; sin fuente confirmatoria. |
| PROVENANCE / FILL / COSTS | ⛔ BLOCKED | Proveedor/licencia/acquisición no resueltos; fill M15 unknown; costes parcialmente conocidos pero spread/slippage/financiación M15 sin contrato. |
| CALIBRATION | ❌ FAIL | Sin VALIDATION_ONLY / HOLDOUT_NEVER_USED_FOR_FIT / Brier / hash de curva reliable; no existe modelo calibrado. score ≠ probabilidad. |
| OOD / ABSTENTION | ❌ FAIL | Requiere calibración previa; no hay modelo calibrado. |
| OOS_VALIDATION | ❌ FAIL | HOLDOUT 2021-2025 no abierto; EXP-SEQ-CTX-01 OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE; WYCKOFF_HOLDOUT: accuracy 0.348605 vs baseline 0.338948, colapso a failure; NO_EDGE_DEMONSTRATED. |
| ECONOMIC_EDGE | ❌ FAIL CIENTÍFICO | net_R medio 2022-2025 = -1.077566R, IC [-1.348208, -0.604024]; proxy consistente en trimestres, sesiones y regímenes; EXCHANGEABLE vs PREFERRED. |
| POWER_MDE | ❌ FAIL | n insuficiente (3/6 celdas <30; EXP-WYCKOFF-ICT-01 FEASIBILITY_FAIL_INSUFFICIENT_N, máx 85 vs 389). |
| STABILITY | ❌ FAIL | Negativo en todos los trimestres y sesiones y regímenes. |
| REPRODUCIBILITY | ❌ FAIL | worktree DIRTY (git confirma); provenance BLOCKED; audit_status=PENDING_INDEPENDENT_REVIEW. |
| INDEPENDENT_AUDIT | ⏳ PENDING | Autoauditoría adversarial realizada, no certificada independientemente. No hay audit.json/report.md mínimos para Fase 2B. |
| PRODUCTOR OPERABLE | 🔒 BLOCKED | Gate técnico engine.mechanical_signal_publication BLOCKED. No publica SYMBOL/DIRECTION/PROBABILITY/CONFIRMED/ASOF. |

---

## BASELINE B0 — REFERENCIA HISTÓRICA CONGELADA (no negociable)

```text
BASELINE_PHASE_2B_2026-09-11
=============================
net_R (2022-2025, proxy PROXY_PILOT): -1.077566R
IC bootstrap 95%: [-1.348208, -0.604024]
Trimestres: todos negativos
Sesiones: London -0.489994R / NY -1.239506R / otros -1.166782R
Regímenes: BULLISH -1.096718R / BEARISH -1.055892R
n efectivo: 3/6 celdas <30 (FEASIBILITY_FAIL_INSUFFICIENT_N)
HOLDOUT 2021-2025: NO abierto para esta misión; congelado para selectividad futura.
```

**Regla de oro B0:** `B0 es una referencia histórica congelada, no un objetivo de optimización.` La investigación B1 puede comparar contra `-1.077566R` como campo de comparación, pero NO puede modificar reglas mirando repetidamente el HOLDOUT 2021-2025 para "ganarle". Ese período ya aportó información y permanece fuera de la selección de nuevas hipótesis.

---

## PRÓXIMA UNIDAD DE TRABAJO: MISIÓN DIAGNÓSTICA B1

**FOQUE:** sobre los `CANDIDATE_SETUP` existentes (Fase 2A), descomponer la cadena causal para respuesta a:

> ¿En qué punto exacto de la cadena causal aparece la diferencia entre candidatos rentables y candidatos perdedores?

**Cadena de descomposición:**

```text
HTF CONTEXT
    ↓
SWEEP
    ↓
DISPLACEMENT
    ↓
BOS / CHOCH
    ↓
FVG / OB
    ↓
RETEST
    ↓
ENTRY / TIMING
    ↓
RESULTADO ECONÓMICO
```

**Para cada etapa:** probar si añade información discrimativa o está presente indistintamente en ganadores y perdedores.

**Reglas de B1:**

- No modificar el productor mecánico (`mechanical_bot/`, `engine/mechanical_signal_publication.py`, `core.py`, `service.py`).
- No crear otro bot, clasificador ni IA.
- Usar únicamente **DESIGN y VALIDATION** para investigar y seleccionar hipótesis.
- El HOLDOUT 2021-2025 solo para **verificación final** de hipótesis ya seleccionada en VALIDATION.
- Una variable por experimento de descomposición.
- Si un componente (p. ej. retest, POI de calidad) parece diferenciar, la evidencia necesita `n >= 30` por subgrupo, con intervalo, bajo el mismo `PROXY_PILOT`.
- B0 permanente como compartir de comparación (`net_R` mismo modelo económico).
- No optimizar `PROXY_PILOT` mirando resultados; congelarlo como hipótesis de referencia antes de ejecutar.
- Si emerge una hipótesis robusta, formulación preregistrada; **después** de esa hipótesis cerrada abierto thread experimental.

**Decisión de dirección:** FASE 2B archivada. B1 (diagnóstica causal) es la siguiente línea de investigación sin autorización adicional de uso del sistema operativo.

> 📄 Archivo: `.hermes-worklog/2026-09-11_PHASE2B_DIAGNOSTIC_MISSION_B0.md` (misión B1)  📁 listo en disco.

---

*Estado de proyecto: FASE 2B CERRADA. Productor no desbloqueado. B0 congelado. Próximo trabajo: misión diagnóstica B1.* 🧪

