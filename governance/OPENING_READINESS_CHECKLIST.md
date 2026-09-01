# Checklist de preparación para apertura — ICT 2.0

**Objetivo:** certificar la infraestructura antes de la próxima sesión de mercado.

**Alcance de fin de semana:** solo controles de código, gobierno, memoria, trazabilidad y datos existentes. No se ejecutan órdenes, señales operativas, experimentos nuevos ni promoción.

La comprobación ejecutable es `python scripts/opening_readiness.py`. Es local, de solo lectura y devuelve código distinto de cero si algún gate bloquea la apertura.

## Gate previo a la apertura

- [ ] `audits.codigo.bootstrap` pasa y `audit_score >= 0.80`.
- [ ] `architecture_guard.py` pasa.
- [ ] Tests de departamentos y Mission Controller pasan.
- [ ] El Mission Controller puede crear, enrutar, reconciliar y cerrar una misión sin completar sin evidencia.
- [ ] Engram registra el cierre institucional sin sustituir el estado durable.
- [ ] Graphify está actualizado y no presenta una desconexión organizativa crítica.
- [ ] El motor de IA permanece en Shadow Mode con `can_trade=false`.
- [ ] No existen cambios de dataset ni promoción pendientes sin aprobación.
- [ ] Git identifica claramente los cambios que deben revisarse antes de commit/push.

## Primera comprobación al abrir el mercado

- [ ] Confirmar sesión, zona horaria y feed disponible.
- [ ] Confirmar frescura, continuidad y procedencia de los datos.
- [ ] Ejecutar lectura HTF/LTF en modo observación.
- [ ] Confirmar que no hay señal accionable ni ejecución automática habilitada.
- [ ] Registrar el brief de apertura en `.hermes-worklog/`.

## Regla de bloqueo

Cualquier fallo de auditoría, trazabilidad, datos, permisos, PIT/leakage, deriva/OOD o estado `can_trade` desconocido bloquea la operación y escala a D0/CRO. Un resultado histórico o diagnóstico no constituye autorización de promoción.
