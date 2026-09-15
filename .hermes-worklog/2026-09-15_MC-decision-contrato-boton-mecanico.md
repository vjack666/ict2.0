# Bitácora MC-20260915-000000-decision-contrato-boton-mecanico

**Inicio:** 2026-09-15
**Responsable:** nexus (planificación)
**Objetivo:** preparar la decisión de contrato operativo para el botón del bot mecánico.
**Producción:** docs/planificacion/DECISION_CONTRATO_OPERATIVO_BOTON_MECANICO_V1.md
**Estado al cierre:** listo para decisión del usuario.

## Qué se hizo

- Localizó y leyó los cuatro documentos de autoridad: SDD_MECHANICAL_MT5_BOT.md, SDD_DESKTOP_TERMINAL.md, CONTRATO_POI_STOCH_M15_V2.md, SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md.
- Verificó estado del repo y existencia de docs/planificacion/.
- Convirtió los dos caminos en criterios comparables con implicaciones de código, tests, UI y autoridad.

## Qué se encontró

- Camino A: es compatible con CONTRATO_POI_STOCH_M15_V2.md §11, pero incompatible con SDD_MECHANICAL_MT5_BOT.md §Entrada y SDD_DESKTOP_TERMINAL.md §Addendum V3 si no se modifica el muro de probability>=0.70 + confirmed.
- Camino B: es el que conserva los contratos actuales intactos; exige Fase 2B con preregistro, auditoría D5, gates de datos/calibración/edge.

## Riesgo controlado

- No se activaron órdenes.
- No se reinició servicio.
- No se decidió por el usuario.
- No se modificó código ni tests; solo se escribió criterio.

## Siguiente acción

Usuario decide Camino A o Camino B y, si A, define límites DEMO y alcance de commit selectivo.
