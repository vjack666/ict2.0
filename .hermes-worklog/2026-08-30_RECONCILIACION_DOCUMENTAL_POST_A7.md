# Bitácora — Reconciliación documental post-A7

**Fecha:** 2026-08-30
**Agente:** Codex
**Departamento:** D1 Documentación/PMO + D2 Ingeniería + D5 Assurance
**Tarea:** Auditar y consolidar la documentación de Hermes y Codex para la
misión Lifecycle → MarketState → Setup Builder → Episodes/Funnel.
**Estado:** COMPLETED — reconciliación documental; no certifica edge ni producción.

## Auditoría realizada

- Checkout: `C:\Users\v_jac\Desktop\ICT SYSTEM`.
- Rama: `codex/audit-hermes-cert-20260826`.
- HEAD observado: `45783f9`.
- Worktree ya estaba sucio por cambios ajenos y artefactos; no se tocaron ni se
  limpiaron esos archivos.
- Graphify confirmó las relaciones entre `MarketObject`, `lifecycle.py`,
  `market_state.py`, `setup_builder.py`, tests y documentación.
- La documentación anterior tenía dos líneas mezcladas: un SDD v1.2 de la rama
  del visor `codex/visual-replay-wyckoff-v1-1` y la implementación real posterior
  en `engine/`.

## Hallazgo principal

El código canónico ya contiene Lifecycle, MarketState y Setup Builder, pero el
SDD específico que los unía no estaba presente en la rama operativa. El worklog
de PASO 3 lo citaba como creado, pero la ruta no existía en el checkout actual.
Además, la semántica del SDD histórico de `backtest/` permitía una observación
LTF que no coincide con el contrato vigente de autoridad `authority_tf ==
lifecycle_tf == origin_tf` del motor.

## Corrección documental

Se creó el SDD canónico:

`docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`

Este documento:

- fija autoridad y precedencia;
- separa `origin_tf`, `authority_tf`, `lifecycle_tf` y observación LTF;
- define Lifecycle, MarketState, Setup Builder y FULL/PREFIX;
- reconoce el estado implementado real;
- prohíbe segundo motor/FSM, edge, IA y producción;
- prepara Episodes/Funnel sin crear código prematuramente.

También se creó el plan operativo:

`.hermes/plans/2026-08-30_POST_A7_ENGINE_STATE_EPISODES.md`

Y se alinean `.hermes-index.md` y `docs/00_HERMES_START_HERE.md` para que Hermes
encuentre el SDD y el plan antes de recibir una misión de esta capa.

## Verificación prevista para el cierre

- revisar referencias a las nuevas rutas;
- `git diff --check`;
- confirmar que el SDD histórico no se declara autoridad de `engine/`;
- ejecutar Graphify update para mantener el mapa navegable;
- no ejecutar experimentos ni modificar datasets.

## Riesgos y siguiente acción

El siguiente riesgo no es de documentación sino de certificación: la evidencia
FULL/PREFIX debe cubrir el `MarketState` completo en varias decisiones T. La
siguiente misión autorizable es redactar el contrato y SDD específicos de
Episodes/Funnel; no implementar todavía `engine/episodes.py`.
