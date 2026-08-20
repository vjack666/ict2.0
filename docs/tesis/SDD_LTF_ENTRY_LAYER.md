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
`reports/audits/wyckoff_runtime_inventory_2026-08-20.md`; este estado no es un
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
