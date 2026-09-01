# Bitácora — Fase H6–H9: Integridad Causal (tesis cerrada por evidencia)

**Fecha:** 2026-08-28 · **Autor:** Hermes (modo RED TEAM tras desarrollo)
**Rama:** codex/audit-hermes-cert-20260826
**Plan:** Tesis operativa H6–H9 (Ruben) — 12 objetivos OE-01..OE-12, gates binarios.

## [INICIO]
- Tarea: demostrar que MarketState/Lifecycle/Setup Builder solo producen estados
  y setups temporalmente posibles, causalmente ordenados, gobernados por su TF de
  autoridad y bloqueados cuando el contexto no autoriza uso.
- REGLA DE ORO aplicada: el "análisis ChatGPT H6–H9 / 318 tests" se contrastó contra
  código/bitácora. Resultado: ese texto es EN GRAN PARTE FICTICIO respecto al repo
  (nuestra auditoría real fue H1–H5; 318 no coincide con 313+5). Tres de sus 4
  "fallas" ya estaban CUBIERTAS; una (H7) era hueco real; dos más (H9 flag, H6 en
  Setup Builder) eran huecos reales no mencionados correctamente.

## [AUDITORÍA RED TEAM — segunda pasada, OE-10/OE-11]
Ejecutada por Hermes como CRO/auditor tras el cierre de dcce141. La autoauditoría
del commit original era INCOMPLETA: encontré un hueco real en OE-02 (Tesis §6
ítems 2 y 3) que el commit NO cubría.

- HALLAZGO R1 (OE-02): `classify_eligibility` validaba POI≤refinement≤confirmation
  (H6) pero EXCLUÍA el trigger. El comentario justificaba excluirlo porque el
  DISPLACEMENT "crea la estructura y puede preceder al POI" — CIERTO para el
  nacimiento, pero la Tesis §6 exige intentar ROMPER con (a) trigger anterior al
  refinement y (b) trigger posterior a decision_time. El motor no tenía defensa ni
  test para (b): un trigger con tiempo operativo DESPUÉS del refinement quedaba
  ELIGIBLE. Propiedad causal sin cubrir.
- CORRECCIÓN R1: añadida guarda en `classify_eligibility` (setup_builder.py) que
  bloquea cuando `trigger` existe y su tiempo operativo es posterior al de
  `refinement` (límite estructural disponible; Setup no lleva decision_time).
- TESTS R1: 2 adversariales nuevos — `test_H6_trigger_anterior_al_refinement_permitido`
  (ítem 2: trigger previo es válido, no bloquea) y `test_H6_trigger_posterior_al_refinement_bloqueado`
  (ítem 3: trigger posterior al refinement => BLOCKED).
- VERIFICACIÓN R1: `pytest tests/test_integridad_causal_h6_h9.py` 18 passed;
  `pytest tests/` completo **336 passed, 0 failed** (era 334 antes de R1; +2, 0 regresiones).
- CORRECCIÓN DOC: el conteo "328" en §[VERIFICACIÓN FINAL] y SDD §5 estaba MAL; el
  baseline real previo era 318 (commit 677e53b declara 313+5). Se corrige a 318.
  318 + 16 (archivo original) + 2 (R1) = 336 cuadra.
- OE-11: `graphify update .` regenerado (10689 nodos / 17307 edges, graphify-out/
  gitignored por diseño, no se commitea). Worktree tiene 16 archivos sucios AJENOS
  a H6-H9 (.atl/, data/raw/, reports/charts/, briefs, demo, .codex/) — outputs de
  otros runs; fuera de alcance de esta tesis, no se tocan.
- Veredicto RED TEAM: 0 BLOCKER abiertos tras R1. OE-10 = PASS, OE-11 = PASS.

## [HALLAZGOS REALES — lo que la fase encontró y cerró]
1. **H7 (OE-03):** `MarketState.advance_bar` aceptaba velas fuera de orden.
   Corregido: guarda fail-closed `OUT_OF_ORDER` por reloj de TF + `out_of_order_events()`.
2. **OE-07:** `relate_fvg_ob` comparaba `bar_index` entre TF distintas (basura cross-TF).
   Corregido: `_causal_precedes` ordena por `confirmation_time` en cross-TF, por
   `bar_index` en misma TF.
3. **H9 (OE-05):** `classify_eligibility` devolvía ELIGIBLE con `aligned=False`.
   Corregido: `_htf_aligned` respeta `aligned=False` explícito; ausente => alineado
   (no rompe contrato previo de sesgo por cadena).
4. **H6 (OE-02):** `classify_eligibility` no validaba confirmation(BOS) anterior al POI.
   Corregido: guarda `confirmation_time >= poi.confirmation_time`. El trigger
   (DISPLACEMENT) se excluye porque es el impulso que CREA la estructura (precede al POI).
