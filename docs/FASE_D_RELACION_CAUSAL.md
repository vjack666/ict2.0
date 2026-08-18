# FASE D — Relación causal y lineage

**Estado:** `IN_PROGRESS / GATE_PENDING`  
**Precondición:** Gate C PASS  
**Alcance:** lineage y relaciones causales; sin ejecución, scoring, aprendizaje ni optimización.

## Objetivo

Convertir los objetos detectados en una cadena causal auditable, sin permitir que un evento histórico dependa de información futura.

## Contrato

Cada relación causal debe identificar:

- `parent_id`;
- `child_id`;
- `relation`;
- `parent_bar` / `child_bar`;
- opcionalmente `parent_time` / `child_time`.

Reglas obligatorias:

1. parent y child deben ser objetos distintos;
2. `parent_bar <= child_bar`;
3. cuando existen timestamps, `parent_time <= child_time`;
4. no se permiten enlaces causales duplicados;
5. `bar_index` es obligatorio para construir un enlace;
6. el lineage es explícito por origen (`parent_object` / `CausalLink`), no por proximidad temporal.

## Implementación actual

`engine/lineage.py` contiene un consumidor de lineage del motor y una API contractual `CausalLink`, `link()` y `validate_links()` para relaciones temporales explícitas.

La cadena canónica del producto conserva el orden histórico:

`LIQUIDITY → SWEEP → DISPLACE → BOS → POI/REFINEMENT → RETURN`

FVG/OB se integran como objetos derivados del movimiento correspondiente y no pueden utilizar información posterior a su timestamp de decisión.

## Anti-look-ahead

Las pruebas deben demostrar que:

- un parent futuro se rechaza;
- un timestamp futuro se rechaza;
- objetos sin `bar_index` no pueden formar lineage;
- enlaces duplicados se rechazan;
- la relación causal es explícita y estable.

## Fuera de alcance

- entrada, SL/TP;
- scoring;
- aprendizaje/IA;
- ablación;
- OOS;
- obtención de M5;
- clasificación adicional de OB no definida aún por la tesis.

## Gate D

PASS sólo si:

1. contrato de lineage pasa sus tests;
2. no-look-ahead temporal pasa 100% en la suite diseñada;
3. suite completa del repositorio pasa;
4. no se introduce OTE/Fibonacci;
5. documentación, `.hermes-index.md` y worklog reflejan evidencia real.

Ante cualquier fallo: corregir y volver a ejecutar.
