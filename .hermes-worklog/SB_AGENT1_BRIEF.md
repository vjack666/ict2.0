# Agente 1 — Setup Builder: MODELO DE DATOS (SDD §13.2)

ROL: D2 Ingeniería. WORKTREE: C:/Users/v_jac/Desktop/ICT_SYSTEM_wt_model (branch feature/sb-model)

OBJETIVO: Crear la entidad `Setup` y `SetupEligibility` en `engine/setup_builder.py`.
NO implementes la lógica de composición (eso lo hacen otros agentes). Solo el modelo.

ENTREGA:
1. `engine/setup_builder.py` con:
   - `class SetupEligibility(str, Enum)`: ELIGIBLE / BLOCKED / OUT_OF_CONTEXT / SUPERSEDED
   - `class Setup`: dataclass con campos:
       id, symbol, direction (1/-1/0),
       context_htf (Optional[MarketObject]),
       poi (Optional[MarketObject]),
       refinement (Optional[MarketObject]),
       confirmation (Optional[MarketObject]),
       trigger (Optional[MarketObject]),
       eligibility (SetupEligibility),
       reason (str),
       created_at (Any),
       used_by_setup lineage (list[str] en meta del POI, NO en Setup)
   - `to_dict()` y `from_dict()` (JSON-safe, con _normalize_meta estilo market_object).
2. `tests/test_setup_builder_model.py` (tests unitarios del modelo, sin lógica de composición).

REGLAS:
- NO importes backtest/. NO modifiques lifecycle.py ni market_state.py.
- Usa `from engine.market_object import MarketObject`.
- El Setup NO altera object_state de ningún objeto.
- CERO mutación de MarketObject; solo lectura.

VERIFICACIÓN:
- `C:/Python314/python.exe -m pytest tests/test_setup_builder_model.py -q` → 0 fallos.
- Lint ok.

AL CERRAR: commit local selectivo en feature/sb-model, bitácora breve en .hermes-worklog/, NO push.
Devuelve: STATUS, ARCHIVOS, EVIDENCIA (pytest output), RIESGOS.
