# Apertura de misión científica Fase 2B

**AGENTE:** Codex, director operativo
**DEPARTAMENTO:** D4 Data Lineage (dueño inicial), con D5/D6/D3 condicionados
**TAREA:** abrir la misión científica de desbloqueo del productor EURUSD Fase 2B
**STATUS:** PLAN

## Evidencia

- Misión persistida: `MC-20260911-153509-dfab2f`.
- Ruta automática: D4 Data Lineage / Data Engineer; revisiones CRO y
  Compliance.
- Alcance permitido: D1, D3, D4, D5 y D6. Quedan excluidos secretos, órdenes,
  MT5, publicación y promoción.
- Contratos revisados: SDD del productor, preregistro PASS_EDGE y contrato CRO.

## Riesgos

Los gates de provenance, reproducibilidad, fill/costes/horizonte y causalidad
siguen sin PASS. El preregistro continúa `DRAFT_BLOCKED / NO EJECUTAR`; abrir
la misión no equivale a autorizar U4/U5 ni a producir una señal.

## Siguiente acción

U0/U1: inventario D4 y freeze de evidencia, en modo solo lectura. Cualquier
ausencia de fuente, licencia, adquisición, hash o lineage debe quedar como
`BLOCKED` explícito.
