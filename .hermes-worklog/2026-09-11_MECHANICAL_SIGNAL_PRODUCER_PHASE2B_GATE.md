# Productor mecánico de señal — Fase 2B, gate de publicación

**Estado:** IMPLEMENTED_GATE / PUBLICATION_BLOCKED
**Departamento:** D2 ingeniería diaria; D4/D5 son autoridad de evidencia.
**Modo de procedencia:** AUDIT_ONLY.

## Resultado

Se implementó `engine.mechanical_signal_publication.evaluate_publication_gate`.
No entrena ni calcula una probabilidad: valida un certificado externo y
reproducible antes de devolver el único contrato atómico posible de Fase 2B.

El único mapeo direccional permitido es
`CANDIDATE_CONTEXT_DIRECTION_V1`: BULLISH→BUY, BEARISH→SELL. `confirmed` se
define como cadena Fase 2A completa con velas M15 cerradas; el estocástico no
forma parte de esa definición y permanece como recheck del bot.

## Gates obligatorios

`direction_rule`, `confirmation`, `calibration`, `abstention_ood`,
`costs_fill`, `causality`, `provenance`, `edge`,
`production_authorization` deben ser exactamente `PASS`. La calibración exige
VALIDATION-only, HOLDOUT no usado para fit, Brier y hash de curva de
fiabilidad. Cualquier ausencia devuelve `BLOCKED` sin dirección, probabilidad,
archivo de snapshot ni autoridad de trading.

## Estado real auditado

El preregistro `EXP-PASS-EDGE-INTRADIA-01` conserva `DRAFT_BLOCKED / NO
EJECUTAR`: `UNIT_IDENTITY`, fill, costes, horizonte, PIT/FULL-PREFIX,
potencia/estabilidad, provenance, reproducibilidad y autorización no están
todos en `PASS`. El contrato de edge confirma que la evaluación IA existente
no es un `net_R` económico y que el checkout sucio tampoco permite una
certificación confirmatoria. Por eso el gate no se conecta al publicador.

## Verificación

`python -m pytest tests/test_mechanical_signal_publication.py tests/test_mechanical_signal_assessment.py tests/test_mt5_operational_snapshot.py tests/test_desktop_terminal.py tests/test_mechanical_bot_service.py -q` → 70 PASS.

## Siguiente acción

Completar el preregistro y la evidencia D4/D5 de datos, costes/fill, causalidad,
calibración OOS y edge antes de suministrar un certificado. Solo entonces se
podrá evaluar el contrato de publicación, y el bot seguirá revalidando sus
cuatro gates finales.
