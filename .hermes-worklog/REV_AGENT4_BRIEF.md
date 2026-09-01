# Agente 4 — Documentación y reconciliación (Codex H5)

ROL: D1 PMO / COO. WORKTREE: C:/Users/v_jac/Desktop/ICT_REV_docs (branch feature/rev-docs, basado en feature/rev-sb integrado)
Write set exclusivo: .hermes-worklog/2026-08-28_SETUP_BUILDER_PLAN.md, docs/INDICE_AUTORIDAD.md, docs/planificacion/SDD_FVG_OB_ENGINE.md
NO tocar: data/, reports/charts/, briefs/, ni ningún archivo sucio no relacionado.

CONTEXTO (verificado): los patches previos que marcaban Setup Builder como "pendiente" en INDICE_AUTORIDAD.md y la §13 en SDD_FVG_OB_ENGINE.md NO persistieron (el archivo actual no tiene esas secciones). Ese es el desfase H5.

TAREA:
1. En docs/planificacion/SDD_FVG_OB_ENGINE.md: añadir sección "## 13. Setup Builder (capa de composición)" al FINAL del archivo documentando el diseño REAL ya implementado y verificado:
   - Objeto `Setup` (engine/setup_builder.py) con componentes context_htf → poi (ORDER_BLOCK) → refinement (FVG) → confirmation (BOS) → trigger (DISPLACEMENT).
   - `setup_eligibility` (SetupEligibility: ELIGIBLE/BLOCKED/OUT_OF_CONTEXT/SUPERSEDED) SEPARADO de `object_state` (un POI ACTIVE puede dar setup BLOCKED si contexto HTF no alineado).
   - `classify_eligibility(setup, ctx, require_complete=...)`: ELIGIBLE solo si ctx HTF alineado con direction Y poi+refinement+confirmation+trigger presentes y activos; BLOCKED si falta confirmation/trigger (require_complete=True) o dirección no alineada; SUPERSEDED si POI INVALIDATED; OUT_OF_CONTEXT si ctx None.
   - `build_setups_at(ms, T, ctx)` consume `ms.projection_at(T)` (snapshot histórico, SIN look-ahead), NO `ms.active()` del presente.
   - Role.CONFIRMATION/TRIGGER añadidos a la enum Role (market_object.py).
   - NO afirmar CERTIFIED: estado = PROMOVIDO TRAS REVISIÓN (Codex NEEDS REVISION H1-H4 cerrados; certificación pendiente de gates).
2. En docs/INDICE_AUTORIDAD.md: añadir entrada en la sección de motor/arquitectura: "Capa de composición (Lifecycle → Market State → Setup Builder)" con estado "PROMOVIDO CON REVISIÓN 2026-08-28 (H1-H4 cerrados; sin CERTIFIED)".
3. En .hermes-worklog/2026-08-28_SETUP_BUILDER_PLAN.md: añadir sección "[REVISIÓN CODEX H1-H5]" documentando los 5 hallazgos, qué se corrigió, evidencia (313 passed + 5 pruebas negativas del auditor), y que NO se declara CERTIFIED hasta GO del auditor.

NO borrar ni sobrescribir cambios sucios de otros archivos. Solo editar los 3 archivos del write set.

No ejecutar tests (es documentación). Commit local selectivo, NO push. Devolver status/archivos/evidencia/riesgos.
