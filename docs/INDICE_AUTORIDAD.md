# Índice de Autoridad — ICT SYSTEM

Este archivo define qué documentación es **autoridad vigente** en `ICT SYSTEM` y qué se dejó deliberadamente fuera de `SMC-SYSTEMS`.

Principio: **poca documentación, mucha autoridad.**

## Mapa de estructura

La descripción completa de carpetas, capas activas y reglas de migración está
en [`REPOSITORY_MAP.md`](REPOSITORY_MAP.md) y
[`REPOSITORY_ORDER.md`](REPOSITORY_ORDER.md).

El modelo operativo de departamentos, la autoridad de Codex como dirección
ejecutiva y las reglas de delegación están en
[`../AGENTS.md`](../AGENTS.md),
[`../governance/ORGANIGRAMA_ICT_2_0.md`](../governance/ORGANIGRAMA_ICT_2_0.md) y
[`../governance/DEPARTMENT_REGISTRY.json`](../governance/DEPARTMENT_REGISTRY.json).

---

## 🟢 Autoridad vigente

### Fuente firmada y enmiendas

| Archivo | Rol | Estado |
| --- | --- | --- |
| `docs/ict/SPEC_TESIS_FORMAL.md` | Contrato fuente firmado 2026-07-20. | Autoridad base. |
| `docs/ict/SPEC_TESIS_FORMAL_V1.1_AMENDMENT_OTE_REMOVAL.md` | Enmienda operativa 2026-08-17: elimina OTE del modelo. | **Vigente y supersede cualquier regla OTE.** |

**Jerarquía:** el SPEC firmado sigue siendo la fuente base; la enmienda v1.1 modifica exclusivamente el tratamiento de OTE. Ante cualquier conflicto sobre OTE, la enmienda manda.

### Libros de la tesis

| Archivo | Rol |
| --- | --- |
| `docs/ict/00_INDICE.md` | Índice de la biblioteca ICT. |
| `docs/ict/01_KILLZONES.md` | Ventanas horarias. |
| `docs/ict/02_MSS_CHOCH.md` | MSS / CHOCH / BOS. |
| `docs/ict/03_FVG.md` | Fair Value Gap — **núcleo de entrada**. |
| `docs/ict/04_ORDER_BLOCKS.md` | Order Blocks — **núcleo de entrada**. |
| `docs/ict/05_LIQUIDEZ.md` | Liquidez / Sweep. |
| `docs/ict/06_TURTLE_SOUP.md` | Turtle Soup. |
| `docs/ict/07_SILVER_BULLET.md` | Silver Bullet. |
| `docs/ict/08_POWER_OF_THREE.md` | PO3 / AMD. |
| `docs/ict/14_STOP_LOSS_ESTRUCTURAL.md` | SL estructural. |
| `docs/ict/15_INTRADIA_ENTRADA_SL_TP.md` | Entrada/SL/TP. |
| `docs/ict/16_TEMPORALIDAD_EJECUCION.md` | Temporalidad de ejecución. |
| `docs/ict/17_SCALPING_ENTRADA_SL_TP.md` | Scalping. |
| `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md` | HTF/ITF/exec. |
| `docs/ict/20_TESIS_ICT.md` | Síntesis unificadora. |
| `docs/ict/21_POI.md` | POI / PD Arrays. |

### Diccionarios de detección

| Archivo | Rol |
| --- | --- |
| `docs/reglas/ICT_RULEBOOK.md` | Diccionario machine-readable ICT. **OTE eliminado.** |
| `docs/reglas/WYCKOFF_RULEBOOK.md` | Diccionario Wyckoff. |
| `docs/wyckoff/**` | Teoría Wyckoff. |

### Capa LTF del motor diario

| Archivo | Rol | Estado |
| --- | --- | --- |
| `docs/tesis/PLAN_LTF_ENTRY_LAYER.md` | Plan de trabajo para conectar LTF/EXEC al uso diario. | Activo |
| `docs/tesis/SDD_LTF_ENTRY_LAYER.md` | Contrato de diseño LTF-1; observación, no órdenes. | Normativo LTF-1 |

### Motor autónomo de misiones Hermes

| Archivo | Rol | Estado |
|---|---|---|
| `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md` | Contrato normativo del motor de misiones autónomas, persistencia, delegación, recuperación y terminación. | Diseño autorizado; implementación pendiente |
| `.hermes/plans/2026-08-20_HERMES_MISSION_CONTROLLER.md` | Plan MC-0..MC-8 con gates obligatorios. | Autorizado para ejecución por fases |

