# Bitácora — Plan/SDD LTF y conexión al motor diario

**Fecha:** 2026-08-20
**Estado:** LECTURA LTF IMPLEMENTADA / EJECUCIÓN FUERA DE ALCANCE

## Hallazgo

No existía un plan ni un SDD dedicado a LTF. El README referenciaba
`docs/tesis/SDD_LTF_ENTRY_LAYER.md`, pero `docs/tesis/` no estaba presente.
Las piezas existentes estaban repartidas entre `engine/plan.py`,
`engine/sequence.py`, `engine/plan_driver.py`, el SDD MTF/AHF y el brief diario.

## Cambios

- Creado `docs/tesis/PLAN_LTF_ENTRY_LAYER.md`.
- Creado `docs/tesis/SDD_LTF_ENTRY_LAYER.md`.
- Creado `engine/daily_motor.py` con perfil D1→H4→H1→M15.
- Conectado `scripts/brief_lunes.py` al snapshot LTF closed-only.
- Eliminadas referencias operativas a OTE del brief diario.
- Añadidos tests de observación, ausencia de orden y no-look-ahead.
- Actualizados `docs/INDICE_AUTORIDAD.md` y `.hermes-index.md`.

## Política

El adaptador solo reporta contexto, estructura LTF, zona, retest y razón de
espera. `entry_authorized` es siempre `false`; `SETUP_READY` no se transforma
en orden. Entry/SL/TP, fill, sizing y gestión de posición quedan fuera de este
alcance.

## Pendientes

- Validar el brief con feeds recientes y todos los símbolos soportados.
- Profundizar la lectura secuencial/retest sin duplicar la FSM.
- Resolver datos reproducibles M5/M1 antes de ampliar la lectura a scalping.
