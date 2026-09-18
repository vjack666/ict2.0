# Auditoría de autonomía — commit 26a820d

**Fecha:** 2026-09-18  
**Commit auditado:** `26a820dd4a2ac269a61e42e799dee65dec7c6ebe`  
**Veredicto:** `REVIEW_REQUIRED_NOT_AUTONOMOUS`

## Hallazgos bloqueantes

1. `orchestration/mission_controller/router.py` no compilaba por una expresión
   inválida en la resolución de ROOT. Esto impide importar el Mission Controller.
2. No existe `.github/workflows/` en el commit auditado: no hay gate remoto
   que detecte regresiones de sintaxis antes de considerar una entrega válida.
3. `.hermes-state/gate_evidence.json` afirmaba que
   `data/materialized/v2/ai_outcome_v2_full.jsonl.manifest` estaba completo,
   pero el archivo no existe en el árbol del commit.
4. La certificación documentaba una raíz de seis elementos; GitHub muestra 37
   entradas en la raíz del commit.
5. El commit añadió dos registros `OPEN` al blackbox mecánico durante una
   entrega titulada como cleanup. Esos eventos no son evidencia de readiness y
   deben tratarse como estado operativo/test, no como gate científico.
6. No existe en el commit el materializador temporal solicitado
   `scripts/lab/experiments/mt_temporal_episode_materializer.py` ni tests
   `test_temporal_episode_*`. El problema 292/292 sigue sin una solución
   materializada/certificada.
7. El Mission Controller tiene persistencia, routing, recover, adapters y gates,
   pero no existe todavía un supervisor continuo que ejecute
   PLAN→DELEGATE→OBSERVE→VERIFY→RECOVER de punta a punta sin intervención.

## Componentes rescatables

- MissionStore atómico y event log append-only.
- MissionController fail-closed para completar tareas sin evidencia.
- Adapter CLI/HTTP para OpenCode.
- Recovery de sesiones/misiones.
- Engram como sink de cierre.
- Separación `can_trade=false` / `training_eligible=false`.

## Gates para autonomía

La siguiente promoción requiere, en orden:

```text
AUTONOMY-G0  repository syntax/CI green
AUTONOMY-G1  provider registry/config resolved without repo secret/config coupling
AUTONOMY-G2  supervisor loop durable + restart/recovery
AUTONOMY-G3  automatic evidence collection + executable test gates
AUTONOMY-G4  temporal episode dataset ICT+Wyckoff certified
AUTONOMY-G5  baseline temporal OOS
AUTONOMY-G6  GRU only if incremental OOS value
AUTONOMY-G7  shadow autonomous operation
AUTONOMY-G8  trading remains separately gated
```

Until G7, the system may automate research/orchestration but is not autonomous
for market execution. Trading activation is explicitly out of scope.
