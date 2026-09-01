# Contrato — MTF Replay Orchestrator v1

**Estado:** IMPLEMENTADO — M0–M9 PASS TÉCNICO SINTÉTICO

**Fecha:** 2026-09-01

**Owner técnico:** D2 Ingeniería

**Auditor:** D5 Assurance

**Consumidor:** `backtest/` y visor local

**Modo:** `LOCAL_ONLY`, `diagnostic_only=true`, `can_trade=false`

## 1. Propósito y frontera

El orquestador reproduce en orden causal el estado del sistema sobre barras
cerradas de varias temporalidades. Consume autoridades de `engine/` y genera un
artefacto visual/auditable. No detecta de nuevo, no optimiza, no aprende, no
envía órdenes y no promociona reglas.

`engine/` nunca importa `backtest/`. `backtest/` puede consumir APIs públicas
de `engine/`.

## 2. Perfil de capas

Todo run declara explícitamente:

```text
htf       = contexto y autoridad superior
itf       = zona/estructura intermedia
exec_tf   = disparo, entry, SL y TP
refine_tf = opcional; observación más fina sin autoridad superior
```

Perfiles iniciales:

| profile_id | HTF | ITF | EXEC | Refinamiento | Uso |
|---|---|---|---|---|---|
| `INTRADAY_H4_M15` | H4 | M15 | M15 | ninguno | Intradía normativo. |
| `INTRADAY_H4_M15_M5_REFINEMENT` | H4 | M15 | M5 | M5 | Entrada fina pre-registrada; M5 no mata H4/M15. |
| `SCALP_H1_M5_M1` | H1 | M5 | M1 | M1 | Futuro; no se habilita en el primer incremento. |

Un perfil no puede cambiar durante una corrida. Añadir otro exige contrato o
config versionada y pruebas; nunca selección post-hoc por resultado.

## 3. Reloj causal normativo

Para cada `close_time=t`:

1. `CLOSE_BATCH`: reunir solo barras cerradas con `close_time == t`.
2. `APPLY_AUTHORITY`: aplicar transiciones por TF de mayor a menor.
3. `SNAPSHOT`: congelar `MarketState.projection_at(t)`.
4. `DECISION`: construir setups y Episodes desde ese snapshot.
5. `EXECUTION`: evaluar triggers únicamente si eran observables y tradables.
6. `EMIT`: escribir deltas, rechazos y referencias de evidencia.

Una decisión creada en el batch `t` no puede entrar usando un precio anterior
a su `tradable_time`. Por defecto tampoco usa la misma barra que la confirmó;
el primer fill elegible pertenece a una barra EXEC posterior. Cualquier modelo
de fill distinto debe pre-registrarse.

## 4. Autoridad e invalidación

- Una observación LTF no cambia el estado oficial de un objeto HTF.
- Si el setup se invalida antes del fill: `CANCELLED_BEFORE_ENTRY`.
- Si cambia de candidato por lineage: `SUPERSEDED_BEFORE_ENTRY`.
- Si ya existe trade abierto, la invalidación superior se registra como
  `AUTHORITY_INVALIDATION_AFTER_ENTRY`; v1 mantiene la política SL/TP/horizonte
  congelada. Salir por esa invalidación requiere otro perfil pre-registrado.
- Outcome no puede cambiar retroactivamente la validez que existía en `t`.

## 5. Artefacto visual 2.0

El artefacto debe declarar:

```text
schema_version = "2.0"
artifact_kind  = "MTF_REPLAY"
run_metadata
policy
profiles
candles_by_tf
timeline
market_state_checkpoints
state_deltas
setups
episodes
invalidations
trades
rejections
checksum
```

Todo registro temporal incluye `observation_time`, `confirmation_time` cuando
aplique, `authority_tf`, `source_refs` y un ID estable. El checksum excluye
campos volátiles como `generated_at`.

El visor puede seguir leyendo 1.1/1.2 como históricos, pero 2.0 es la salida
vigente. El visor muestra evidencia; no reconstruye decisiones.

## 6. Razones canónicas mínimas

```text
MISSING_LAYER
MISSING_CLOSED_BAR
OUT_OF_ORDER_EVENT
FUTURE_DATA
INVALID_AUTHORITY
BROKEN_LINEAGE
NOT_TRADABLE
CANCELLED_BEFORE_ENTRY
SUPERSEDED_BEFORE_ENTRY
AMBIGUOUS_FILL
RESOURCE_LIMIT
```

## 7. Reproducibilidad y recursos

- Orden total estable: `(close_time, tf_rank, event_kind, stable_id)`.
- Entrada idéntica + config idéntica + commit idéntico = checksum idéntico.
- Procesamiento streaming; no materializar todos los prefijos.
- Checkpoints configurables y reanudación con hash de entrada/config.
- El visor carga por ventanas; el JSON completo puede dividirse en manifiesto y
  chunks deterministas.

## 8. Gates

| Gate | PASS requerido |
|---|---|
| M0 Contrato | documentos enlazados y revisión D5. |
| M1 Schema | validación 2.0, IDs y lineage negativos incluidos. |
| M2 Clock | orden determinista y pruebas de timestamps simultáneos. |
| M3 Causalidad | FULL/PREFIX exacto en varios cortes y ambas direcciones. |
| M4 Autoridad | LTF no invalida HTF; rollback superior correcto. |
| M5 Lifecycle | cancelación, supersession y post-entry separados. |
| M6 Determinismo | dos runs iguales, checksum lógico igual. |
| M7 Viewer | cursor nunca muestra evidencia futura; build/test local PASS. |
| M8 Recursos | run pequeño acotado, checkpoint/reanudación equivalentes. |
| M9 Auditoría | auditor independiente emite GO técnico. |

## 9. No equivalencias

`M0–M9 PASS` no equivale a edge, rentabilidad, entrenamiento IA, promoción ni
autorización MT5. Cada una pertenece a su gate científico u operativo.

## 10. Evidencia de implementación 2026-09-01

- Auditoría: `reports/audits/mtf_replay/mtf_replay_audit.json`.
- Dos perfiles: `INTRADAY_H4_M15` y
  `INTRADAY_H4_M15_M5_REFINEMENT`.
- FULL/PREFIX: 10/25/50/75/90 % PASS en ambos perfiles.
- Determinismo, checkpoint/resume y chunk-size invariance: PASS.
- Suite Python: 464 pruebas PASS tras la última autoauditoría.
- Visor: 3 pruebas PASS, build Vite PASS y `npm audit` con 0 vulnerabilidades.
- Alcance: fixture sintético únicamente; T7 real permanece sin autorización.
