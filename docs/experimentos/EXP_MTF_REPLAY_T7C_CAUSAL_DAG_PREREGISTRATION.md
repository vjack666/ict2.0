# Preregistro — T7c DAG causal y puente hacia IA

## Objetivo

Verificar que el productor histórico v2 materializa setups completos mediante
el Setup Builder canónico sin imponer que el FVG preceda al displacement.
T7c es un gate de población y causalidad, no una búsqueda de edge.

## Datos congelados

- EURUSD M15, diciembre 2024 como warmup y enero 2025 como evaluación.
- Mismos dos archivos y SHA-256 congelados en T7/T7b.
- No descargar, reparar, sustituir ni seleccionar otro mes por resultados.
- Integridad mecánica y procedencia formal se reportan por separado;
  `BLOCKED_PROVENANCE` no se convierte en PASS por disponer de hashes.

## Productor congelado antes de ejecutar

- POI: OB H4 ACTIVE.
- Refinement: FVG M15 del mismo sentido, solapado con el POI.
- Confirmation: BOS M15 del mismo sentido y vinculado al POI.
- Trigger: displacement M15 posterior al BOS, mismo sentido y POI.
- Ventanas: POI→hijo 120 h; BOS→displacement 24 h.
- Todos los tiempos son cierres publicados; lineage solo apunta hacia atrás.

## Gates

1. IDs y salida deterministas.
2. Todo padre existe y `parent_time <= child_time`.
3. FULL/PREFIX exacto en 25/50/75/90%.
4. Al menos un setup completo en enero.
5. Al menos un setup elegible y un episodio materializado.
6. Ningún setup aparece antes de confirmation y trigger.
7. Manifest/chunks reproducibles.

Si 4–5 fallan, estado `BLOCKED_POPULATION`; no se cambian ventanas, detectores
ni mes después de observar el resultado. Si pasan, se autoriza solamente la
materialización de un corpus diagnóstico causal; no edge, promoción ni trading.
