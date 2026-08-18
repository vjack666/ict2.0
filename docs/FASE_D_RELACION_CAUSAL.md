# FASE D — Relación causal y lineage

**Estado:** `COMPLETADA / GATE_PASS`  
**Precondición:** Gate C PASS  
**Alcance:** lineage y relaciones causales; sin ejecución, scoring, aprendizaje ni optimización.

## Objetivo

Convertir los objetos detectados en una cadena causal auditable, sin permitir que un evento histórico dependa de información futura.

## Contrato

Cada relación causal debe identificar `parent_id`, `child_id`, `relation`, `parent_bar`/`child_bar` y, cuando existe, `parent_time`/`child_time`.

Reglas obligatorias:

1. parent y child deben ser objetos distintos;
2. `parent_bar <= child_bar`;
3. cuando existen timestamps, `parent_time <= child_time`;
4. no se permiten enlaces causales duplicados;
5. `bar_index` es obligatorio para construir un enlace;
6. el lineage es explícito por origen (`parent_object` / `CausalLink`), no por proximidad temporal.

## Implementación

`engine/lineage.py` conserva el consumidor `trace_setup_lineage()` y ahora además expone `CausalLink`, `link()` y `validate_links()` como contrato ejecutable de relaciones históricas.

La cadena canónica conserva el orden:

`LIQUIDITY → SWEEP → DISPLACE → BOS → POI/REFINEMENT → RETURN`

FVG/OB se integran como objetos derivados del movimiento correspondiente y no pueden utilizar información posterior a su timestamp de decisión.

## Evidencia Gate D

**Workflow:** `Hermes Tests`  
**Run:** `#85`  
**Run ID:** `32084187515`  
**Resultado:** **27 passed in 0.05s**

Cobertura específica:

- parent antes de child;
- rechazo de parent futuro;
- rechazo de timestamp futuro;
- rechazo de `bar_index` ausente;
- rechazo de enlaces duplicados;
- inmutabilidad de `CausalLink`.

El primer intento de Gate D falló por una discrepancia entre el `lineage.py` preexistente y el contrato de pruebas (`CausalLink` no estaba implementado). Se corrigió el código y se volvió a ejecutar la suite. El segundo intento quedó completamente verde.

## Fuera de alcance

- entrada, SL/TP;
- scoring;
- aprendizaje/IA;
- ablación;
- OOS;
- obtención de M5;
- clasificación adicional de OB no definida aún por la tesis.

## Decisión

**GATE D = PASS.** Fase E queda habilitada.
