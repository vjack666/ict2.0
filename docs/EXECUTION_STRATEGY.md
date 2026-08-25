# Estrategia de ejecución — ICT 2.0

**Decisión:** 2026-08-25
**Estado:** VIGENTE — LOCAL ONLY
**Responsable:** Hermes/Codex desde el checkout operativo

## 1. Regla general

Todos los tests, auditorías, experimentos, backtests, walk-forwards, descargas,
jobs de laboratorio y scripts de terminal se ejecutan exclusivamente desde:

```text
C:\Users\v_jac\Desktop\ICT SYSTEM
```

El repositorio remoto queda limitado a código, historial, revisión y publicación
autorizada. No se usa ningún servicio remoto como host de ejecución.

## 2. Procedimiento local obligatorio

Antes de ejecutar:

1. abrir PowerShell en el checkout operativo;
2. leer `AGENTS.md`, `.hermes-index.md`, el último worklog, el SDD/plan aplicable,
   Engram y Graphify;
3. comprobar `git status --short`, dataset, hash y permisos de la tarea;
4. ejecutar únicamente el comando autorizado por el plan;
5. guardar logs, JSON/Markdown, hashes y evidencia en el repositorio local;
6. autoauditar el resultado y corregir faltantes antes del cierre;
7. actualizar bitácora, Engram y Graphify;
8. crear commit local selectivo; no hacer push sin auditoría independiente.

## 3. Comandos locales de referencia

```powershell
Set-Location 'C:\Users\v_jac\Desktop\ICT SYSTEM'
python -m pytest tests/
python scripts/audit/tna_20y_parallel.py
python audits/codigo/full_stack.py
git status --short
```

Los comandos son referencias y no autorizan por sí mismos la ejecución de un
experimento o backtest. Cada corrida requiere su contrato, SDD, dataset y permiso.

## 4. Clasificación de carga

La carga pesada no se migra a otro host. Si el PC no puede completar una tarea,
el estado correcto es `WAITING` o `BLOCKED`; Hermes debe documentar el motivo y
esperar una decisión del usuario.

## 5. Estado de trabajos

| Trabajo | Estado | Fuente de verdad |
| --- | --- | --- |
| Funnel FVG/OB + Sequence + MTF | Cerrado según evidencia versionada | `reports/audits/experiments/fvg_ob/` |
| TNA TRACE | Según reporte auditado | `reports/audits/temporal/` |
| TNA behavioral/full-span | Según reporte auditado y reproducibilidad local | `reports/audits/temporal/tna_20y.json` |
| SEQUENCE × CONTEXT | `INSUFFICIENT_N` / según índice vigente | reportes de experimentos |
| Backtest / walk-forward | `BLOCKED` hasta gates aceptables | `.hermes-index.md` |

## 6. Historial

Los reportes que mencionan hosts remotos documentan ejecuciones pasadas. No son
procedimientos vigentes, no autorizan repetir esas corridas y no deben usarse como
destino de ejecución.
