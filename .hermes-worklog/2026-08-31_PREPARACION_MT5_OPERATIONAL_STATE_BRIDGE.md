# Bitácora — Apertura del puente de estado operativo MT5 v1

**Fecha:** 2026-08-31
**Agente:** Codex — CEO operativo
**Departamentos:** D2, D4, D5, D1 y D7
**STATUS:** COMPLETED — ensamblaje y aceptación operativa local verificados; auditoría independiente/publicación pendiente

## Decisión

Después del cierre técnico de Episodes/Funnel, la siguiente etapa será la
lectura operativa local desde MT5. Dukascopy no se usa en esta misión: queda
como evidencia histórica/fixure y no se descarga, modifica ni mezcla.

La arquitectura conserva dos planos: Dukascopy histórico para investigación,
funnel, análisis, backtest y tests generales; MT5 local para actualizar la
punta actual y alimentar la lectura operativa. MT5 será la fuente de una futura
capa de envío de órdenes, pero ese envío requiere otro contrato y no queda
activado por este puente de observación.

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

## Implementación y evidencia

- `engine/ltf_canonical_feed.py` expone `build_canonical_objects` y conserva
  detectores/relaciones como autoridades únicas.
- `engine/mt5_operational_snapshot.py` ensambla Context State, Object
  MarketState event-sourced, canonical feed, Wyckoff y daily motor.
- `scripts/daily/brief_lunes.py` consume el snapshot único y muestra su estado,
  conteo de objetos, TF faltantes y provenance.
- Pruebas focales: `11 passed`.
- Suite completa final: `399 passed in 37.58s`.
- Compilación: `py_compile=PASS`.
- Integración final con parquet MT5 local tras refresco real: `READY`,
  `provenance=PASS`, 6 hashes/artefactos hasheados, 3418 objetos históricos,
  JSON serializable y `OBSERVE_ONLY_NO_ORDER`.
- La integración se conectó al brief diario; el commit del generador se toma
  localmente con `git rev-parse HEAD` y los hashes se calculan sobre los bytes
  de cada parquet suministrado.
- Auditoría independiente: `audits/codigo/mt5_operational_snapshot.py` produjo
  `reports/audits/operational/mt5_operational_snapshot_audit_20260831.json`.
  Resultado técnico `PASS`: ASSEMBLY, POLICY, FULL_PREFIX, AUTHORITY_AND_PIT,
  SERIALIZATION, BOUNDARY y PROVENANCE.
- El gate operativo del brief ejecutó refresco MT5 local `OK=6/6` y confirmó que
  D1/H4/H1/M15/M5/M1 alcanzaban su último cierre requerido. El brief EURUSD se
  escribió en 146.0 s; su snapshot quedó `READY`, con `TF faltantes=[]` y
  `provenance=PASS`.
- La auditoría reproducible `AUDIT_ONLY` conserva `MT5_FRESHNESS=REVIEW`
  porque deliberadamente no refresca la terminal; la aceptación live anterior
  es evidencia separada y no una auto-certificación de publicación.
- Se corrigió un bloqueo Windows de `EURUSD_M1.parquet`: el updater ahora
  materializa un temporal, valida que no esté vacío y reemplaza atómicamente
  con reintentos acotados. Un benchmark residual de Codex fue cerrado; no se
  tocó ningún proceso de Hermes.
- Se eliminó el replay LTF duplicado del ensamblador: `Object MarketState` es
  la única proyección de lifecycle del snapshot; `ltf_canonical_feed` conserva
  detección/relaciones y el modo público de touch.
- Fallas encontradas durante la misión: sello `tf` ausente, identidad
  `__index__` ausente y fixture de longitud inválida; todas corregidas y
  reverificadas.

## Riesgos

- La frescura de MT5 depende de la terminal local; si falla, el brief debe
  quedar bloqueado. Esta misión no ejecutó un refresco de la terminal.
- El puente certifica ensamblaje mecánico y causal, no la actualidad del feed
  ni la calidad científica de una lectura.
- Este gate no prueba edge ni autoriza trading.
- El brief completo EURUSD tarda 146 s en el host actual; es operativo y
  fail-closed, pero queda como deuda de rendimiento antes de ampliar a cuatro
  símbolos.

## Siguiente acción

M2–M5 quedan cerrados técnicamente y la frescura operativa fue verificada en
local. La siguiente acción es regenerar la auditoría final sobre el commit
local, realizar revisión independiente y decidir la publicación de los commits.
Esto no autoriza trading, backtest, IA, descarga Dukascopy ni promoción.
