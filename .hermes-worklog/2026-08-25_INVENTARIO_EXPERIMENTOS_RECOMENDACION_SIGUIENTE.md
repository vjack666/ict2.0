# Inventario de experimentos y recomendación científica siguiente

**Fecha:** 2026-08-25  
**AGENTE:** Codex (CEO/auditor de decisión científica)  
**DEPARTAMENTO:** Research/Lab + Gobierno de evidencia  
**TAREA:** Revisar planes/SDD vigentes en `2fe5d70`, inventariar experimentos pendientes, resolver colisiones de nombres y recomendar un único siguiente experimento.  
**STATUS:** COMPLETED — recomendación entregada; no se ejecutaron backtests, entrenamiento, descargas ni jobs de laboratorio.

## Alcance y estado inicial

- Checkout operativo usado: `C:\Users\v_jac\Desktop\ICT SYSTEM`.
- `HEAD`: `2fe5d7029fcc0dba8104babb5636b581a65425c6` (`feature/a5-audit-datos`, también en `origin/feature/a5-audit-datos`).
- Se preservaron sin tocar cambios preexistentes en `data/raw/`, `reports/charts/`, `.codex/` y `docs/briefs/`.
- El inventario fue documental/read-only. No se escribieron datasets ni se lanzaron runners.

## Hechos verificados

### 1. EXP-SEQ-CTX-01 queda cerrado

`.hermes-index.md` § Sequence × Context y `docs/experimentos/EXP_SEQ_CTX_01.md` §7 registran el gate causal re-ejecutado como `PASS 0/120`, pero mantienen el veredicto OOS `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`. Las celdas HOLDOUT verificadas son canonical `19/110/23` y lite `24/177/44`; no hay snapshot de IA ni autorización operativa.

La cabecera antigua de `EXP_SEQ_CTX_01.md` todavía dice `EN EJECUCIÓN` en la línea 4, mientras la reconciliación §7 y el índice lo tratan como cerrado. Esto es una inconsistencia documental pendiente, no una razón para reabrir el experimento.

### 2. La serie B standalone ya tiene evidencia, pero el reconciliador histórico no la incluye

El worklog `.hermes-worklog/2026-08-21_1845_LAB_15EXP_INCREMENTALIDAD.md` documenta B1–B5 con artefactos en `reports/audits/`:

- B1 baseline: PASS, `n=211`, `meanR=+0.2499`.
- B2 `+D1`: FAIL incremental, `Δ=-0.1061 R`, IC95 cruza 0.
- B3 `+H4`: PASS mecánico, pero el incremento no queda demostrado.
- B4 D1+H4: PASS mecánico, pero el IC del incremento cruza 0.
- B5 apareado con/sin HTF: FAIL incremental, `Δ=-0.0703 R`, IC cruza 0.

`reports/audits/EXP_B2_audit.json` confirma que B2 significa `INCREMENTAL_D1_BIAS_FILTER`, con `FAIL_INCREMENTAL`.

En cambio, `reports/audits/experiments/current_batch/EXP_MASTER_RECONCILIATION.{json,md}` fue generado el 2026-08-21 con otra matriz de 15 experimentos y marca B1–B5 como `BLOCKED` por ausencia de JSON dentro de esa subcarpeta. No debe usarse para negar los artefactos standalone; debe leerse como reconciliación parcial de otro lote. La discrepancia queda registrada como deuda de reconciliación.

### 3. El nombre B2 está colisionado

- El plan maestro `.hermes/plans/2026-08-16_1510_PIPELINE_APRENDIZAJE_CIENTIFICO.md` usa `B2` para `WYCKOFF × ICT CONFLICT`.
- `docs/experimentos/EXP_B_DESIGN.md` usa `B2` para el filtro HTF D1 y declara que ese diseño fue reconstruido post-hoc, aunque los artefactos standalone B1–B5 sí existen.
- El pre-registro nuevo resuelve la ambigüedad con el ID inequívoco `EXP-WYCKOFF-ICT-01` y declara explícitamente que no reutiliza B2.

Conclusión: no se debe ordenar a Hermes “ejecuta B2”. Debe usarse exclusivamente `EXP-WYCKOFF-ICT-01`.

