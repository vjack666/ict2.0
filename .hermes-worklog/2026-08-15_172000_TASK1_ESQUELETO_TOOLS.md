# Bitácora — Task 1: Esqueleto tools/base.py + tools/event.py

**Fecha:** 2026-08-15 17:20 UTC-5
**Plan:** `.hermes/plans/2026-08-15_143000-individual-tools-m5-learning.md` (Fase 1, Task 1)
**Decisiones cerradas:** baseline 50% · calificación humana por .md · subir código+AUDIT_REQUEST+learning.

---

## Objetivo
Definir la interfaz común que TODA herramienta individual cumplirá en Fase 1.

## Archivos creados
- `tools/__init__.py` — paquete tools.
- `tools/event.py` — `ToolEvent` (dataclass: bar_index, time, symbol, tf, tool_name, signal, detail, confidence_raw, extra, human_score vía log).
- `tools/base.py` — `SingleTool` (ABC): `run(df, symbol, context) -> list[ToolEvent]`; envuelve detector en `_detect` + `_to_events`; escribe log append-only jsonl a `data/learning/<tool>/<sym>_M5_<mes>.jsonl` con `human_score=None` (pendiente de calificación humana).

## Verificación
Smoke test con `.venv/Scripts/python.exe` (pandas 3.0.5):
- `SingleTool()` lanza TypeError (abstracta, no instanciable sin `_detect`/`_to_events`) ✓
- `ToolEvent.to_dict()` serializa señal/nombre ✓
- `LEARNING_DIR` = `C:/Users/v_jac/Desktop/ICT SYSTEM/data/learning` ✓

## Notas
- El venv del PROYECTO es `ICT SYSTEM/.venv` (Python 3.11, pandas 3.0.5). El Python del sistema (3.14) tiene numpy roto (cp311/cp314) → no usar para pandas.
- El log de aprendizaje se activa en `run()`; el agente trader humano llena `human_score` editando el .md de muestra (Task 11/13c, Fase 2).
- `import pandas` en `base.py` es diferido solo al importar el módulo; los detectores reales lo usarán.

## Siguiente
Task 2: `tools/swing.py` (primera herramienta individual real, base de la plantilla vela-a-vela).
