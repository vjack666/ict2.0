# PLAN — Capa LTF de lectura del motor diario

**Estado:** ACTIVO — Lectura de mercado únicamente
**Fecha:** 2026-08-20
**Fuente normativa:** `docs/ict/16_TEMPORALIDAD_EJECUCION.md`, `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`, `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`
**SDD:** `docs/tesis/SDD_LTF_ENTRY_LAYER.md`

## 1. Hallazgo inicial

No existía un plan ni un SDD dedicado a la capa LTF. El repositorio sí contenía:

- la jerarquía HTF/ITF/EXEC en los libros ICT 16 y 18;
- el contexto MTF/AHF en `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`;
- piezas LTF dispersas en `engine/plan.py`, `engine/sequence.py` y `engine/plan_driver.py`;
- un brief diario que explícitamente decía que no emitía señales ejecutables.

Este documento y su SDD cierran el hueco documental para lectura de mercado.
La ejecución, entry, SL y TP están fuera de alcance y no se implementarán aquí.

## 2. Objetivo

Conectar la lectura LTF al motor diario respetando la cadena:

```text
HTF: contexto / sesgo / liquidez
  -> ITF: estructura / zona
  -> EXEC-LTF: confirmación / zona activa / estado de retest
```

La implementación entrega un snapshot auditable de observación. No entrega
entry, SL, TP, fill ni autorización operativa.

## 3. Configuración operativa inicial

| Perfil | HTF | ITF | Contexto | EXEC/LTF |
| --- | --- | --- | --- | --- |
| Intradía diario | D1 | H4 | H1 | M15 |
| Scalping futuro | M15/H1 | M5 | — | M5/M1 |

El perfil implementado en esta fase es **intradía diario D1→H4→H1→M15**.
M5/M1 permanecen disponibles como extensión, pero no se promocionan sin datos,
pruebas y evidencia propios.

## 4. Fases y gates

### LTF-0 — Contrato y auditoría de integración

- Crear este plan y `SDD_LTF_ENTRY_LAYER.md`.
- Declarar el motor diario canónico y separar legado de autoridad.
- Mantener `Context State ≠ entry` y `SETUP_READY ≠ order`.

**Gate:** documentación consistente y sin OTE/Fibonacci.

### LTF-1 — Snapshot LTF conectado al motor diario

- Implementar `engine.daily_motor.build_daily_motor_snapshot`.
- Usar únicamente barras cerradas `as-of(t)`.
- Exponer estado de contexto, estructura LTF, zona/retest y razón de espera.
- Conectar el snapshot al brief diario.

**Gate:** tests sintéticos de contrato y no-look-ahead; el snapshot nunca
contiene una orden.

### LTF-2 — Lectura secuencial y estado de zonas

- Consumir `engine.sequence` como fuente de secuencia/lineage cuando se use para
  lectura histórica.
- Exponer estados de zona y retest solo como observación.
- No duplicar la máquina de estados en el brief ni en un agente.

**Gate:** tests temporales y de lineage; ninguna salida de ejecución.

### LTF-3 — Validación de lectura

- Comparar baseline sin LTF, LTF de confirmación y secuencia con retest
  únicamente como lecturas de estado.
- Usar split temporal/OOS cuando el dataset lo permita.
- No declarar edge por un snapshot o por un gate formal.

**Gate:** evidencia reproducible, métricas y auditoría documentadas.

## 5. Fuera de alcance permanente de este plan

- No emitir órdenes ni señales ejecutables.
- No calcular entry, SL, TP, fill, sizing o gestión de posición.
- No conectar brokers, backtests de ejecución ni walk-forward de ejecución.
- No reintroducir OTE, Fibonacci, EMA o ATR como gate normativo.
- No reactivar `ict_backtest/`.
- No declarar que M1 mejora M5 sin experimento comparativo.
- No desbloquear el backtest antes de los gates A0-A9, Funnel y TNA.

## 6. Archivos de implementación

| Rol | Archivo |
| --- | --- |
| Contrato de diseño | `docs/tesis/SDD_LTF_ENTRY_LAYER.md` |
| Adaptador del motor diario | `engine/daily_motor.py` |
| Pruebas | `tests/test_daily_motor.py` |
| Consumidor diario | `scripts/brief_lunes.py` |
| Secuencia canónica futura | `engine/sequence.py` |

## 7. Criterio de cierre de lectura LTF

LTF-1 solo puede marcarse `PASS` cuando:

1. el snapshot funciona con frames sintéticos;
2. datos futuros HTF/LTF no cambian el resultado en `t`;
3. el perfil diario devuelve estado y razón explicables;
4. `entry_authorized` no forma parte de una API ejecutable y, en el snapshot
   de compatibilidad, es siempre `False`;
5. el brief deja de inventar una señal y muestra el estado LTF real;
6. el índice maestro y el worklog reflejan el cambio;
7. no existe ninguna dependencia de ejecución para usar esta lectura.
