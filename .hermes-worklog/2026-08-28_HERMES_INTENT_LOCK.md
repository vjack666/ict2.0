# Corrección de deriva de objetivo de Hermes

- **Fecha:** 2026-08-28
- **Agente:** Hermes / gobierno
- **Estado:** COMPLETED — corrección documental acotada
- **Objetivo:** evitar que tareas de configuración, datos, arquitectura,
  documentación o auditoría se conviertan automáticamente en búsqueda de edge.

## Hallazgo

`.hermes.md` define a Hermes como ejecutor, investigador y experimentador; el
plan activo mantiene el carril de laboratorio; y `docs/00_HERMES_START_HERE.md`
incluye backtest/evaluation en el ciclo científico. Además, el Mission Controller
dispone de router por intención, pero `start_hermes.py` solo ejecuta el bootstrap
de auditoría y no usa ese router. El comportamiento efectivo queda por tanto
sesgado por las directivas generales y el plan activo.

## Decisión

El objetivo literal de la misión actual tiene precedencia. `INVESTIGAR EDGE` es
un modo opt-in: requiere solicitud explícita o un protocolo científico vigente.
El plan, la memoria y los worklogs aportan contexto, pero no amplían el alcance.

## Cambios

- `.hermes.md`: Mission Brief, precedencia de objetivo y bloqueo de deriva.
- `docs/00_HERMES_START_HERE.md`: guardia para activar el plan solo con la orden
  explícita y separación del carril científico.
- `governance/ORQUESTADOR.md`: regla normativa de enrutamiento por intención.
- `.hermes-index.md`: estado de la corrección.

## Verificación

- Lectura de los documentos de gobierno, índice, worklogs recientes, memoria y
  Mission Controller.
- No se modificó `engine/`, `data/`, `datasets/`, `lab/` ni resultados científicos.
- No se ejecutaron experimentos, backtests, entrenamiento ni promoción.
- Pendiente posterior: conectar el Mission Controller al entrypoint si se desea
  enforcement ejecutable; esta corrección no inventa esa integración.

## Siguiente acción

Usar el Mission Brief en cada misión y, en una tarea separada, diseñar y probar
la integración del router con el entrypoint local.
