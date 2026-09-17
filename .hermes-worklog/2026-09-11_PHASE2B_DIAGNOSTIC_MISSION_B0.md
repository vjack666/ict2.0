# MISIÓN DIAGNÓSTICA CAUSAL DEL FAIL — BASELINE B0 = -1.077566R

**AGENTE:** Hermes / Codex  
**DEPARTAMENTO:** D5 CRO / Assurance  
**MISION:** MC-20260911-153509-dfab2f-DIAGNOSTIC (derivada de FASE 2B FAIL)  
**FECHA:** 2026-09-11  
**BASELINE B0:** `net_R = -1.077566R` (2022-2025, IC `[-1.348208, -0.604024]`, todos los trimestres/sesiones/regímenes negativos). Congelado. No se borra, no se recalcula, no se sustituye.

---

## 1. ESTADO DEL PRODUCTOR (NO SE TOCA)

| Elemento | Estado | Evidencia |
|---|---|---|
| `engine/mechanical_signal_publication.py` | `BLOCKED`; 9 gates internos `PASS` técnico | `mechanical_bot_state.json` = `ARMED`; `publish_candidate.json` = candidato técnico (`SOURCE_PUBLICATION_ONLY`) |
| Fase 2A detector (`CANDIDATE_SETUP`) | ✅ CONSERVADO como detector DIAGNÓSTICO | `SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md` §3; `mechanical_signal_assessment.py` |
| Probabilidad del CANDIDATE | **NO CALIBRADA** (campo diagnóstico, no estadístico) | Sin `brier`/`reliability`/hash curva / `VALIDATION_ONLY`; `min_probability=0.70` es threshold de publicación, no de calibración |
| `confirmed` | Validación ESTRUCTURAL, no económica (`confirmed=true` ≠ edge) | `core.py`: `min_probability` + `confirmed` + `m15_gate` ≠ `net_R>0` |
| Fase 2B (operable) | ❌ FAIL CIENTÍFICO — permanece bloqueado | Archivo `.hermes-worklog/2026-09-11_PHASE2B_FINAL_VERDICT_FAIL_SCIENTIFIC.md` (32.684 bytes, verificado) |
| HOLDOUT 2021-2025 | ❌ NO ABIERTO para esta investigación; congelado como B0 | `preregistro §5`; no se usa para ajuste ni para afirmar PASS |

---

## 2. REGLAS DE ESTA MISIÓN (heredan de FASE 2B, no permiten modificarlo)

