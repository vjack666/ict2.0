# Bitácora — Apertura del puente de estado operativo MT5 v1

**Fecha:** 2026-08-31
**Agente:** Codex — CEO operativo
**Departamentos:** D2, D4, D5, D1 y D7
**STATUS:** READY — preflight documental completado; implementación pendiente

## Decisión

Después del cierre técnico de Episodes/Funnel, la siguiente etapa será la
lectura operativa local desde MT5. Dukascopy no se usa en esta misión: queda
como evidencia histórica/fixure y no se descarga, modifica ni mezcla.

## Evidencia de entrada

- `scripts/daily/update_mt5_ict.py` ya actualiza parquet local.
- `scripts/daily/brief_lunes.py` ya exige frescura y excluye velas abiertas.
- `engine/ltf_canonical_feed.py` ya ensambla FVG/OB/relations/Sequence.
- `engine/Wyckoff/` ya entrega lectura subordinada y read-only.
- `engine/market_state.py` ya conserva historial event-sourced de objetos.
- `engine/mtf_navigation.py` ya entrega Context State multinivel.
- Suite completa: `392 passed in 22.45s`.
- `py_compile`: PASS; imports de ambas capas: PASS; worktree inicial: limpio.

## Hallazgo principal

Existen dos clases llamadas `MarketState` con responsabilidades diferentes:
Context State de navegación y Object MarketState histórico. No es un error que
existan; sería un error mezclarlas o crear una tercera autoridad. El contrato
nuevo exige nombrar la frontera explícitamente.

## Archivos nuevos

- `docs/contratos/CONTRATO_MT5_OPERATIONAL_SNAPSHOT_V1.md`
- `docs/planificacion/SDD_MT5_OPERATIONAL_STATE_BRIDGE_V1.md`
- `.hermes/plans/2026-08-31_MT5_OPERATIONAL_STATE_BRIDGE_V1.md`

## Riesgos

- El brief actual aún no materializa un Object MarketState completo a partir de
  todos los objetos MT5; eso es M2, no se debe declarar resuelto ahora.
- Frescura de MT5 depende de la terminal local; si falla, el brief debe quedar
  bloqueado.
- Este gate no prueba edge ni autoriza trading.

## Siguiente acción

Implementar M2 únicamente después de revisar el contrato y conservar el write
set acordado; luego ejecutar M3 causalidad/determinismo y auditoría independiente.