5. **H8 (OE-04):** `observe_lower_tf` aceptaba `observed_tf == origin_tf`.
   Corregido: jerarquía `_TF_RANK`; solo TF ESTRICTAMENTE inferior observa.

## [CAMBIOS]
- engine/market_state.py: `__init__` lleva `_last_seen`/`_out_of_order_events`;
  `advance_bar` guarda OUT_OF_ORDER; helpers `_is_out_of_order`/`_update_last_seen`/`out_of_order_events`.
- engine/relations.py: imports datetime; `_as_time`/`_causal_precedes`; strict mode
  usa reloj correcto (misma TF bar_index, cross-TF timestamp).
- engine/lifecycle.py: `_TF_RANK`/`_tf_rank`/`_is_strictly_lower_tf`; guarda H8 en `observe_lower_tf`.
- engine/setup_builder.py: `_obj_time`; `_ctx_aligned` (ausente=>True); `_htf_aligned`
  respeta `aligned=False`; guarda H6 en `classify_eligibility`.
- tests/test_integridad_causal_h6_h9.py: 16 tests adversariales (OE-02,03,04,05,06,07,08,10).
- docs/planificacion/SDD_FASE_H6_H9_INTEGRIDAD_CAUSAL.md: SDD de la fase.

## [VERIFICACIÓN FINAL]
- `pytest tests/test_integridad_causal_h6_h9.py` → 16 passed.
- `pytest tests/` completo → **334 passed, 0 failed** (era 318 antes de la fase;
  +16 nuevos, 0 regresiones). Nota: el texto externo decía "318 tests" — es
  inventado; el conteo real del repo era 318 y ahora 334. (Tras auditoría RED TEAM
  R1: 336 passed, 0 failed.)
- Graphify: `graphify update .` en curso (OE-11) para reflejar HEAD 677e53b.

## [AUTOAUDITORÍA RED TEAM — OE-10]
Revisados manualmente: lookahead (projection_at congelado, OK), serialización
(round-trip JSON de lifecycle verificado en ciclo previo), FULL/PREFIX (test
OE-08), determinismo (test OE-10), lifecycle terminal (test OE-06), separación de
vidas HTF/LTF (test OE-10). 0 defectos BLOCKER abiertos.

## [MATRIZ DE ENTREGA — OE-12] (actualizada tras auditoría RED TEAM R1)
```text
OE-01 Contrato temporal       PASS
OE-02 H6 causalidad           PASS  (incluye cierre hueco trigger-order R1)
OE-03 H7 orden temporal       PASS
OE-04 H8 autoridad MTF        PASS
OE-05 H9 elegibilidad         PASS
OE-06 Lifecycle              PASS
OE-07 Relaciones MTF         PASS
OE-08 FULL/PREFIX            PASS
OE-09 Adversarial            PASS  (18 ítems Tesis §6 cubiertos, +2 R1)
OE-10 Autoauditoría          PASS  (RED TEAM encontró y cerró R1)
OE-11 Reproducibilidad       PASS  (graphify regenerado; suite 336 passed)
OE-12 Certificación          PASS (sujeto a GO de Ruben/auditor)

BLOCKERS: 0   CRITICAL: 0
OBJETIVO GENERAL: ACHIEVED (por evidencia reproducible)
EPISODES/FUNNEL: DESBLOQUEADO (tras GO de Ruben/auditor)
```

## [VEREDICTO FINAL — TESIS H6–H9]
Demostrado por evidencia (no por conteo): MarketState, Lifecycle y Setup Builder
construyen únicamente estados/setups temporalmente posibles, causalmente ordenados,
gobernados por su TF de autoridad y bloqueados cuando el contexto no autoriza uso.
La segunda pasada RED TEAM encontró y cerró un hueco real (trigger-order) que la
primera autoauditoría había dejado abierto. Suite completa **336 passed, 0 failed**,
reproducible y sin xfail ocultos.

NO me autoproclamo CERTIFIED en sentido fuerte: conforme a AGENTS.md y a la Tesis §9,
el GO final es de Ruben/auditor sobre los gates. Commit local pendiente de firma de
Ruben; sin push. (Nota: en ICT SYSTEM Ruben ha solicitado push en entregas; lo haré
solo con su GO explícito tras su revisión punto por punto.)

## [CIERRE DEFINITIVO TESIS 1 — R2, OE-01..OE-15]

Ejecutado autónomamente bajo PROTOCOLO DE EJECUCIÓN AUTÓNOMA POR OBJETIVOS.
La Tesis 1 (certificación de integridad causal H6–H9) quedó dividida en OE1–OE15;
cada OE se autoevaluó con gate binario y se documenta abajo.

### OE-01 — Congelar contrato causal (PASS)
Ley congelada: `t_POI <= t_REFINEMENT <= t_CONFIRMATION <= t_TRIGGER <= t_DECISION`,
con POI=OB, refinement=FVG, confirmation=BOS, trigger=DISPLACEMENT. Registrada en
SDD §4b. Defecto semántico de R1 corregido: el trigger NO puede preceder a
confirmation (el "trigger crea la estructura" no exime el orden temporal real).

