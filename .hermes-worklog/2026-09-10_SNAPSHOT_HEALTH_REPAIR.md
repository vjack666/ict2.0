# Snapshot canónico disponible y vigente — auditoría y reparación

AGENTE: Codex principal; diagnóstico independiente inicial ict_assurance.
DEPARTAMENTO: D2 Ingeniería / D7 Delivery; revisión D5.
TAREA: auditar y reparar el mensaje de snapshot canónico ausente en ICT Terminal.
STATUS: READY — código verificado; activación en el proceso principal pendiente.

## Causa comprobada

La API de 127.0.0.1:8790 publica un motor READY con análisis
MT5_OPERATIONAL_SNAPSHOT_V1 y seis TF. El publicador del bot exige direction,
probability, confirmed, asof_time y symbol. El análisis de lectura no tiene ese
contrato; el publicador elimina latest_snapshot.json y el servicio comunica
SNAPSHOT_MISSING. El texto de la UI confundía ausencia de señal con ausencia de
análisis. Evidencia local previa en .hermes-state/snapshot-audit-baseline/before.json.

## Cambios

- canonical_snapshot_health independiente en cada respuesta HTTP, incluso en
  transporte incremental: esquema, símbolo, política, estado, reloj con zona,
  edad máxima 180 s y cierre de cada TF anterior o igual a decision_time.
- Feed no vigente, fallo del motor o TF vencida bloquean la salud. RUNNING puede
  conservar el análisis previo solo si sigue cumpliendo todos los controles.
- Reintentos del motor con espera exponencial 5–60 s; recuperación de pool roto;
  fallo de submit identificado como error del motor; una única tarea pendiente.
- Interfaz diferencia análisis válido/vigente de señal operable pendiente,
  incluidos los requisitos de entrada y el resumen de cuenta.
- No se crea probabilidad, dirección, confirmación ni señal. No se modifica el
  servicio mecánico, sus gates ni cambios previos de estocástico intrabarra.

## Evidencia y autoauditoría

- 32 passed: tests/test_desktop_snapshot_health.py y tests/test_desktop_terminal.py.
- npm run build: PASS, Vite y empaquetado local.
- Graphify actualizado por AST local: 14229 nodos y 23676 aristas; sin APIs.
- Validación con payload real del servicio: PASS; antigüedad observada 13.9 s,
  decision_time 2026-09-10T23:58:00+00:00, can_trade=false y entry_authorized=false.
- Inspección visual previa en navegador confirmó exactamente el mensaje reportado.
- D5 independiente confirmó causa y separación segura de contratos. La revisión
  independiente final del diff no se completó: ambos agentes agotaron su límite
  de uso. Autoauditoría del principal realizada con pruebas y payload real.
- Cambios concurrentes en Git durante la misión: HEAD llegó a 5fb9d15; contiene
  un snapshot mecánico añadido por otro trabajo. Ese archivo ya estaba ausente
  en runtime por el publicador existente; no se incluye su borrado en el commit.

## Límite operativo y siguiente acción

Dos intentos de reinicio fueron rechazados automáticamente por política:
primero conservando execution-enabled y después en modo lectura. La herramienta
solo informó blocked by policy, sin razón más específica. Ninguno ejecutó cambios
de procesos. La instancia principal verificada era PID 10500, bot OFF, sin ciclo,
execution_enabled=true. No se armó el bot ni se enviaron órdenes en esta misión.

El bundle está compilado; el backend activo aún no expone el canal nuevo.
Falta autorizar/aplicar un reinicio del servicio y verificar la UI contra el
backend actualizado. No declarar COMPLETED operativo antes de esa comprobación.
El snapshot de lectura sigue sin constituir señal mecánica ni certificación
histórica. Conservar los gates y no hacer push.
