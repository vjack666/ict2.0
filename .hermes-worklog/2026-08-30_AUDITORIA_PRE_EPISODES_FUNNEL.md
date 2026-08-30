# Bitácora — Auditoría previa a Episodes / Funnel v1

**Fecha:** 2026-08-30
**Agente:** Codex
**Departamentos:** D1 Documentación, D2 Ingeniería, D5 Assurance
**Estado:** COMPLETED — auditoría base y documentos preparados; implementación de Episodes pendiente.

## Alcance

Se auditó la cadena posterior a A7:

```text
MarketObject → Lifecycle → MarketState → Setup Builder → Episodes/Funnel
```

El checkout operativo está en `C:\Users\v_jac\Desktop\ICT SYSTEM`, rama
`codex/audit-hermes-cert-20260826`, con HEAD `1757793` publicado y árbol limpio.
El trabajo local anterior permanece recuperable en el stash
`pre-episodes-funnel-local-generated-work-2026-08-30`.

## Evidencia de la capa previa

- Graphify localizó `engine/lifecycle.py`, `engine/market_state.py`,
  `engine/setup_builder.py`, sus tests y el SDD padre.
- Las suites focales de Lifecycle, MarketState, Setup Builder y contrato de
  MarketObject ejecutaron **94 passed**.
- No existe `engine/episodes.py` canónico en la rama operativa.
- El código de Episodes/Funnel no debe deducirse de históricos de `backtest/` ni
  de `.hermes-cert/`.

## Hallazgos

1. La capa previa está disponible como entrada de Episodes, pero no debe ser
   reimplementada.
2. Faltaba un contrato específico para definir identidad, deduplicación,
   rechazos, lineage, tiempos y FULL/PREFIX de Episodes.
3. Faltaba un SDD vigente y un plan ejecutable que obligara a Hermes a crear y
   resolver subtareas técnicas automáticamente.
4. La agrupación v1 debe ser conservadora: un Setup canónico es un Episode; no
   se fusionan setups distintos sin un contrato posterior.

## Entregables preparados

- `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`
- `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md`
- `.hermes/plans/2026-08-30_EPISODES_FUNNEL_V1.md`
- actualizaciones de `docs/INDICE_AUTORIDAD.md`, `docs/00_HERMES_START_HERE.md`,
  `.hermes-index.md` y el SDD padre.

## Decisión

La fase queda **READY_FOR_EXECUTION**, no `COMPLETED`: el contrato y SDD están
preparados, pero T1.7 requiere revisión independiente D5 antes de crear código.
La siguiente acción es ejecutar T1.7 y, si pasa, comenzar T2 bajo el write set
cerrado.
