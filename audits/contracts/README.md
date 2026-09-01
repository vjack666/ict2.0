# Contratos de auditoría

Los contratos de auditoría son normativos y separan tres cosas:

1. **Finding** — qué salió mal.
2. **AuditResult** — estado agregado del Gate.
3. **StageSummary** — población que atraviesa cada etapa.

No contienen reglas de trading. Sólo expresan invariantes de calidad, temporalidad y trazabilidad.

## Severidades

- `CRITICAL` → FAIL y bloqueo.
- `HIGH` / `MEDIUM` → WARN; requieren explicación y decisión explícita antes de habilitar el siguiente Gate.
- cualquier ausencia de finding → PASS.
