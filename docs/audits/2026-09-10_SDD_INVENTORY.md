# Inventario de SDD y contratos — 2026-09-10

## SDD completados hoy

1. `docs/audits/2026-09-10_RULES_CONFLICT_AUDIT.md` — auditoría y dictamen.
2. `docs/tesis/SDD_RULES_ARBITRATION_V1.md` — precedencia, estados y autoridad.
3. `docs/tesis/SDD_ICT_WYCKOFF_READING_V1.md` — lectura por temporalidad y contratendencia.
4. `docs/tesis/SDD_MECHANICAL_MT5_BOT.md` — actualizado al flujo manual, sesiones y riesgo 3%.
5. `docs/tesis/SDD_DESKTOP_TERMINAL.md` — addendum de controles, conflictos y FVG.

## Documentos que siguen siendo referencias

`SDD_LTF_ENTRY_LAYER.md`, `PLAN_LTF_ENTRY_LAYER.md`, `SDD_SEQUENCE_EVENT_WAIT.md`,
`CONTRATO_CONTEXT_STATE.md`, `CONTRATO_MT5_OPERATIONAL_SNAPSHOT_V1.md`,
`CONTRATO_MULTI_TF_LAYERS.md`, `CONTRATO_MTF_NAVIGATION_GRAPH.md`, los rulebooks
ICT/Wyckoff y las tesis históricas de intradía/scalping. No se reescriben como
reglas runtime; se enlazan desde los SDD nuevos.

## Faltantes para declarar cierre completo del sistema

- Validar polaridad de eventos antes de clasificar `COUNTERTREND`: COMPLETADO en `engine/Wyckoff/classifier.py` con pruebas.
- Probar internamente que el builder excluye siempre la vela MT5 abierta: COMPLETADO en `tests/test_desktop_terminal.py`.
- Añadir tests de `manual_direction`, `LONDON_SELL_ONLY` y espera estocástica: COMPLETADO.
- Alinear el snapshot y la UI para separar contexto de autorización manual.
- Ejecutar revisión independiente D5 y commit selectivo; no hacer push.

## Dictamen

Los SDD escritos o completados el 2026-09-10 tienen objetivo, no objetivos,
autoridades, estados, parámetros, evidencia, riesgos y criterios de verificación.
La verificación focal del conjunto actualizado es `50 passed`. El sistema completo
mantiene `can_trade=false` y no se declara certificado de edge ni de producción;
esa separación es un límite del SDD, no un faltante documental.