### 4. El siguiente candidato está preregistrado, pero bloqueado por factibilidad

`docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md` declara `PRE-REGISTRADO / NO EJECUTADO`, `can_train=false` y `can_trade=false`. El índice vigente lo clasifica como `FEASIBILITY BLOCKED` porque todavía falta un clasificador Wyckoff por barra reproducible y debe resolverse/documentarse el conflicto entre el motor a5 y TNA.

El plan `.hermes/plans/2026-08-20_WYCKOFF_ENGINE_INTEGRATION.md` exige antes: inventario/clasificación de módulos, autoridad runtime, `WyckoffSnapshot`, prefijo PIT, tests unitarios/integración/migración y ausencia de veto universal. Por tanto, el siguiente trabajo inmediato no es la corrida científica: es cerrar ese gate de factibilidad.

## Inventario operativo

| Elemento | Estado verificado | Tratamiento |
|---|---|---|
| `EXP-SEQ-CTX-01` | Cerrado negativo honesto: OOS insuficiente; G0/G1 pasan | No reabrir ni rescatar sin nueva decisión/prerregistro |
| `EXP-SEQ-CTX-01` legado (`EXP_SEQUENCE_X_CONTEXT_STATE`) | Ejecutado; `INSUFFICIENT_N`/baja evidencia | Histórico; no siguiente |
| Expectancy COMPLETE H1 | Ejecutado; `n=5`, insuficiente | Cerrado como insuficiente |
| Expectancy DEPTH≥4 LITE H1 | Ejecutado; gate técnico PASS, no señal aprobada | No usar como autorización operativa |
| FVG/OB causal forward | Hipótesis falsada | No repetir como siguiente experimento |
| Multifactor H1 | Congelado, evidencia exploratoria/sin edge | No expandir ad-hoc |
| Serie B standalone | Ejecutada; P2 HTF incremental refutada bajo ese protocolo | No repetir B2 ni cambiarle el nombre |
| `EXP_B_DESIGN.md` | Diseño reconstruido post-hoc; no autoridad para relanzar la serie | Mantener como registro, reconciliar estados |
| `EXP-004B-01` generalización temporal | OPEN, sin prioridad frente al candidato preregistrado | No elegir como siguiente |
| M5 learning | DEFERRED/OPEN | Fuera de la ruta H1/H4/D1 actual |
| Integración Wyckoff | Objetivo activo de infraestructura/factibilidad | Prerrequisito de `EXP-WYCKOFF-ICT-01`, no resultado científico |
| `EXP-WYCKOFF-ICT-01` | Preregistrado, no ejecutado, FEASIBILITY BLOCKED | Único siguiente experimento recomendado, condicionado al gate |

## Recomendación única

### Experimento

`EXP-WYCKOFF-ICT-01 — WYCKOFF × ICT CONFLICT`.

### Hipótesis

El contexto Wyckoff (`PRO_TREND`, `COUNTERTREND`, `TRANSITION`, `NEUTRAL`) aporta información incremental sobre los outcomes respecto al `Context State` ICT (`ALIGNED`, `NEUTRAL`, `AGAINST`), especialmente comparando conflicto Wyckoff dentro de un bucket ICT fijo frente a no-conflicto.

### Datos y contrato

- EURUSD, 20Y Dukascopy canónico; H1/H4/D1.
- Motor secuencial `canonical_bos` y `MTFNavigator` con equivalencia FULL-vs-PREFIX.
- Wyckoff debe producir un snapshot por barra con `close_time <= t`.
- Bloques congelados: DESIGN 2006–2015, VALIDATION 2016–2020, HOLDOUT 2021–2025.
- Outcomes futuros a +6/+12/+24/+48 H1; sin EMA, ATR como sesgo, OTE, entry, stop, PnL u optimización.

### Tamaño muestral

Para MDE de 10 puntos porcentuales, potencia 0.80 y alfa 0.05, el preregistro fija aproximadamente `389 por grupo` (`~778` total), con corrección por las tres comparaciones primarias. `n≥30` es solo piso administrativo. Si no se alcanza el n preregistrado, el veredicto obligado es `INSUFFICIENT_N / INCONCLUSIVE`; no se amplía post-hoc.

