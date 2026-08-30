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
- [ ] `T1.7` Obtener revisión independiente D5 del contrato antes de código.

### T2 — Implementar Episode/Funnel — D2

- [ ] `T2.1` Crear `engine/episodes.py` solo después de T1.7 PASS.
- [ ] `T2.2` Implementar proyección desde `MarketState.projection_at(T)`.
- [ ] `T2.3` Implementar validación temporal, autoridad y lineage fail-closed.
- [ ] `T2.4` Implementar identidad canónica y deduplicación determinista.
- [ ] `T2.5` Implementar separación de outcomes/labels posteriores.
- [ ] `T2.6` Si surge una dependencia no escrita, crear `SUB-T2-n`, ejecutarla
  y volver a probar T2 completo.

### T3 — Tests de dominio y auditoría — D2/D5

- [ ] `T3.1` Crear tests de aceptación y rechazo del Episode.
- [ ] `T3.2` Crear tests negativos de futuro, autoridad, lineage, duplicados y
  mutación.
- [ ] `T3.3` Crear `audits/codigo/episodes.py` con salida determinista.
- [ ] `T3.4` Ejecutar FULL/PREFIX literal en varias decisiones T, TF y dirección.
- [ ] `T3.5` Repetir corrida idéntica y comparar checksum lógico.
- [ ] `T3.6` Corregir automáticamente cada fallo reproducible y repetir todos
  los gates afectados.

### T4 — Cierre documental y entrega — D1/D7

- [ ] `T4.1` Ejecutar tests focales y `pytest tests/` completo.
- [ ] `T4.2` Generar reporte con commit, configuración, provenance, agregados,
  rechazos, lineage y checksum.
- [ ] `T4.3` Actualizar worklog, `.hermes-index.md`, SDD y contrato si la
  evidencia cambió una decisión.
- [ ] `T4.4` Ejecutar `graphify update .` y registrar su resultado.
- [ ] `T4.5` Ejecutar `git diff --check` y revisar write set.
- [ ] `T4.6` Crear commit local selectivo; no hacer push automático.
- [ ] `T4.7` Entregar `AGENTE/DEPARTAMENTO/TAREA/STATUS/EVIDENCIA/ARCHIVOS/
  RIESGOS/SIGUIENTE ACCIÓN`.

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
