# FASE D — Relación causal y lineage

**Estado:** `COMPLETADA / GATE_PASS`  
**Precondición:** Gate C PASS  
**Alcance:** lineage y relaciones causales; sin ejecución, scoring, aprendizaje ni optimización.

**Enmienda 2026-09-21:** instalado contrato jerarquico `LINEAGE_HIERARCHY_V1`
en `engine/lineage_hierarchy.py` y conectado al snapshot observacional de
`engine/daily_motor.py`. Ver
`docs/contratos/CONTRATO_LINEAGE_HIERARCHY_V1.md`.

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

`engine/lineage_hierarchy.py` agrega el adaptador de grafo jerarquico:
deriva o consume `CausalLink`, valida ciclos, huerfanos, referencias no
resueltas, futuros, profundidad, raices/hojas, provenance por TF y cobertura
D1/H4/H1/M15/M5/M1. El adaptador no detecta nuevos objetos ni inventa padres.

La cadena canónica conserva el orden:

`LIQUIDITY → SWEEP → DISPLACE → BOS → POI/REFINEMENT → RETURN`

FVG/OB se integran como objetos derivados del movimiento correspondiente y no pueden utilizar información posterior a su timestamp de decisión.

## Evidencia Gate D

**Evidencia histórica:** suite `Hermes Tests`, run `#85`, ID `32084187515` (las futuras verificaciones son locales)
**Resultado:** **27 passed in 0.05s**

Cobertura específica:

- parent antes de child;
- rechazo de parent futuro;
- rechazo de timestamp futuro;
- rechazo de `bar_index` ausente;
- rechazo de enlaces duplicados;
- inmutabilidad de `CausalLink`.

El primer intento de Gate D falló por una discrepancia entre el `lineage.py` preexistente y el contrato de pruebas (`CausalLink` no estaba implementado). Se corrigió el código y se volvió a ejecutar la suite. El segundo intento quedó completamente verde.

## Evidencia enmienda jerarquica 2026-09-21

**Commit local:** `117c8f31 feat(lineage): enforce hierarchical lineage snapshot contract`

Cobertura nueva:

- cadena D1 -> H4 -> H1 -> M15 -> M5 -> M1 valida con `require_all_six_tfs=True`;
- H4/M15-only queda `LINEAGE_LEGACY_UNVALIDATED` cuando se exige seis TF;
- ausencia de lineage se publica como `LINEAGE_NOT_PROVIDED`, no como `None`;
- lineage invalido recibido por `daily_motor` bloquea candidato con `WAIT_LINEAGE_VALIDATION`;
- no quedan `type: ignore` ni `Optional[...]` en la ruta nueva.

Resultados:

- `tests/test_daily_motor.py tests/test_lineage_hierarchy.py`: `13 passed`;
- grupo lineage/causalidad: `53 passed`;
- suite completa: `865 passed, 8 warnings`;
- `graphify update .`: PASS.

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