- **No modificar el productor mecánico.** `mechanical_bot/`, `engine/mechanical_signal_publication.py`, `core.py`, `service.py` — intactos.
- **No usar el HOLDOUT para ninguna nueva afirmación confirmatoria.** El `-1.077566R` es B0; cualquier mejora debe demostrar `net_R > 0` + MDE `+0.10R` + potencia `0.80` + `n>=30` + IC inferior `>=+0.10R` + estabilidad por trimestre/sesión REGISTRADA EN DESIGN/VALIDATION, no en el mismo HOLDOUT.
- **No convertir score → probabilidad sin calibración.** `SDD §4`; `preregistro §11`; `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §6/§7/§8. Lo que hoy es `probability` en `CANDIDATE_SETUP` es un score de confirmación estructural; si la nueva hipótesis requiere probabilidad calibrada, debe construirse en `TRAIN` con `VALIDATION_ONLY`, con curva Brier, y validarse en `VALIDATION` antes de tocar `HOLDOUT`.
- **Una variable por experimento (descomposición causal).** No mezclar `sweep + displacement + BO` en un solo test; descomponer por componente de la secuencia ICT.
- **No seleccionar casos favorables.** Si un componente (p.ej. retest) parece mejorar el resultado, la evidencia debe ser `n>=30` por subgrupo, con intervalo, con reproducibilidad, sin eliminar perdedores.

---

## 3. PREGUNTA CIENTÍFICA NUEVA (reemplaza "¿podemos activar?")

> **¿Qué propiedad causal de un `CANDIDATE_SETUP` distingue los que terminan con `net_R > 0` de los que terminan con `net_R < 0` (como el B0 actual), sin optimizar retrospectivamente el productor?**

Esto no busca "arreglar" el productor. Busca **entender** dónde se rompe el pipeline:

```
HTF context (D1/H4) → Liquidez → Sweep → Displacement → BOS/CHOCH → POI (FVG/OB) → Retest → Entry → LTF confirmation → Resultado económico
```

Cada flecha es un candidato a "desaparecer el edge".

---

## 4. ESTRUCTURA DEL ESTUDIO DIAGNÓSTICO (propuesta de diseño — NO ejecutado aún)

### 4.1 Hipótesis preliminar (a validar, NO prematura)

`H-DIAG-01`: El colapso del `net_R` ocurre en la transición `POI → Retest → Entry`; los candidatos con retest fallido o con POI sintético (`bos_level ± 0.5·ATR`) contribuyen desproporcionadamente al `-1.077566R`.

`H-DIAG-02`: La dirección HTF (`bull/bear`) interactúa con el resultado de forma asimétrica (p. ej. `SELL` con contexto `BULLISH` H4 falla más que `BUY` con `BEARISH`), y esa interacción explica parte del `STABILITY FAIL`.

`H-DIAG-03`: El `CANDIDATE_SETUP` con `FVG/OB` de baja calidad (solo booleano, sin `parent_event`, sin `zone_high/low`, sin `origin_tf` verificable) es estadísticamente indistinguible de un setup sin estructura, y por tanto su `probability` no debe interpretarse como predictiva.

---

## 5. METODOLOGÍA (si se autoriza por Ruben / Codex)

| Paso | Qué | Cómo | Restricción |
|---|---|---|---|
| **A. Corpus** | Reutilizar `CANDIDATE_SETUP` existente (Fase 2A) | `engine/mechanical_signal_assessment.py`; `SDD §3`; NO regenerar; NO eliminar perdedores | Sin modificarlos; con `lineage`, `decision_time`, `snapshot/hash` |
| **B. Descomposición** | Por componente de secuencia | `sweep_idx` → `displace_idx` → `bos_idx` → `poi_idx` → `entry_at` (`sequence.py` o `expediente.phase_events`) | Un componente por sub-estudio |
| **C. Etiquetado** | Resultado económico posterior según contrato B0 | Usar `PROXY_PILOT` (spread 1 pip, slippage 0.3, timeout 12 M15) como **hipótesis de comparación**; NO como verdad; comparar `net_R` por subgrupo | No optimizar parametros post-resultado; congelar `PROXY_PILOT` antes |
| **D. Separación** | TRAIN / VALID / HOLDOUT (ya congelado) | `TRAIN` para descomposición; `VALIDATION` para selección de subgrupo; `HOLDOUT` solo para **verificación final** de una hipótesis ya seleccionada en `VALIDATION` | El `HOLDOUT` NO se usa para descubrir; solo para confirmar |
| **E. Calibración (si aplica)** | Si un subgrupo requiere probabilidad | `brier`, `reliability`, `calibration curve`; `VALIDATION_ONLY`; nunca convertir `score` directo; `HOLDOUT` nunca usado para fit | `SDD §4`; `preregistro §11` |
| **F. Test de poder** | `n` por subgrupo post-descomposición | `n>=30`; si `<30`, marcar `BLOCKED` (no inferir); ampliar período permitido, NO cambiar hipótesis | `CONTRATO §6`; `preregistro §11` |

---

## 6. LO QUE NO HAREMOS (restricciones duras de esta misión)

- ❌ No abriremos el `HOLDOUT 2021-2025` para esta investigación.
- ❌ No modificaremos `ENGINE`, `mechanical_bot/`, `core.py`, `service.py`.
- ❌ No generaremos un nuevo `CANDIDATE_SETUP`; solo analizaremos los existentes.
- ❌ No usaremos `score → probability` sin calibración demostrada.
- ❌ No eliminaremos operaciones perdedoras ni seleccionaremos casos favorables.
- ❌ No optimizaremos `PROXY_PILOT` mirando resultados; queda congelado como hipótesis de referencia.
- ❌ No declararemos `PASS` para ningún sub-estudio sin `n>=30`, IC, reproducibilidad, y evidencia de `net_R > 0` en `VALIDATION` (no en `HOLDOUT`).

---

## 7. BASELINE B0 — REGISTRADO (no negociable)

```text
BASELINE PHASE_2B_2026-09-11 (B0)
net_R (2022-2025, proxy): -1.077566R
IC 95% bootstrap: [-1.348208, -0.604024]
Trimestres: todos negativos
Sesiones: London -0.489994R / NY -1.239506R / otros -1.166782R
Regímenes: BULLISH -1.096718R / BEARISH -1.055892R
n efectivo: <30 en 3/6 celdas (FEASIBILITY_FAIL_INSUFFICIENT_N)
HOLDOUT: NO ABIERTO para este estudio
Estado: FAIL CIENTÍFICO — congelado como referencia
```

Cualquier nuevo resultado debe ser comparado contra B0 con la misma métrica (`net_R`, mismo modelo económico `PROXY_PILOT`, mismos costes, misma partición temporal). No se puede usar una métrica distinta para "ganarle".

---

## 8. TAREAS PENDIENTES SI SE AUTORIZA

- [ ] Diseño formal de `H-DIAG-01/02/03` + preregistro de esta misión diagnóstica (`EXP_DIAGNOSTIC_FAIL_01_PREREGISTRATION.md` o equivalente)
- [ ] Revisión de `engine/sequence.py` + `engine/expediente.py` para confirmar que `phase_events` conserva suficiente info para la descomposición (ver `smc-systems-research` Fase 2 / info-loss audit)
- [ ] Definición del subgrupo más prometedor para `VALIDATION` (basado en evidencia de `CANDIDATE_SETUP` existente, NO en optimización)
- [ ] Ejecución en `TRAIN` / `VALIDATION` (si Ruben/Codex autoriza y confirma que `worktree` está limpio o que el dirty no afecta el análisis)
- [ ] Verificación independiente (`INDEPENDENT_AUDIT`) si algún sub-estudio alcanza `READY_FOR_INDEPENDENT_AUDIT`

---

## 9. REFERENCIAS (reproducibles en disco en esta sesión)

- `.hermes-worklog/2026-09-11_PHASE2B_FINAL_VERDICT_FAIL_SCIENTIFIC.md` (dictamen FASE 2B)
- `.hermes-worklog/2026-09-11_FASE2B_UNLOCK_MISSION_OPENED.md`
- `.hermes/plans/2026-09-11_FASE2B_UNLOCK_SCIENTIFIC_MISSION.md`
- `reports/audits/experiments/pass_edge_proxy_pilot_2022_2025_summary.md`
- `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md`
- `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md`
- `engine/mechanical_signal_publication.py`; `mechanical_signal_assessment.py`; `core.py`
- `skill_view(name='mechanical-bot-audit')`; `skill_view(name='trading-strategy-audit')`; `skill_view(name='ict-system-task-closure')`

---

*Dictamen: FASE 2B = FAIL CIENTÍFICO. Productor no desbloqueado. El FAIL se convierte en herramienta de diagnóstico. Base B0 congelada. No se modifica el sistema. La siguiente investigación es causal, no operativa.*
