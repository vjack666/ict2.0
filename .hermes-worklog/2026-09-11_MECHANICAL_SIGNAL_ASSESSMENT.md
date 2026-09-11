# 2026-09-11 — Respuesta explicable del productor mecánico

**AGENTE:** Codex principal
**DEPARTAMENTO:** D2 Ingeniería / D5 Assurance / D1 Documentación
**TAREA:** eliminar la ambigüedad de `snapshot=null` sin fabricar una señal
automática.
**STATUS:** COMPLETED para Fase 1 diagnóstica; Fase 2 automática BLOCKED.

## Resultado

`MechanicalBotService.analyze()` publica `signal_assessment` junto al campo
histórico `snapshot`. Cuando no existe `latest_snapshot.json`, la respuesta es
completa y estable:

```json
{
  "status": "NO_SIGNAL",
  "code": "MECHANICAL_PRODUCER_UNAVAILABLE",
  "entry_authorized": false
}
```

Incluye detalle, campos requeridos, campos observados, campos faltantes cuando
el payload es inválido y la siguiente condición concreta. La interfaz muestra
esta respuesta antes de los seis gates de readiness.

## Límites preservados

- No se genera `BUY`, `SELL`, probabilidad, `confirmed` ni
  `latest_snapshot.json`.
- `engine.can_trade=false` y `entry_authorized=false` permanecen invariantes.
- Una señal con forma válida se etiqueta `CANDIDATE_SIGNAL`; readiness conserva
  la única autoridad de entrada.
- La IA diagnóstica, `direction_hint`, microconfirmación y sigmoide sin
  calibración no se conectan al consumidor.

## Evidencia

- `python -m pytest tests/test_mechanical_bot_service.py
  tests/test_desktop_terminal.py tests/test_desktop_snapshot_health.py -q`
  → **68 passed**.
- `npm run build` en `runtime/desktop_terminal/ui` → **PASS**.
- `python -m py_compile mechanical_bot/service.py` → **PASS**.
- `git diff --check` → **PASS**.

## Fase 2 bloqueada por contrato

El SDD nuevo `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md` establece que
un productor automático requiere reglas deterministas congeladas, definición
causal de confirmación, probabilidad calibrada con TRAIN/VALIDATION/OOS,
FULL/PREFIX, provenance, gate de edge y auditoría D5. Sin esos elementos no se
convierte contexto en señal ni se habilita una orden DEMO.

## Siguiente acción

Diseñar y preregistrar la estrategia determinista de Fase 2, o utilizar el
modo manual asistido ya especificado para pruebas DEMO de transporte.
