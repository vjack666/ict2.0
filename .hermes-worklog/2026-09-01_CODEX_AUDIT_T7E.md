# Auditoría Codex — último trabajo OpenCode/Hermes T7e

## Dictamen

`PASS_TECHNICAL_REPRODUCED / REVIEW`.

## Verificación independiente

- 65 pruebas focales de lifecycle, episodes, Setup Builder, productor y replay: PASS.
- T7d re-ejecutado desde `b7eabad` en una carpeta temporal aislada:
  `PASS_TECHNICAL_BLOCKED_PROVENANCE`, 4 setups completos, 4 elegibles,
  4 episodios, 20 registros y 0 trades.
- Determinismo interno, FULL/PREFIX 25/50/75/90, manifest y gate temporal: PASS.

## Corrección

Se retiró `CERTIFIED_REPLAY_SEED` como certificación formal. El dictamen OE7 y
sus corridas viven bajo `%TEMP%`, no en Git; además el reporte versionado declara
commit `9f0d56a`, anterior al fix B5 `c99d00b`. La evidencia demuestra
reproducibilidad técnica actual, no una certificación formal de punta.

## Riesgos y siguiente acción

La muestra es 2 setups únicos / 4 episodios y no contiene trades, edge ni IA.
Antes de T7f se debe versionar un reporte reproducido cuyo commit de generador
incluya todos los fixes relevantes. No se tocaron datasets, parquets ni
artefactos IA no relacionados.