### OE-02 / OE-03 — Cerrar H6 (PASS)
`classify_eligibility` valida las 3 inversiones (POI>refinement, refinement>confirmation,
confirmation>trigger) por tiempo operativo, no bar_index cross-TF. Tests:
`test_H6_confirmation_anterior_al_refinement_bloqueado`,
`test_H6_trigger_anterior_al_confirmation_bloqueado`,
`test_H6_trigger_anterior_al_refinement_bloqueado`,
`test_H6_confirmation_anterior_al_poi_bloquea_setup` (original).

### OE-04 — Cerrar H7 (PASS, ver FASE 1 dcce141 + R2 OE-05)
OUT_OF_ORDER fail-closed por reloj de TF ya existente; R2 lo hace persistente.

### OE-05 / OE-11 — SAVE/LOAD equivalente (PASS)
HALLAZGO R2-A: `MarketState.to_dict` NO serializaba `_last_seen` ni
`_out_of_order_events` => el restaurado olvidaba hasta qué instante vivió y aceptaba
velas que el original rechazaba (comportamiento no equivalente). CORRECCIÓN:
`to_dict`/`from_dict` persisten ambos. Test `test_OE11_save_load_conserva_reloj_out_of_order`
demuestra que el restaurado rechaza la misma vela fuera de orden que el original.

### OE-06 — Lifecycle terminal (PASS, ver dcce141)
`test_OE06_objeto_terminal_no_resucita` cubre.

### OE-07 — Relaciones cross-TF (PASS, ver dcce141)
`relate_fvg_ob` usa timestamps cross-TF, bar_index misma TF.

### OE-08 — FULL vs PREFIX (PASS)
`test_OE08_full_vs_prefix_identico_en_T`.

### OE-09 — Pruebas adversariales (PASS)
18 ítems Tesis §6 cubiertos + 4 nuevos R2 (3 H6 + 1 OE-11).

### OE-10 / OE-12 — Autoauditoría RED TEAM (PASS)
Encontré y cerré 2 defectos reales: (a) semántica trigger al revés en R1;
(b) H7 no persistente (R2-A). Ambos corregidos con test permanente.

### OE-13 / OE-14 — Reproducibilidad + cierre técnico (PASS)
Suite completa **338 passed, 0 failed**, sin xfail ocultos; graphify-out regenerado;
SDD y bitácora reconciliados.

### OE-15 — Autoevaluación final (PASS)
MATRIZ:
  OE-01 PASS  OE-02 PASS  OE-03 PASS  OE-04 PASS  OE-05 PASS
  OE-06 PASS  OE-07 PASS  OE-08 PASS  OE-09 PASS  OE-10 PASS
  OE-11 PASS  OE-12 PASS  OE-13 PASS  OE-14 PASS  OE-15 PASS
  BLOCKERS: 0  CRITICAL: 0
  SUITE: 338 passed / 0 failed

OBJETIVO GENERAL TESIS 1: ACHIEVED (por evidencia reproducible).
Episodes/Funnel (TESIS 2): DESBLOQUEADO, pendiente de GO de Ruben/auditor.

RIESGO RESIDUAL:
- `decision_time` no existe en `Setup`; la cota superior del trigger se valida contra
  `confirmation` (suficiente mientras no haya ejecución posterior). Si Tesis 2 introduce
  decision_time, la guarda debe extenderse a `t_TRIGGER <= t_DECISION`.
- `_TF_RANK` local a lifecycle; extender si se adoptan M3/W1 (ya anotado en dcce141).
- `first_touch_bar` vs `tradable_bar`: evaluate puede producir first_touch < tradable
  vivo que luego no pasa la validación de MarketObject al restaurar. No afecta H6/H7
  pero es deuda a auditar en lifecycle (fuera de alcance de esta tesis).

```


## [DECLARACIÓN PARA AUDITOR INDEPENDIENTE]
Los 5 defectos reales están corregidos y cubiertos por tests permanentes. No
declaro CERTIFIED autónomamente: requiere GO de Codex/auditor sobre gates de
reproducibilidad/riesgo (AGENTS.md). Sin push (regla repo). Commit local
selectivo pendiente de firma de Ruben.

## [RIESGO RESIDUAL]
- `relate_fvg_ob` en cross-TF requiere `candidate_time`/`confirmation_time` en
  ambos objetos; si faltan timestamps en cross-TF, la relación se rechaza (no se
  inventa) — aceptable fail-closed.
- La jerarquía `_TF_RANK` es local a lifecycle; si el repo adopta nuevas TF
  (ej M3, W1) debe extenderse. M3 ya existe en scripts de datos pero no en el
  motor; no afecta hoy.
