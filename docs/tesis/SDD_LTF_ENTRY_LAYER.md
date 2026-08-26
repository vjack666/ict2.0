# SDD — Capa LTF / EXEC + Wyckoff especializada

**Versión:** 3.0  
**Estado:** NORMATIVO para lectura de mercado; no contiene contrato de ejecución  
**Fecha:** 2026-08-20  
**Autoridad:** `docs/ict/SPEC_TESIS_FORMAL.md` + ICT 16/18  
**Plan:** `docs/tesis/PLAN_LTF_ENTRY_LAYER.md`  
**Padre MTF:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`  
**Contratos:** `CONTRATO_MULTI_TF_LAYERS.md`, `CONTRATO_AHF.md`, `CONTRATO_CONTEXT_STATE.md`  
**Biblioteca Wyckoff:** `docs/reglas/WYCKOFF_RULEBOOK.md`, `docs/wyckoff/**`

**Estado de implementación:** `WYCKOFF-0 PASS / WYCKOFF-1..2 IN PROGRESS /
WYCKOFF-3..4 PARTIAL / WYCKOFF-5 PENDING`. La evidencia de inventario está en
`reports/audits/runtime/wyckoff_runtime_inventory_2026-08-20.md`; este estado no es un
PASS final del motor.

## 1. Propósito

Definir una única lectura top-down ICT/MTF/LTF en la que Wyckoff sea una capa especializada de interpretación del proceso de mercado.

```text
Context State       != entry
Wyckoff state       != entry
SETUP_READY         != order
LTF confirmation    != fill
```

La capa Wyckoff no es un segundo motor. No crea otro AHF, otro Context State, otra FSM de Sequence ni otra definición de FVG/OB.

## 2. Perfil temporal

Perfil diario:

```text
HTF     = D1
ITF     = H4
CONTEXT = H1
EXEC    = M15
```

Extensión de tesis:

```text
D1 → H4 → H1 → M15 → M5 → M1
```

Autoridad Wyckoff:

| TF | Responsabilidad | Autoridad |
|---|---|---:|
| D1 | fase/regimen macro | 4 |
| H4 | rango/causa/transición | 3 |
| H1 | confirmación de proceso | 2 |
| M15 | comportamiento local | 1 |
| M5/M1 | microcontexto | 0 / diferido |

`authority_tf` debe ser explícito en todo `WyckoffSnapshot`.

## 3. Contrato de entrada

La capa puede recibir solamente snapshots/objetos producidos por fuentes de autoridad:

```text
context_state        ← engine.mtf_navigation
navigation_snapshot  ← engine.ahf
POI/MarketObject     ← detectores canónicos
sequence_snapshot    ← engine.sequential_events
lineage              ← engine.lineage
OHLC prefix          ← feed as-of(t)
```

No debe consultar directamente un agente legacy para decidir estado canónico si existe el adaptador runtime.

## 4. Contrato de salida Wyckoff

```text
WyckoffSnapshot {
  phase
  phase_state
  authority_tf
  range_ref
  events[]
  evidence_refs[]
  effort_result
  volume_mode
  ict_alignment
  conflict
  explanation
}
```

### `phase`

```text
ACCUMULATION
MARKUP
DISTRIBUTION
MARKDOWN
RANGE_UNCLASSIFIED
TRANSITION
UNKNOWN
```

### `phase_state`

```text
PRO_TREND
COUNTERTREND
TRANSITION
NEUTRAL
```

### Eventos

```text
SPRING
UPTHRUST
UTAD
SOS
SOW
LPS
LPSY
TEST
FAILED_TEST
RANGE_BREAK
EFFORT_RESULT_DIVERGENCE
```

Cada evento debe contener, como mínimo:

```text
event_id
event_type
tf
event_time
source_ref
evidence_refs
confirmation_status
```

## 5. Definición semántica de la capa

Wyckoff responde:

> “¿Qué proceso de oferta/demanda/rango está describiendo el mercado?”

ICT responde:

> “¿Qué estructura, liquidez, POI y confirmación existen?”

La integración responde:

> “¿La lectura ICT ocurre a favor del proceso Wyckoff, contra él o durante una transición?”

No se exige que ambos sistemas produzcan la misma etiqueta.

## 6. Mapeos autorizados

Estos son **analogías operativas**, no equivalencias matemáticas:

```text
Spring/reclaim       ↔ liquidity sweep + reclaim
Spring + Test        ↔ CHOCH/MSS bullish
SOS                   ↔ bullish displacement/BOS
LPS                   ↔ pullback/retest hacia POI
UTAD/rejection       ↔ BSL sweep + bearish rejection
SOW                   ↔ bearish displacement/BOS
LPSY                  ↔ bearish pullback/retest
```

La capa debe conservar qué evidencia pertenece a cada sistema.

## 7. Clasificación ICT/Wyckoff

### `PRO_TREND`

Usar cuando el proceso Wyckoff y la dirección/estructura ICT son compatibles.

Ejemplo:

```text
D1/H4 bearish
Wyckoff markdown/distribution
ICT bearish structure
```

### `COUNTERTREND`

Usar cuando Wyckoff sugiere acumulación/markup contra un contexto bajista o distribución/markdown contra uno alcista y existe evidencia inicial ICT compatible con la transición.

Ejemplo:

```text
D1 bearish
H4 accumulation + Spring/SOS
H1/M15 bullish confirmation
```

`COUNTERTREND` nunca autoriza entry.

### `TRANSITION`

Hay indicios de cambio de fase pero la estructura ICT todavía no confirma la nueva dirección.

### `NEUTRAL`

Wyckoff no tiene evidencia suficiente. No se debe inventar sesgo ni penalizar artificialmente la lectura ICT.

## 8. Política de conflicto

```text
ICT bullish + Wyckoff bearish
   → conflict = true
   → phase_state = COUNTERTREND o TRANSITION
   → mantener direction_hint ICT
   → esperar/elevar evidencia LTF según plan
```

No permitido:

```text
Wyckoff bearish → direction_hint = BEARISH
Wyckoff bearish → AHF rollback
Wyckoff bullish → bloquear shorts
```

Solo AHF puede realizar rollback de una capa superior y solo con evidencia contractual de AHF.

Wyckoff nunca genera `entry_authorized=True`.

## 9. Volumen y esfuerzo/resultado

`tick_volume` de MT5 es evidencia relativa del feed, no volumen centralizado del mercado FX.

```text
volume_mode = AVAILABLE | UNAVAILABLE | RELATIVE_ONLY
```

Sin volumen:

```text
volume_mode = UNAVAILABLE
```

No se permite fabricar una confirmación de volumen.

ATR, si aparece por la implementación histórica, solo puede servir para normalización de rango/esfuerzo. No puede transformarse en bias/veto. EMA, OTE y Fibonacci están fuera de la capa normativa.

## 10. Integración con LTF

El flujo obligatorio es:

```text
D1 Context State
      ↓
H4 ITF / POI
      ↓
H1 context / Sequence
      ↓
Wyckoff D1/H4/H1 evidence
      ↓
M15 ICT structure
      ↓
FVG/OB canonical zone
      ↓
touch / retest
      ↓
WAIT_* / OBSERVABLE_SETUP
```

Wyckoff puede aportar:

```text
phase_state
conflict
context explanation
required evidence level
```

pero no puede sustituir:

```text
Context State
Sequence
FVG/OB
lineage
LTF confirmation
```

## 11. Integración con AHF

El AHF sigue siendo la única máquina jerárquica:

```text
WAIT_D1 → D1_LOCKED → WAIT_H4 → H4_LOCKED → WAIT_H1 → WAIT_LTF → SETUP_READY
```

Wyckoff se ejecuta como lectura dentro del snapshot de la capa activa.

No crear estados padre Wyckoff.

Si Wyckoff detecta transición o conflicto, debe expresarlo en datos:

```text
wyckoff.conflict
wyckoff.phase_state
wyckoff.authority_tf
```

No escribir directamente:

```text
D1_LOCKED
H4_LOCKED
WAIT_H4
WAIT_D1
```

## 12. PIT

Regla única:

```text
as_of(tf,t) = última vela cerrada con time <= t
```

Todo detector Wyckoff debe recibir el prefijo de datos disponible en `t`.

Debe cumplirse:

```text
candidate/event/phase confirmation times <= decision_time
```

Y:

```text
wyckoff(prefix_to_t,t) == wyckoff(full_series,t)
```

para campos históricos.

## 13. Fuente única de conceptos

| Concepto | Fuente de autoridad |
|---|---|
| BOS/CHOCH | `engine.bos` / `engine.plan` |
| Context State | `engine.mtf_navigation` |
| AHF | `engine.ahf` |
| FVG/OB | detectores canónicos / `MarketObject` |
| Sequence | `engine.sequential_events` |
| Lineage | `engine.lineage` |
| Wyckoff phase/events | `engine/Wyckoff/` |
| Presentación | `daily_motor` / `brief_lunes.py` |

Si el código legacy y el motor canónico producen estados diferentes, el agente debe detener la promoción, registrar el conflicto y resolver la autoridad documental antes de marcar PASS.

## 14. Migración de legacy

`analysis/wyckoff_agent.py` debe tratarse como fuente candidata/legacy hasta concluir auditoría.

`agents/wyckoff_agent.py` y cualquier `orchestrator` antiguo no pueden seguir siendo la autoridad silenciosa del brief.

Cuando haya consumidores existentes:

```text
legacy import
   ↓
compat wrapper
   ↓
engine/Wyckoff canonical API
```

Cuando no haya consumidores, eliminar después de documentar la migración.

## 15. Seguridad de interfaz

El componente LTF/Wyckoff no debe exponer:

```text
order
fill
broker
position
sizing
entry_authorized=True
```

`OBSERVABLE_SETUP`, `PRO_TREND` y `COUNTERTREND` son estados de lectura.

## 16. Tests obligatorios

### Inventario/migración

- cero imports funcionales a una implementación duplicada;
- wrappers legacy comprobados;
- todos los consumidores identificados.

### Wyckoff

- fase con ventanas sintéticas;
- Spring/Upthrust;
- SOS/SOW;
- LPS/LPSY;
- esfuerzo/resultado;
- ausencia de volumen;
- autoridad temporal.

### Integración

- Context State → Wyckoff → LTF;
- PRO_TREND;
- COUNTERTREND;
- TRANSITION;
- NEUTRAL;
- conflicto sin mutar direction_hint;
- AHF sin segunda FSM;
- retest/lineage intactos.

### PIT/determinismo

- future-only HTF;
- future-only ITF;
- future-only M15;
- future-all;
- prefix invariance;
- mismo dataset+commit+config → mismo snapshot.

## 17. Observabilidad

El brief debe poder explicar:

```text
HTF:
  direction / location / regime

ITF:
  structure / POI

Wyckoff:
  phase / phase_state / authority_tf
  events / evidence / conflict

Sequence:
  depth / refs

LTF:
  structure / zone / retest / status
```

Si falta evidencia, usar `UNKNOWN`, `NEUTRAL` o `WAIT_*` con causa. Nunca rellenar huecos para producir una lectura más convincente.

## 18. Gate de aceptación

`PASS` solo cuando:

1. inventario de código/documentación/historia completo;
2. `engine/Wyckoff/` o equivalente es la única autoridad runtime;
3. biblioteca `docs/wyckoff/**` conserva y documenta el conocimiento;
4. `WyckoffSnapshot` se integra al snapshot LTF sin segundo motor;
5. `authority_tf` explícito;
6. PRO_TREND/COUNTERTREND/TRANSITION/NEUTRAL reproducibles;
7. conflictos transparentes y no bloqueantes por defecto;
8. cero look-ahead;
9. lineage/timestamps resolubles;
10. tests de migración/integración/PIT/determinismo PASS;
11. brief semanal+diario muestra la capa;
12. worklog final y commits trazables.

**Este PASS es de arquitectura/lectura. No demuestra edge, PnL ni rentabilidad.**

## 19. WYCKOFF-7 — Fases canónicas + CME 6E

Esta sección formaliza la extensión CME `6E` sin crear una segunda FSM. Su
estado inicial es `DRAFT — REVIEW PENDING`; no autoriza implementación,
descarga de datos ni experimentos.

### 19.1 Secuencias y FSM

```text
Acumulación: PS → SC → AR → ST → FASE_B → SPRING → TEST → SOS → LPS → MARKUP
Distribución: PSY → BC → AR → ST → FASE_B → UTAD → TEST → SOW → LPSY → MARKDOWN
```

La representación canónica de la secuencia Wyckoff es un evaluador de
transiciones por `range_id`, subordinado a AHF/Context State; no es una FSM de
orquestación hermana. AHF continúa siendo la única FSM jerárquica autorizada.
El evaluador no crea estados AHF, no cambia `direction_hint`, no genera
órdenes y no convierte una fase en autorización de entrada.

Los tokens se clasifican así: `PS/SC/AR/ST/PSY/BC/SPRING/TEST/UTAD/SOS/SOW/
LPS/LPSY` son eventos observables; `FASE_B` es un estado de construcción de
causa; y `MARKUP/MARKDOWN` son estados de régimen posteriores a la confirmación. La
tabla de transición y el rulebook deben resolver cada token antes de declarar
`WYCKOFF-7 PASS`; un token ausente se registra como `NOT_OBSERVED`,
`INVALIDATED` o `UNAVAILABLE_EVIDENCE`, nunca se salta silenciosamente.

Cada transición conserva:

```text
range_id, episode_id, from_state, event_type, to_state,
appeared_at, confirmed_at, invalidated_at,
source_ref, evidence_refs[], reason
```

`appeared_at` es el primer instante observable con el prefijo; `confirmed_at`
es el instante en que se satisface la regla causal. Toda confirmación debe ser
`<= decision_time`. Saltos incompatibles, eventos sin rango y evidencia no
resoluble son inválidos. Las invalidaciones se conservan como registros y
retiran la transición del estado activo.

Cada rango conserva límites, periodo, frontera, timeframe y
`dataset_snapshot_hash`; `episode_id` identifica un subepisodio causal dentro
del rango. La unidad inferencial primaria será `range_id`: un solo outcome por
rango, sin rangos solapados. Para validarlo se ordena por
`(symbol, venue, timeframe, range_start)` y se rechaza si
`next.range_start < previous.range_end_exclusive`, usando intervalos
`[range_start, range_end_exclusive)` y deduplicando antes los mismos
`range_id`. Rangos de distintos timeframes se agrupan y no son independientes.
`episode_id` sirve para lineage y auditoría, no para multiplicar observaciones.
El ancla del rango es el primer PS/PSY
observable; su cierre es la invalidación terminal o la confirmación de
MARKUP/MARKDOWN. Marcos correlacionados, duplicados y eventos derivados no
cuentan como muestras independientes.

Los fixtures mínimos deben demostrar rangos adyacentes aceptados, solapados
rechazados, duplicados deduplicados y rangos abiertos censurados/no inferibles.

### 19.2 Contrato de datos CME

Cada evento debe identificar símbolo/contrato, venue, mes, timestamp/zona
horaria, sesión, política de rollover, OHLCV, volumen, open interest,
`range_id` y `episode_id`.

```text
CME_CENTRALIZED   volumen CME con procedencia verificable
TICK_VOLUME_PROXY conteo relativo explícito, no volumen centralizado
UNAVAILABLE       volumen ausente o no verificable
```

`open_interest=null` con `open_interest_status=UNAVAILABLE` es obligatorio si
la fuente no lo entrega; nunca se imputa ni se sustituye por ticks. ICT y
Wyckoff conservan referencias y timestamps separados: sus correspondencias
son analogías operativas, no equivalencias ni veto/orden. El open interest
debe conservar `published_at`/`available_at`; no se une a una barra antes de
su disponibilidad. La unión `6E ↔ EURUSD` debe tener `join_id`, timezone UTC,
clave temporal normalizada, tolerancia explícita, estado de match y lineage
de ambos registros.

Los valores históricos `AVAILABLE` y `RELATIVE_ONLY` solo son aliases de
entrada: `RELATIVE_ONLY` se serializa como `TICK_VOLUME_PROXY`;
`AVAILABLE` solo puede mapear a `CME_CENTRALIZED` si hay venue/contrato y
procedencia CME verificables, y en caso contrario degrada a `REVIEW` o
`UNAVAILABLE`.

**Gate WYCKOFF-7:** `PASS` requiere evaluador Wyckoff único subordinado a la
FSM jerárquica AHF, secuencias, timestamps, invalidaciones, rango, volumen/OI,
lineage ICT separado y tests causales.
Ambigüedad acotada es `REVIEW`; autoridad duplicada, procedencia insuficiente
o look-ahead es `BLOCKED`.

## 20. WYCKOFF-8 — Certification / Preflight

WYCKOFF-8 define la certificación documental y PIT previa a cualquier
ejecución futura. No descarga datos, no entrena IA y no ejecuta
`EXP-WYCKOFF-CANONICAL-02`.

El manifest debe contener versión, `dataset_snapshot_id`/hash, archivos con
SHA-256/esquema/cobertura/filas, símbolo/venue/contrato, timeframes,
timezone/sesiones/roll, `volume_mode`, fuente OI, `config_canonical_hash`,
`code_commit`, `generator_commit`, comando generador, worktree/rama,
procedencia, rangos, episodios, fecha y `evidence_refs`. Commits resolubles,
datos declarados y hashes de bytes/configuración exactos son obligatorios.

La certificación debe comparar:

```text
FULL   = serie completa del snapshot certificado
PREFIX = prefijo cerrado disponible en decision_time
wyckoff(PREFIX, decision_time) == wyckoff(FULL, decision_time)
```

La comparación correcta es una proyección histórica:

```text
snapshot_at(FULL, t) == snapshot_at(PREFIX, t)
```

Solo se comparan datos y transiciones observables hasta `t`; una invalidación
conocida después de `decision_time` no puede retroescribir el snapshot
histórico. La igualdad cubre fase/estado, `range_id`, `episode_id`,
timestamps, invalidaciones visibles y refs. Dataset, configuración,
dependencias y commit iguales en checkout limpio deben producir el mismo
manifest, evaluador, eventos y hashes.

| Gate | Criterio |
|---|---|
| `PASS` | manifest completo, hashes/commits resolubles, PIT/FULL-PREFIX causal, determinismo clean e independencia declarada |
| `REVIEW` | ambigüedad documental acotada, sin afirmar certificación |
| `BLOCKED` | falta/inconsistencia de datos o procedencia, look-ahead, no determinismo o rango/episodio irresoluble |

Este PASS certifica documentación, trazabilidad y reproducibilidad del
artefacto; no demuestra edge, PnL, rentabilidad, entrenamiento, ejecución ni
promoción.
