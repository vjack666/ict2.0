# SDD — Capa LTF de lectura del motor diario

**Versión:** 1.0
**Estado:** NORMATIVO para lectura LTF; no contiene contrato de ejecución
**Fecha:** 2026-08-20
**Plan:** `docs/tesis/PLAN_LTF_ENTRY_LAYER.md`
**Extiende:** `docs/contratos/CONTRATO_MULTI_TF_LAYERS.md`, `docs/contratos/CONTRATO_AHF.md`

## 1. Propósito

Definir cómo el motor diario observa la capa LTF/EXEC después de que el
contexto HTF/ITF esté disponible. La capa LTF confirma o espera; no cambia el
sesgo HTF y no participa en ejecución de operaciones.

```text
Context State       != entry
SETUP_READY         != order
LTF confirmation    != fill
```

## 2. Roles temporales

El perfil intradía vigente es:

```text
HTF     = D1       contexto, sesgo y liquidez
ITF     = H4       estructura y zona
CONTEXT = H1       confirmación intermedia
EXEC    = M15      timing, zona y retest
```

El perfil no impide perfiles futuros, pero cada perfil debe declarar los cuatro
roles y no asumir que `itf == exec_tf` sin decirlo.

## 3. Entrada del adaptador

`build_daily_motor_snapshot(frames, decision_time, config)` recibe:

- `frames`: `dict[str, pandas.DataFrame]` con columnas OHLC y `time`;
- `decision_time`: timestamp de la última vela cerrada que se quiere evaluar;
- `config`: perfil HTF/ITF/CONTEXT/EXEC explícito.

La función reutiliza `engine.plan.build_context_stack`,
`engine.plan.ltf_structure_at` y `engine.plan.top_down_allows_trade`. No crea
un segundo detector de BOS/CHOCH.

## 4. Regla temporal

Para toda decisión en `t`:

```text
as_of(tf, t) = última barra de tf con time <= t
```

Obligatorio:

1. ninguna barra posterior a `t` entra en un snapshot;
2. el contexto superior se calcula antes de interpretar el LTF;
3. una observación futura no puede cambiar el resultado histórico en `t`;
4. el timestamp devuelto debe ser el cierre observado, no el tiempo de ejecución
   del proceso.

## 5. Salida canónica

El adaptador devuelve un diccionario serializable con, como mínimo:

```text
{
  "policy": "OBSERVE_ONLY_NO_ORDER",
  "entry_authorized": false,
  "status": "WAIT_CONTEXT | WAIT_LTF_CONFIRMATION | WAIT_LTF_ZONE |
             WAIT_RETEST | OBSERVABLE_SETUP | NO_LTF_DATA",
  "decision_time": timestamp,
  "direction": -1 | 0 | 1,
  "context": {"allowed": bool, "reason": str, "stack": {...}},
  "ltf": {
    "tf": str,
    "available": bool,
    "trend": str,
    "bos_dir": int,
    "momentum": int,
    "structure_confirmed": bool,
    "zone_present": bool,
    "retest_observed": bool
  }
}
```

`OBSERVABLE_SETUP` significa únicamente que el contexto y la evidencia LTF
son observables según este adaptador. No significa `ENTRY_READY`, `FILLED` ni
autorización de operación.

## 6. Máquina de estados de observación

```text
NO_LTF_DATA
      │ datos EXEC disponibles
      ▼
WAIT_CONTEXT ── contexto válido ──> WAIT_LTF_CONFIRMATION
                                      │ estructura a favor
                                      ▼
                                  WAIT_LTF_ZONE
                                      │ zona FVG/OB observable
                                      ▼
                                  WAIT_RETEST
                                      │ retest observable
                                      ▼
                              OBSERVABLE_SETUP
```

Una contradicción del contexto superior devuelve `WAIT_CONTEXT`. Un LTF
contrario no invierte la dirección: devuelve `WAIT_LTF_CONFIRMATION`.

## 7. Retest como lectura

En LTF-1 `retest_observed` solo puede ser verdadero cuando el estado de la zona
ya expone una marca explícita de toque/mitigación/retest. La simple existencia
de un FVG u OB no cuenta como retest.

Si se usa la secuencia canónica de `engine.sequence` para análisis histórico,
debe conservar:

```text
candidate_time <= confirmation_time <= tradable_time <= retest_time <= entry_time
```

Esta cadena es temporal y descriptiva; no autoriza entry, SL, TP ni fill. La
ejecución queda fuera de este SDD.

## 8. Integración con el uso diario

`scripts/brief_lunes.py` consume el adaptador y publica la sección
“LTF / exec M15” con estado, dirección, confirmación, zona, retest y razón de
espera. El brief es exclusivamente una lectura de mercado y no una interfaz
de órdenes.

## 9. Seguridad y prohibiciones

- No OTE ni Fibonacci.
- No EMA/ATR como bias o veto normativo.
- No look-ahead cross-timeframe.
- No emitir `entry`, `sl`, `tp`, `order`, `fill`, sizing o gestión de posición.
- No permitir que M15/M5/M1 reescriba D1/H4.
- No usar un `SETUP_READY` del AHF como orden.

## 10. Gates

LTF-1 pasa con:

1. test de salida serializable y `entry_authorized=False`;
2. test de contexto inválido;
3. test de datos futuros ignorados;
4. test de LTF contrario que no invierte dirección;
5. integración del brief sin excepción.

La ejecución no forma parte del alcance de este plan/SDD. Si se solicita en el
futuro, deberá abrirse un plan y contrato separados.