### Capa de composición del motor

| Archivo | Rol | Estado |
| --- | --- | --- |
| `engine/setup_builder.py` | Capa de composición (Lifecycle → Market State → Setup Builder): ensambla `Setup` ICT/SMC completos desde `MarketState` histórico (`context_htf → poi → refinement → confirmation → trigger`). | **PROMOVIDO CON REVISIÓN 2026-08-28 (H1–H4 cerrados; sin CERTIFIED)** |
| `docs/planificacion/SDD_FVG_OB_ENGINE.md` §13 | Contrato de diseño de Setup Builder (modelo, separación `object_state` vs `setup_eligibility`, snapshot histórico sin look-ahead). | PROMOVIDO CON REVISIÓN 2026-08-28 (H1–H4 cerrados; sin CERTIFIED) |

### SDD consolidado post-A7

| Archivo | Rol | Estado |
|---|---|---|
| `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md` | Contrato único de la capa `MarketObject → Lifecycle → MarketState → Setup Builder`, autoridad TF, observación LTF, persistencia y FULL/PREFIX. | **NORMATIVO 2026-08-30** |
| `.hermes/plans/2026-08-30_POST_A7_ENGINE_STATE_EPISODES.md` | Plan operativo de reconciliación, verificación y transición a Episodes/Funnel. | **VIGENTE** |
| `.hermes-worklog/2026-08-30_RECONCILIACION_DOCUMENTAL_POST_A7.md` | Evidencia de la reconciliación y sus límites. | **CERRADO DOCUMENTALMENTE** |
| `SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md` en `codex/visual-replay-wyckoff-v1-1` | SDD histórico de proyección diagnóstica `backtest/`; no gobierna `engine/`. | **HISTÓRICO / NO AUTORIDAD ACTUAL** |

### Episodes / Funnel

| Archivo | Rol | Estado |
|---|---|---|
| `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md` | Identidad, etapas, razones de rechazo, lineage, deduplicación y gates del Funnel. | **NORMATIVO PARA IMPLEMENTACIÓN LOCAL** |
| `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md` | Diseño de la capa sobre `MarketState(T)` y `Setup(T)`. | **NORMATIVO PARA DISEÑO; REVISIÓN D5 PENDIENTE** |
| `.hermes/plans/2026-08-30_EPISODES_FUNNEL_V1.md` | Lista de tareas, subtareas dinámicas, responsables y criterio de cierre para Hermes. | **READY_FOR_EXECUTION** |
| `.hermes-worklog/2026-08-30_AUDITORIA_PRE_EPISODES_FUNNEL.md` | Auditoría de entrada y decisión de alcance. | **CERRADO — IMPLEMENTACIÓN PENDIENTE** |

La siguiente capa es Episodes/Funnel. Debe tener contrato y SDD propios antes de
crear código; no se deben reimplementar Lifecycle, MarketState ni Setup Builder.

### Contratos con ruta canónica

| Concepto | Ruta canónica | Ruta de compatibilidad |
|---|---|---|
| Context State | `docs/contratos/CONTRATO_CONTEXT_STATE.md` | `docs/historical/compatibility/CONTRATO_CONTEXT_STATE_legacy_2026-08-20.md` |
| Inventario de datos | `docs/DATA_INVENTARIO.md` | `docs/historical/compatibility/DATA_INVENTARIO_legacy_2026-08-20.md` |

Las rutas históricas no deben recibir nuevas reglas normativas. Se conservan
bajo `docs/historical/` para auditoría y trazabilidad, no como interfaces
activas.

---

## 🔴 Documentación histórica / fuera de autoridad

Los documentos de arquitectura, SDDs y filtros históricos de `SMC-SYSTEMS` permanecen fuera de la autoridad vigente. En particular, los antiguos documentos `10_SWEEP_OTE_FILTRO.md` y `11_SWEEP_OTE_MANUAL_VS_AUTO.md` son históricos y **no deben reintroducir OTE** en `ict2.0`.

---

## Cambio 2026-08-17 — OTE eliminado

La política actual de entrada es:

`HTF bias → liquidez → sweep → displacement → BOS/CHOCH → FVG/OB → retorno/retest → entry → SL estructural → TP en liquidez`

Premium/Discount y EQ 50% permanecen como contexto. **OTE, Fibonacci 62–79%, OTE score y OTE gate quedan fuera.**

El núcleo de zonas de entrada queda concentrado en **FVG + Order Block**, con liquidez, estructura y displacement como contexto/confirmación.
