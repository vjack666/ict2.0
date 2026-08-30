# Plan ejecutable Hermes — Episodes / Funnel v1

**Estado:** READY_FOR_EXECUTION
**Owner:** Hermes, director de D2; Codex conserva auditoría independiente y autoridad final
**Modo:** LOCAL_ONLY
**SDD:** `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md`
**Contrato:** `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`

## Regla principal

Hermes debe trabajar hasta cerrar el objetivo completo. Una tarea no se marca
con `✅` por haber ejecutado un comando: se marca solo con evidencia guardada.
Si una tarea genera una subtarea técnica necesaria, Hermes debe crearla,
ejecutarla y verificarla automáticamente sin consultar al humano, siempre que
permanezca dentro del objetivo, write set, seguridad y autoridad definidos aquí.

## Protocolo autónomo de subtareas

Para cada tarea `T-x`:

1. Leer SDD, contrato, índice, último worklog, Graphify y estado Git.
2. Descomponer la tarea en subtareas atómicas antes de editar.
3. Si aparece trabajo necesario no listado, crear `SUB-T-x-n` en este plan y en
   la bitácora, con responsable, write set, criterio de DONE y dependencia.
4. Ejecutar la subtarea; no dejarla solo como comentario.
5. Verificarla con el gate correspondiente.
6. Si falla, diagnosticar causa raíz, corregir dentro del alcance y repetir.
7. Marcar `[x]` únicamente cuando la evidencia esté en un archivo o salida
   reproducible. Actualizar estado y `evidence_refs` inmediatamente.
8. Reanudar la tarea padre y repetir sus pruebas, porque una subtarea puede
   cambiar sus supuestos.

No pedir confirmación humana para decisiones técnicas internas reversibles. Sí
detenerse en `WAITING/BLOCKED` si se requiere cambiar objetivo, autoridad,
presupuesto, seguridad, datos, promoción, push o una acción destructiva.

## Lista de tareas

### T0 — Preparación y auditoría base — D1/D2/D5

- [x] `T0.1` Confirmar checkout, rama, HEAD, remote y ausencia de cambios
  pendientes antes de iniciar.
- [x] `T0.2` Leer `AGENTS.md`, índice, SDD padre, Lifecycle, MarketState,
  Setup Builder y Graphify.
- [x] `T0.3` Ejecutar pruebas focales de la capa previa: 94 passed.
- [x] `T0.4` Confirmar que no existe todavía un `engine/episodes.py` canónico.
- [x] `T0.5` Registrar auditoría base y riesgos en worklog.

### T1 — Congelar contrato y SDD — D1/D5

- [x] `T1.1` Definir Episode, FunnelRecord, estados y razones canónicas.
- [x] `T1.2` Definir identidad estable, deduplicación e idempotencia.
- [x] `T1.3` Definir autoridad temporal, lineage y separación de labels futuros.
- [x] `T1.4` Definir salida JSON, provenance, checksum y agregados.
- [x] `T1.5` Definir gates E0–E7 y criterio de DONE.
- [x] `T1.6` Enlazar contrato y SDD en índice y entrada de Hermes.
- [x] `T1.7` Obtener revisión independiente D5 del contrato antes de código. → PASS documental: 5 discrepancias reconciliadas con la API real de `engine/`, worklog `2026-08-30_AUDITORIA_D5_CONTRATO_EPISODES.md`.

### T2 — Implementar Episode/Funnel — D2

- [x] `T2.1` Crear `engine/episodes.py` tras T1.7 PASS. → `engine/episodes.py` (17.7 KB, lint OK).
- [x] `T2.2` Proyección desde `MarketState.projection_at(T)` (vía `build_setups_at`).
- [x] `T2.3` Validación temporal/autoridad/lineage fail-closed (`_check_temporal`/`_check_authority`/`_check_lineage`).
- [x] `T2.4` Identidad canónica `sha256` + sentinel NONE + dedupe idempotente (`_canonical_key`/`_episode_id_for`/`seen_keys`).
- [x] `T2.5` Separación de outcomes/labels: el funnel NO consume `outcome`/label futuro; estado derivado solo de `SetupEligibility`.
- [x] `T2.6` Dependencia no escrita resuelta: `build_episodes` acepta `candidates` override (audit/tests) sin salir del write set.

### T3 — Tests de dominio y auditoría — D2/D5

- [x] `T3.1` Tests de aceptación/rechazo (`tests/test_episodes.py`: ELIGIBLE→ACCEPTED, SUPERSEDED, BLOCKED→REJECTED, OUT_OF_CONTEXT→REJECTED).
- [x] `T3.2` Tests negativos: futuro (FUTURE_DATA), autoridad (INVALID_AUTHORITY), lineage (MISSING_LINEAGE), temporal (TEMPORAL_ORDER), duplicados (DUPLICATE_SETUP/idempotencia), no-mutación.
- [x] `T3.3` `audits/codigo/episodes.py` con salida determinista (JSON: records/episodes/rejections/aggregates/gates/checksum).
- [x] `T3.4` FULL/PREFIX literal en 3 decisiones T, TF H4/M15, dirección ±1 (`run_full_prefix` → `prefix_matches_full=True`).
- [x] `T3.5` Dos corridas idénticas → checksum estable (`da1008f8...` reproducible).
- [x] `T3.6` Fallos reproducibles corregidos y re-verificados (ids no deterministas del corpus audit → arreglados; 388 passed).

### T4 — Cierre documental y entrega — D1/D7

- [x] `T4.1` `pytest tests/` completo → **388 passed**.
- [x] `T4.2` Reporte `reports/audits/episodes/episodes_audit_20260830.json` (status PASS, commit, config, provenance, aggregates, rejections, lineage, checksum).
- [x] `T4.3` Worklog `2026-08-30_EPISODES_FUNNEL_CIERRE.md` + index + contrato/SDD actualizados por la revisión D5.
- [ ] `T4.4` Ejecutar `graphify update .` y registrar resultado.
- [ ] `T4.5` `git diff --check` y revisar write set.
- [ ] `T4.6` Commit local selectivo; no push.
- [ ] `T4.7` Entrega final con AGENTE/DEPARTAMENTO/TAREA/STATUS/EVIDENCIA/ARCHIVOS/RIESGOS/SIGUIENTE ACCIÓN.

## Condiciones de cierre

Hermes puede marcar `COMPLETED` solo si T1.7, T2, T3 y T4 están completos,
todos los gates E0–E7 están en PASS y no existe subtarea abierta. Si existe un
bloqueo externo real, marcar `WAITING` o `BLOCKED` con evidencia concreta; no
declarar éxito parcial.

## No desviación

No buscar edge, no ejecutar backtest de rendimiento, no entrenar IA, no tocar
datasets, no descargar datos, no usar remoto, no crear segunda FSM, no modificar
Lifecycle/MarketState/Setup Builder salvo que un test demuestre un defecto y la
corrección quede dentro del contrato padre.
