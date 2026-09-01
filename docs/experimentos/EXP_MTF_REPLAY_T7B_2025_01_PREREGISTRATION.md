# Preregistro T7b — replay mensual con setups completos

**Estado:** FROZEN_BEFORE_RUN

Reutiliza exactamente los dos archivos, hashes, ventana enero 2025, warmup
diciembre y perfil `INTRADAY_H4_M15` de T7. No descarga, repara ni sustituye
datos. Procedencia formal permanece `BLOCKED_PROVENANCE`.

## Productor congelado

- Contrato: `CONTRATO_HISTORICAL_EVENT_OBJECT_PRODUCER_V1.md`.
- Ventanas de lineage: OB→FVG 120 h; FVG→BOS 72 h; BOS→displacement 24 h.
- Contexto en cada T: dirección del BOS H4 publicado más reciente.
- Sin niveles de ejecución, SL/TP, outcomes, edge, optimización, IA ni MT5.

## Gates

1. Productor determinista y FULL/PREFIX 25/50/75/90 PASS.
2. Todos los padres existen y `parent_time <= child_time`.
3. Al menos un BOS, displacement, setup completo y Episode en enero.
4. Ningún setup anterior al trigger que completa su lineage.
5. Replay determinista y FULL/PREFIX 25/50/75/90 PASS.
6. Artefacto/chunks schema 2.0 válidos y recursos reportados.
7. Cero trades es esperado: T7b valida composición, no ejecución.

Si no aparece población completa, T7b falla; no se cambian ventanas después de
observar el resultado.
