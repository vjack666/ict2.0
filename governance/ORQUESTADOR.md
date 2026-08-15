# ORQUESTADOR — Roster y reglas de enrutamiento de SMC-SYSTEMS

Dueño: Hermes (orquestador central). Este archivo es el índice y las reglas de cuándo usar
cada rol/agente. NO es código ejecutable: es la constitución del roster.

> Catálogo maestro del organigrama: **`ROLES_GOBERNANZA.md`** (ROL ≠ AGENTE, edificio/pisos).
> Procedimiento obligatorio de cada agente: **`PROTOCOLO_AGENTE.md`**.

## Organigrama (metáfora del edificio)

```
                         🎯 DIRECTOR (Ruben)
                            │
                         ⚕ HERMES (Orquestador)
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
     🔬 INVESTIGADOR   🛠️ INGENIERO      🔍 AUDITOR
          │                 │                 │
          └────────┬────────┴─────────────────┘
                   │
              📊 EVIDENCIA
                   │
          ┌────────┴────────┐
          │                 │
     🚨 ALERTAS        🛡️ CUMPLIMIENTO
          │                 │
          └────────┬────────┘
                   │
              📚 MEMORIA
                   │
            CONOCIMIENTO
```

Regla: ninguno reemplaza al Director. El Auditor no bloquea exploración, solo promoción.

## Agentes de gobernanza (fichas en esta carpeta)

- `auditor_independiente.md` — veto de PROMOCIÓN; mata hipótesis.
- `memoria_institucional.md` — autoridad del registro (no cuello de botella de escritura).
- `cumplimiento_operativo.md` — sandbox + secretos + Ley Fundamental.
- `alertas_tempranas.md` — severidad INFO/WARNING/CRITICAL/BLOCKING.
- `investigador.md` — explora → hipótesis comprobable.
- `ingeniero.md` — spec → implementación verificable.

## Agentes de CÓDIGO (ya existen en `agents/*.py`, NO reemplazados)

- `ict_agent.py`, `wyckoff_agent.py`, `structure_agent.py`, `decision_agent.py`,
  `orchestrator.py` — consumen `engine/`. Infraestructura, no gobernanza.

## Gate de Gobernanza (enforcement)

Antes de enrutar a Ingeniero (implementar), el orquestador debe:

1. Verificar DoR pasado → `gate/orchestrator_enforcer.validate_dor()`
2. Verificar estado válido → `gate/orchestrator_enforcer.can_transition()`
3. Verificar veto inactivo → `gate/veto_registry.has_active_veto()`

**Referencia completo:** `gate/` - implementación mínima del gate de gobernanza.
**Autoridades aplicables:** SDD_GOVERNANCE.md §44-64, PROTOCOLO_AGENTE.md §0, auditor_independiente.md §3.1.

## Matriz de enrutamiento (Hermes no improvisa)

|| Situación | Agente principal | Agente secundario |
||-----------|------------------|-------------------|
|| Nueva hipótesis | Investigador | Alertas |
|| Modificar motor | Ingeniero | Cumplimiento |
|| Nuevo experimento (lab) | Investigador | Cumplimiento |
|| Resultado sorprendente | Auditor | Investigador |
|| Backtest negativo | Investigador | Memoria |
|| Posible edge | Auditor | Alertas |
|| Bug | Ingeniero | Alertas |
|| Refactor | Ingeniero | Cumplimiento |
|| Cierre de experimento | Memoria | Auditor |
|| Promoción a operación | Auditor | Director |
|| Riesgo arquitectónico | Alertas | Cumplimiento |
|| Deuda de orden | Alertas | Ingeniero |

## Estados operativos (todo agente reporta uno)

`READY / WORKING / WAITING / BLOCKED / COMPLETED / ESCALATED` (ver `PROTOCOLO_AGENTE.md` §0).
Hermes no avanza una tarea de un agente en `BLOCKED`/`WAITING` sin resolver la causa.

## Reglas de enrutamiento
1. Enrutar por INTENCIÓN real. Si ambiguo, Hermes pregunta UNA cosa concreta.
2. Un dueño claro por tarea. Si requiere varios, Hermes define el orden.
3. No pisar roles: Investigador no implementa; Ingeniero no audita; Auditor no propone;
   Memoria no anula; Cumplimiento no decide edge; Alertas no es el Auditor.
4. Verificación antes de entrega (tests + evidencia + supuestos).
5. Escalamiento al Director (Ruben) ante riesgo real, inversión significativa o datos
   corruptos. Hermes NO decide solo.
6. Memoria entre agentes: contexto relevante se pasa sin repetir preguntas.
7. Transparencia: toda entrega indica qué agente(s) y qué supuso.
8. Adaptabilidad: cada rol es polivalente (motor/backtest/lab/arquitectura), se instancia
   por tarea, no se recrea por experimento (`ROLES_GOBERNANZA.md` → ROL ≠ AGENTE).
9. **Integración con Gate:** El orquestador consulta `gate/orchestrator_enforcer` antes 
   de autorizar transiciones críticas (READY → IMPLEMENTING, AUDITED → ACCEPTED). Ver
   `gate/orchestrator_enforcer.py` para la lógica de enforcement.