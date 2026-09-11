# Productor mecánico de señal — Fase 2A

**Estado:** IMPLEMENTED_DIAGNOSTIC_ONLY
**Departamento:** D2 ingeniería diaria; evidencia para D5.
**Alcance:** EURUSD, snapshot canónico MT5, sin publicación de señal operable.

## Resultado

Se añadió `engine.mechanical_signal_assessment.assess_mechanical_signal`, un
evaluador puro que recibe el snapshot canónico ya recortado a `decision_time`.
Congela la secuencia H4/H1 → M15 sweep → displacement → BOS/CHOCH → FVG/OB →
retest y siempre devuelve `BLOCKED`, `NO_SIGNAL` o `CANDIDATE_SETUP`.

La evidencia de sweep no existía como artefacto canónico. Por diseño, la
ausencia queda como `SWEEP_EVIDENCE_UNAVAILABLE`; no se infiere de zonas o de
contexto. El snapshot live observado tenía H4 bajista y H1 mixto, por lo que
la primera respuesta aplicable es `HTF_CONFLICT`.

## Fronteras preservadas

- `can_trade=false` y `entry_authorized=false` en cada salida.
- Sin `BUY`/`SELL`, probabilidad, `confirmed`, SL, TP, orden ni ciclo nuevo.
- `latest_snapshot.json` no recibe la evaluación; el publicador existente la
  elimina si no existe un contrato operable completo.
- M5/M1 y estocástico M15 continúan separados del productor diagnóstico.

## Evidencia

- `tests/test_mechanical_signal_assessment.py`: fixtures para los cinco
  rechazos de la cadena, HTF, M15 ausente, evidencia sweep ausente, candidato
  diagnóstico e igualdad FULL/PREFIX.
- `tests/test_mt5_operational_snapshot.py`: la evaluación conserva las
  invariantes observacionales dentro del ensamblador.
- `tests/test_desktop_terminal.py`: el terminal proyecta la evaluación sin
  fabricar snapshot mecánico.
- Caja negra: `SIGNAL_ASSESSMENT` conserva resultado, hash del snapshot,
  fuente y tiempo de decisión una vez por actualización del motor.

## Verificación

`python -m pytest tests/test_mechanical_signal_assessment.py tests/test_mt5_operational_snapshot.py tests/test_desktop_terminal.py tests/test_mechanical_bot_service.py -q` → 65 PASS.

## Riesgo y siguiente acción

No existe todavía un productor causal de `m15_evidence.sweep`; crear uno exige
contrato/fixture causal propio antes de que un candidato live pueda ocurrir.
Fase 2B continúa bloqueada por calibración, costes/fill, procedencia y edge;
ningún resultado de esta fase la sustituye.