### Gates

1. **Factibilidad:** clasificador Wyckoff por barra y contrato `WyckoffSnapshot` existentes/reproducibles; conflicto a5↔TNA resuelto o formalmente delimitado.
2. **PIT:** `snapshot(full,t) == snapshot(prefix_through_t,t)`; eventos y confirmaciones no pueden mirar futuro.
3. **Integridad/provenance:** commit, hashes, fuente canónica, configuración y manifest congelados.
4. **Muestra/potencia:** evaluar con el n preregistrado; si es insuficiente, cerrar como inconcluso.
5. **Estadística:** efecto incremental dentro de ICT fijo, IC95 bootstrap agrupado por `chain_id`, corrección por comparaciones múltiples y estabilidad temporal.
6. **Seguridad:** `can_train=false`, `can_trade=false`; ningún resultado promociona una señal ni autoriza backtest productivo.

### Coste aproximado

Inferencia de planificación, no medición: coste local medio/alto respecto a una auditoría simple, porque requiere clasificador Wyckoff por barra, navegación MTF, outcomes, manifest y bootstrap. No requiere nube ni descarga adicional si se conserva el universo canónico. El tiempo exacto debe medirse únicamente en un preflight autorizado; no se ejecutó por esta misión.

### Motivo de prioridad

Es el único candidato explícitamente preregistrado después del cierre de `EXP-SEQ-CTX-01`, responde una pregunta nueva —Wyckoff incremental frente a ICT— y evita reabrir una hipótesis de Context State ya cerrada. La prioridad es científica, pero la autorización de ejecución queda condicionada al cierre de factibilidad.

## Riesgos y decisión solicitada

- El riesgo principal es invertir en una corrida cuyo `n` real vuelva a ser insuficiente; el preregistro ya obliga a declararlo `INCONCLUSIVE`.
- La nomenclatura B2 puede inducir a Hermes a repetir el experimento HTF ya ejecutado o a mezclarlo con Wyckoff.
- La documentación todavía contiene estados históricos que no están completamente reconciliados (`EXP_SEQ_CTX_01.md` cabecera y `current_blockers.md` antiguo). No se han corregido en esta misión para evitar mezclar una auditoría con una edición normativa.

**Siguiente acción propuesta para decisión de Ruben:** autorizar únicamente una auditoría/preflight de factibilidad de `EXP-WYCKOFF-ICT-01` conforme al plan de integración Wyckoff. No autorizar todavía la matriz, backtest, entrenamiento ni descarga.

## Evidencia principal

- `.hermes-index.md:98-132` — estado vigente, siguiente candidato y bloqueadores.
- `.hermes/plans/2026-08-16_1510_PIPELINE_APRENDIZAJE_CIENTIFICO.md:169-203,237-251` — A7 y B2 del plan maestro.
- `.hermes/plans/2026-08-20_WYCKOFF_ENGINE_INTEGRATION.md:28-70,256-331` — inventario, PIT y gate de integración.
- `docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md:1-7,33-108,112-192` — contrato prospectivo, potencia, PIT y veredictos.
- `docs/experimentos/EXP_B_DESIGN.md:1-18,22-28,59-79` — B2 HTF y caveat de reconstrucción.
- `reports/audits/EXP_B2_audit.json:1-42` — B2 standalone, `FAIL_INCREMENTAL`.
- `.hermes-worklog/2026-08-21_1845_LAB_15EXP_INCREMENTALIDAD.md:35-72` — resultados B1–B5 y refutación P2.
- `reports/audits/experiments/current_batch/EXP_MASTER_RECONCILIATION.md:5-40` — reconciliación parcial histórica que marca el grupo B como ausente en ese lote.

## Estado de sincronización

- Engram local y compartido: handoff final sin secretos, con este dictamen y el bloqueo de factibilidad.
- Graphify: consultado en modo lectura; confirma nodos y relaciones de `EXP-WYCKOFF-ICT-01`, `EXP-SEQ-CTX-01` y B2. No se actualizó el grafo porque no se modificó código ni se alteraron dependencias.
- Git: este worklog es el único artefacto generado por esta misión; los cambios ajenos permanecen fuera del alcance.
