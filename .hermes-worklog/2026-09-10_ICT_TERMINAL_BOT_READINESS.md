# 2026-09-10 — Readiness explicable del bot en ICT Terminal

AGENTE: Codex principal + `ict_viewer_builder`; auditor independiente `ict_assurance`.
DEPARTAMENTO: D2 Ingeniería / D7 Delivery; verificación D5 Assurance.
TAREA: sustituir el bloqueo ambiguo de armado por requisitos de entrada visibles.
STATUS: COMPLETED.

## Resultado

- `Armar bot · iniciar loop` queda separado de la autorización de entrada.
- El servicio publica seis gates con código y detalle: ejecución, snapshot válido
  y edad máxima 20 minutos, dirección, probabilidad mínima 70 %, confirmación
  estocástica M15 sobre velas cerradas y sesión Londres/Nueva York.
- ICT Terminal habilita siempre el gate de sesión; las ventanas son
  `[08:00,12:00)` en la zona local de cada plaza, con weekday y DST.
- JSON malformado, NaN, snapshot futuro/stale y fallo de velas M15 quedan visibles
  y bloquean readiness. El frontend falla cerrado si falta el contrato.
- El tick conserva la revalidación autoritativa antes de ejecutar. El motor
  canónico permanece `can_trade=false`; el panel no es señal ni promoción.

## Evidencia

- Focal Python: `69 passed` en core, servicio, adaptador MT5 y terminal.
- Frontend: Vite build correcto; Sites worker `4 passed`.
- QA local `127.0.0.1:8791`: conexión DEMO en lectura, ejecución deshabilitada,
  panel `NO LISTO` con seis filas y causa exacta; no se armó el bot ni se envió
  ninguna orden.
- Auditoría D5: `COMPLETED / READY` para integración, sin promoción.

## Archivos

`mechanical_bot/service.py`, `scripts/start_desktop_terminal.py`,
`runtime/desktop_terminal/ui/src/{App.jsx,styles.css}`,
`tests/test_mechanical_bot_{service,mt5_adapter}.py`,
`tests/test_desktop_terminal.py`, SDD, índice y reglas UI.

## Riesgos y siguiente acción

El checkout contiene cambios previos ajenos a esta misión; el commit debe ser
selectivo y no absorberlos. Una cuenta con `execution_enabled=true` sigue
requiriendo armado humano y todos los gates dentro del tick. No hacer push.
