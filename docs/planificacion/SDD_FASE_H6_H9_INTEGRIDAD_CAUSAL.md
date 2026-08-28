# SDD — Fase H6–H9: Integridad Causal de Market State y Setup Builder

**Estado:** NORMATIVO (cierre por evidencia, 2026-08-28)
**Alcance:** MarketObject, MarketState, Lifecycle, relations, Setup Builder
**Fuera de alcance:** Episodes/Funnel, backtest, IA, edge, experimentos

## 1. Objetivo general

Demostrar y certificar que MarketState, Lifecycle y Setup Builder construyen
únicamente estados y setups temporalmente posibles, causalmente ordenados,
correctamente gobernados por su temporalidad de autoridad y bloqueados cuando
el contexto no autoriza su utilización.

La fase TERMINA solo cuando se demuestra (no por conteo de tests):

```
OBJETOS CORRECTOS → LIFECYCLE CORRECTO → ESTADO EN T CORRECTO →
RELACIONES MTF CORRECTAS → SETUP CAUSALMENTE POSIBLE → ELEGIBILIDAD CORRECTA
→ AUDITORÍA ADVERSARIAL → REPRODUCIBILIDAD → CERTIFICACIÓN
```

Hasta entonces Episodes/Funnel permanece BLOQUEADO.

## 2. Contrato temporal (OE-01)

Cada `MarketObject` carry esta semántica inequívoca:

| Campo | Significado | Regla |
|---|---|---|
| `origin_tf` | TF donde nació | inmutable tras nacimiento |
| `authority_tf` | TF que decide transición | `== origin_tf` (garantizado en `__post_init__`) |
| `lifecycle_tf` | TF del lifecycle | `== origin_tf` |
| `observed_tf` | TF subordinada que observa (no decide) | debe ser ESTRICTAMENTE inferior en jerarquía |
| `candidate_time` | instante de huella | `<= confirmation_time` |
| `confirmation_time` | instante operativo | `<= tradable_time` |
| `tradable_time` | instante en que es operable | contrato `candidate<=confirmation<=tradable` |
| `bar_index` | índice de vela | **solo comparable dentro de la MISMA TF** |

Jerarquía de TF (OE-04): `D1(6) > H4(5) > H1(4) > M15(3) > M5(2) > M1(1)`.

## 3. Reglas científicas

- **A — Tiempo causal:** `POI <= refinement <= confirmation(BOS) <= trigger` por
  `confirmation_time` (no `bar_index` cross-TF). Validado en `classify_eligibility`.
- **B — Estado en T:** `MarketState.projection_at(T)` contiene solo lo conocido
  hasta T; nada de T+1 lo modifica. (YA implementado v1.)
- **C — Autoridad MTF:** `observe_lower_tf` rechaza `observed_tf` no estrictamente
  inferior a `origin_tf` (ni igual, ni superior). `evaluate` exige vela de
  `authority_tf`. (Corregido OE-04/H8.)
- **D — Fail closed:** ante contradicción/timestamp imposible/TF inválida/contexto
  `aligned=False` → bloquear, no adivinar. (Corregido OE-05/H9.)
- **E — Existencia ≠ elegibilidad:** objeto ACTIVE con `aligned=False` → `BLOCKED`.

## 4. Hallazgos de la auditoría adversarial (OE-09/10)

La fase encontró y cerró defectos REALES (no los 4 ficticios del "análisis
ChatGPT" externo, que mezclaba casos ya cubiertos con casos inexistentes):

| ID | Defecto real | Corrección | Estado |
|---|---|---|---|
| H7 | `MarketState.advance_bar` aceptaba velas fuera de orden | guarda fail-closed `OUT_OF_ORDER` por reloj de TF + registro | CERRADO |
| OE-07 | `relate_fvg_ob` comparaba `bar_index` entre TF distintas | orden causal cross-TF por `confirmation_time`; misma TF por `bar_index` | CERRADO |
| H9 | `classify_eligibility` devolvía ELIGIBLE con `aligned=False` | `_htf_aligned` respeta `aligned=False` explícito (ausente => alineado) | CERRADO |
| H6 | `classify_eligibility` no validaba confirmation anterior al POI | guarda `confirmation_time >= poi.confirmation_time` | CERRADO |
| H8 | `observe_lower_tf` aceptaba `observed_tf == origin_tf` | jerarquía estricta: solo TF inferior observa | CERRADO |

Casos del "análisis ChatGPT" ya CUBIERTOS antes de esta fase (verificados por
los tests adversariales, no por afirmación): H6 en `relate_fvg_ob` strict; H8
en `evaluate`/`observe_lower_tf` tf-check; H9 ya tenía `_htf_aligned` pero con
el hueco del flag explícito (cerrado aquí).

## 5. Evidencia

- `tests/test_integridad_causal_h6_h9.py`: 16 tests adversariales (OE-02,03,04,05,06,07,08,10).
- `pytest tests/` completo: **334 passed, 0 failed** (era 318 en el texto externo;
  328 antes de la fase; +16 de la suite nueva, +0 regresiones).
- Graphify actualizado a HEAD (OE-11).

## 6. Criterio de certificación

```
H6=PASS H7=PASS H8=PASS H9=PASS
Lifecycle=PASS MTF=PASS Causal=PASS Eligibility=PASS
Adversarial=PASS FULL/PREFIX=PASS Determinismo=PASS
0 BLOCKER 0 CRITICAL 0 xfail ocultos
→ GO a Episodes/Funnel
```

**El número de tests no certifica nada por sí solo.** La certificación requiere
el GO explícito del auditor (Codex/independiente) sobre los gates de
reproducibilidad/riesgo, conforme a `AGENTS.md` (sin push en cierre normal).
