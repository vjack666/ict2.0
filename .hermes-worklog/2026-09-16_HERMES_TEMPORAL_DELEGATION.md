# Delegacion autonoma del plan temporal

AGENTE: Codex, coordinacion de entrega; ejecutores Hermes existentes.
DEPARTAMENTO: D0 con D2/D3/D4/D5/D6/D1.
TAREA: actualizar plan y delegar trabajo autonomo solicitado por Ruben.
STATUS: WORKING (programa cientifico); asignacion y despacho inicial realizados.

## Evidencia

- `hermes profile list` y SOUL locales: Forge coordina, Nexus datos, Helix IA,
  Probe experimentos, Orion investigacion, Vigil auditoria, Sentinel gates,
  Ledger trazabilidad. No se cambian perfiles ni modelos.
- Tablero dedicado `ict-temporal-v1`: 11 tarjetas con padres, goal loop de
  20 turnos, 2h por intento y limite de 2 fallos consecutivos.
- `dispatch --max 3 --json`: spawned Forge t_794063cd, Nexus t_0b2b2423,
  Orion t_24fddd4f. `runs` y `list` confirman running al comprobar arranque.
- Logs iniciales advierten Unknown toolsets: a2a. No se afirma trabajo
  cientifico completado ni comunicacion A2A operativa.
- Seguimiento de tarea Codex activo: supervisar-hermes-ict-temporal,
  cada 15 minutos; verificar resultados, despachar elegibles, no busy loop.
- Forge bootstrap se libera al terminar arranque; cierre separado tras Ledger
  evita bloquear la implementacion por concurrencia del mismo perfil.

## Cambios y limites

Plan ampliado con tiempo real de disponibilidad, estados entre velas,
TFs separados, memoria de episodio, corpus continuo en memoria, tensor y
ablations temporales, ejecucion offline y validacion independiente.
Fuentes/datasets/labels/splits/manifiestos existentes permanecen inmutables.
No se confunde entrenamiento exploratorio autorizado con certificacion.
No se toca engine/execution.py ni archivos ajenos. No ordenes ni push.
can_trade=false; entry_authorized=false.

## Riesgos y siguiente accion

Gateway detenido no impidio spawned por CLI. Un worker running no demuestra
respuesta del proveedor ni entrega; verificar logs/artefactos y fallos antes
de continuar. Datos insuficientes pueden impedir entrenamiento concluyente;
no fabricar frecuencia ni PASS. Forge/Vigil deben repetir auditoria despues
de correcciones y documentar resultado negativo cuando corresponda.

ARCHIVOS: plan multimodelo, manifiesto de tareas, indice y esta bitacora.
