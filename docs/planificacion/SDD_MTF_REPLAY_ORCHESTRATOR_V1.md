# SDD — MTF Replay Orchestrator v1

**Estado:** DISEÑO AUTORIZADO; implementación pendiente

**Contrato:** `docs/contratos/CONTRATO_MTF_REPLAY_ORCHESTRATOR_V1.md`

**Auditoría base:** `docs/planificacion/AUDITORIA_COBERTURA_MTF_REPLAY_V1.md`

## 1. Misión

Construir el puente causal que permita observar cómo un contexto H4 habilita
una zona M15, cómo una ejecución M15 o M5 aparece, espera, se invalida o entra,
y cómo se resuelve después; todo barra por barra y visible en el visor local.

## 2. Arquitectura

```text
frames cerrados por TF
        ↓
backtest/mtf_replay.py        reloj y coordinación, sin detección
        ↓
engine authorities           lifecycle → MarketState → SetupBuilder → Episodes
        ↓
engine.sequential_outcome     desenlace posterior, separado
        ↓
backtest/schema.py 2.0        validación + serialización/chunks
        ↓
visor local                  solo lectura y cursor as-of T
```

## 3. Componentes y write sets previstos

| Componente | Acción | Write set |
|---|---|---|
| Orquestador | nuevo | `backtest/mtf_replay.py` |
| Schema | extender 1.0 y conservar compatibilidad | `backtest/schema.py` |
| Adaptador/export | extender | `scripts/export_visual_backtest.py` |
| Visor | portar UI mínima y añadir schema 2.0 | `backtest/viewer/**` |
| Auditoría | nuevo | `audits/codigo/mtf_replay.py` |
| Tests | nuevos/focales | `tests/test_mtf_replay*.py` |

Está prohibido portar del worktree histórico `backtest/market_state.py`,
`backtest/setup_builder.py` o detectores equivalentes. Solo se rescata la UI y
utilidades de lectura que pasen auditoría de dependencia.

## 4. Máquina de tiempo

El motor usa un merge ordenado de iteradores por TF. En cada timestamp procesa
un batch completo y crea una barrera entre hechos, snapshot, decisión y fill.
Esto elimina el resultado dependiente del orden accidental del DataFrame.

```text
CLOSE_BATCH(t)
  → APPLY_AUTHORITY(HTF→LTF)
  → FREEZE_SNAPSHOT(t)
  → BUILD_SETUP_EPISODE(t)
  → CHECK_EXECUTION(after tradable_time)
  → EMIT_DELTA(t)
```

## 5. Ciclo de un setup

```text
CANDIDATE
  ├─ BLOCKED / OUT_OF_CONTEXT
  ├─ SUPERSEDED_BEFORE_ENTRY
  ├─ CANCELLED_BEFORE_ENTRY
  └─ ELIGIBLE → WAIT_RETRACE → FILLED
                              ├─ TP
                              ├─ SL
                              └─ OPEN_AT_HORIZON
```

Una invalidación post-entry se conserva como evidencia independiente. En v1 no
cambia por sí sola el fill ni simula una salida discrecional.

## 6. Perfiles y evolución

El primer incremento implementa `INTRADAY_H4_M15`. El segundo añade
`INTRADAY_H4_M15_M5_REFINEMENT` usando el mismo reloj. M5 es ejecución fina en
ese perfil, no una autoridad capaz de reescribir H4 o M15. Scalping queda fuera
hasta que los dos primeros perfiles pasen M0–M9.

## 7. Optimización de recursos

1. Iteradores por TF y ventanas acotadas, no producto cartesiano de frames.
2. Deltas en cada barra; snapshot completo cada `checkpoint_every` eventos.
3. Chunks por mes o tamaño con manifiesto y checksum.
4. Cache derivada solo por `(dataset_hash, config_hash, code_commit)`.
5. Reanudación valida esos tres hashes antes de continuar.
6. Viewer con carga perezosa alrededor del cursor.

El primer smoke usa datos sintéticos. La primera corrida real, si recibe GO
separado, será un mes; veinte años no son criterio de aceptación del software.

## 8. Pruebas obligatorias

- cierre simultáneo H4/M15/M5 en distinto orden de entrada;
- objeto H4 observado e invalidado falsamente desde M15/M5;
- setup cancelado antes del fill;
- invalidación de autoridad después del fill;
- parent/child futuro, huérfano, ciclo y duplicado;
- fill en la vela de confirmación rechazado por defecto;
- misma entrada/config con chunking distinto produce mismo checksum lógico;
- checkpoint + resume equivale a corrida continua;
- FULL/PREFIX en 10/25/50/75/90 % y cortes sobre transiciones;
- visor en cursor T no muestra estado, outcome ni explicación de T+1.

## 9. Definition of Done

Implementación completa significa M0–M9 PASS, suite sin regresiones, artefacto
sintético reproducible, visor local funcional, bitácora e índice sincronizados
y commit local selectivo. No requiere ni permite declarar edge.
