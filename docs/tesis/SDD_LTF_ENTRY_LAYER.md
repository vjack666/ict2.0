# SDD — Capa LTF / EXEC de lectura canónica

**Versión:** 2.0  
**Estado:** NORMATIVO para LTF-READING; no contiene contrato de ejecución  
**Fecha:** 2026-08-20  
**Fuente de autoridad:** `docs/ict/SPEC_TESIS_FORMAL.md` + libros ICT 16/18  
**Plan:** `docs/tesis/PLAN_LTF_ENTRY_LAYER.md`  
**Padre MTF:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`  
**Contratos relacionados:** `docs/contratos/CONTRATO_MULTI_TF_LAYERS.md`, `docs/contratos/CONTRATO_AHF.md`, `docs/CONTRATO_CONTEXT_STATE.md`

## 1. Propósito

Definir una capa LTF/EXEC que observe y confirme el estado de mercado después de que HTF/ITF hayan emitido contexto y restricciones. La capa debe conectar la tesis con el motor real sin duplicar detectores, lineage ni máquinas de estados.

```text
Context State       != entry
SETUP_READY         != order
LTF confirmation    != fill
```

La capa LTF es **subordinada** al estado confirmado de sus ancestros. No redefine D1/H4, no convierte un snapshot en una orden y no utiliza datos posteriores a `decision_time`.

---

## 2. Roles temporales

### Perfil diario vigente

```text
HTF     = D1
ITF     = H4
CONTEXT = H1
EXEC    = M15
```

`CONTEXT=H1` es una capa intermedia del perfil diario actual; no sustituye el contrato universal `htf/itf/exec_tf`.

### Extensión de tesis

```text
D1 → H4 → H1 → M15 → M5 → M1
```

M5/M1 pueden actuar como confirmación fina/microestructura, pero requieren perfil explícito y todos los gates de este SDD antes de promoción.

---

## 3. Autoridad de cada nivel

```text
HTF Context State
   ↓
AHF / navigation state
   ↓
ITF structure + POI
   ↓
Sequence / FVG / OB / lineage
   ↓
EXEC-LTF confirmation
   ↓
zone/retest observation
```

Reglas:

1. HTF emite `direction_hint`, `location`, `regime_stack`, `constraints` y referencias de liquidez/POI cuando estén disponibles.
2. ITF interpreta estructura y zonas dentro del contexto HTF.
3. EXEC/LTF solo confirma/espera respecto de las restricciones heredadas.
4. LTF no cambia `direction_hint` de D1/H4.
5. Rollback de una capa superior se realiza mediante AHF, no mediante mutación local de LTF.
6. El historial de navegación nunca se borra.

---

## 4. Entrada del componente

La interfaz lógica es:

```python
build_daily_motor_snapshot(
    frames,
    decision_time,
    config,
) -> snapshot
```

`config` debe declarar explícitamente:

```text
profile_id
htf
itf
context_tf
exec_tf
```

No se permite inferir roles por nombre de variable, orden de diccionario o existencia de un único `ltf`.

El adaptador puede recibir además, siempre como datos de solo lectura de sus
fuentes de autoridad:

```text
canonical_zones      # MarketObject FVG/OB por timeframe
sequence_snapshot   # refs/depth de Sequence canónica
navigation_snapshot  # snapshot/evento producido por AHF
context_snapshot     # Context State/POI ya resuelto
```

La capa LTF no construye esos objetos, no ejecuta otra FSM y no convierte
marcadores legacy del DataFrame en evidencia canónica.

La entrada de LTF requiere, cuando existan:

```text
Context State locked
POI refs
Sequence refs/depth
parent navigation state
active_tf
```

---

## 5. Regla `as-of(t)` / PIT

Definición única:

```text
as_of(tf, t) = última barra de tf con time ≤ t
```

Para cualquier snapshot:

```text
asof_time[HTF]    ≤ t
asof_time[ITF]    ≤ t
asof_time[CONTEXT]≤ t
asof_time[EXEC]   ≤ t
```

No se permite:

- usar una vela posterior a `t`;
- centrar un pivote con barras futuras;
- recalcular un ancestro usando evidencia posterior;
- mezclar relojes para favorecer una confirmación;
- cambiar un snapshot histórico al añadir datos posteriores.

La detección LTF estructural debe ejecutarse sobre el prefijo `time <= t` antes de cualquier cálculo derivado.

---

## 6. Salida canónica

El snapshot debe ser serializable y contener como mínimo:

```text
{
  policy: OBSERVE_ONLY_NO_ORDER,
  profile_id,
  htf_tf,
  itf_tf,
  context_tf,
  exec_tf,
  decision_time,
  asof_times_by_tf,

  navigation: {
    state,
    active_tf,
    parent_state,
    transition_event,
    transition_time,
    invalidation_reason
  },

  context: {
    direction_hint,
    location,
    regime_stack,
    constraints,
    poi_refs
  },

  sequence: {
    refs,
    depth
  },

  ltf: {
    available,
    structure,
    direction_compatible,
    confirmation_state,
    zone_refs,
    retest_state,
    retest_time
  },

  lineage_refs,
  entry_authorized: false
}
```

Los nombres pueden adaptarse a la implementación, pero la semántica no puede cambiarse sin actualizar este SDD y el contrato/plan relacionados.

---

## 7. Estados observacionales

Los estados mínimos son:

```text
NO_LTF_DATA
WAIT_CONTEXT
WAIT_LTF_CONFIRMATION
WAIT_LTF_ZONE
WAIT_RETEST
OBSERVABLE_SETUP
```

### Reglas

`NO_LTF_DATA`:
- no existe una barra EXEC válida en `as-of(t)`;
- no debe inventarse confirmación.

`WAIT_CONTEXT`:
- falta Context State válido o un ancestro necesario no está locked;
- LTF no puede promover el estado por sí solo.

`WAIT_LTF_CONFIRMATION`:
- contexto válido;
- estructura LTF aún no confirma compatibilidad suficiente.

`WAIT_LTF_ZONE`:
- estructura compatible;
- no existe una zona FVG/OB/POI canónica activa y tradable/observable.

`WAIT_RETEST`:
- zona válida;
- todavía no existe un touch/mitigation/retest canónico observable.

`OBSERVABLE_SETUP`:
- contexto válido;
- navegación compatible;
- estructura LTF compatible;
- zona canónica resuelta;
- retest canónico observado según las reglas vigentes;
- no significa entry ni fill.

---

## 8. FVG / OB / Sequence: autoridad y lineage

### 8.1 FVG/OB

LTF no debe convertir columnas arbitrarias del DataFrame en “verdad de zona”. Una zona válida debe resolver a un objeto/ref producido por los detectores canónicos y, cuando corresponda, a su `CausalLink`/lineage.

### 8.2 Sequence

Cuando la tesis/plan requiera secuencia, LTF consume la Sequence canónica. No debe volver a implementar:

```text
LIQUIDITY_POOL → SWEEP → DISPLACEMENT → STRUCTURE → OB → FVG → RETEST
```

El snapshot puede exponer `sequence_refs` y `depth`, pero la construcción de la cadena pertenece a su fuente canónica.

### 8.3 Zona

Una zona expuesta por LTF debe poder responder:

```text
zone_id
zone_type
origin_tf
candidate_time
confirmation_time
tradable_time
parent_refs
lineage_refs
state
```

### 8.4 Retest

`retest_state` solo puede pasar a observado cuando exista evidencia canónica de touch/mitigation/retest. Un string como `ACTIVE`, por sí solo, no es evidencia de retest.

La implementación conserva `legacy_zone_marker` y `legacy_retest_marker`
únicamente para auditoría de compatibilidad. Esos campos no pueden llenar
`zone_refs`, `retest_state` ni promover el snapshot.

---

## 9. Integración con AHF

LTF no implementa otra máquina jerárquica. Consume la máquina `engine.ahf`.

La navegación esperada es:

```text
WAIT_D1
  ↓
D1_LOCKED
  ↓
WAIT_H4
  ↓
H4_LOCKED
  ↓
WAIT_H1
  ↓
WAIT_LTF
  ↓
SETUP_READY
```

Dentro de `WAIT_LTF`, el SDD LTF puede distinguir:

```text
WAIT_CONTEXT
WAIT_LTF_CONFIRMATION
WAIT_LTF_ZONE
WAIT_RETEST
OBSERVABLE_SETUP
```

pero esas distinciones no crean estados padres nuevos de AHF.

### Rollback

Ejemplos válidos:

```text
H1_INVALIDATED → WAIT_H1
H4_INVALIDATED → WAIT_H4
D1_INVALIDATED → WAIT_D1
```

El evento debe conservar:

```text
state
active_tf
parent_state
transition_event
transition_time
invalidation_reason
```

LTF nunca debe escribir directamente un nuevo `D1_LOCKED` o `H4_LOCKED`.

---

## 10. Autoridad de dirección

La dirección LTF se evalúa como **compatibilidad**, no como nuevo bias normativo.

Ejemplo conceptual:

```text
D1 direction = BULLISH
H4 constraints = compatible
LTF trend = BULLISH
    → compatible

D1 direction = BULLISH
H4 constraints = compatible
LTF trend = BEARISH
    → WAIT_LTF_CONFIRMATION
```

Un LTF contrario no puede cambiar:

```text
D1 direction
H4 locked context
Context State direction_hint
```

Si la tesis o AHF requieren una invalidación superior, debe utilizarse el mecanismo superior documentado, no una inversión silenciosa desde LTF.

---

## 11. Integridad temporal de la cadena de setup

Para cualquier candidato histórico:

```text
candidate_time
≤ confirmation_time
≤ tradable_time
≤ ltf_confirmation_time
≤ retest_time
```

No se puede considerar un retest anterior a la creación/tradabilidad de la zona.

Si en algún punto la implementación no puede determinar el orden temporal, el snapshot debe degradar a `NO_EVIDENCE`/`WAIT_*` y dejar un finding auditable.

---

## 12. No-look-ahead y truncation invariance

Debe cumplirse:

```text
snapshot(prefix_to_t, t)
==
snapshot(full_series, t)
```

para toda información que pertenezca al pasado de `t`.

Casos obligatorios:

1. agregar futuro solo a HTF;
2. agregar futuro solo a ITF;
3. agregar futuro solo a EXEC;
4. agregar futuro a todos;
5. reordenamiento equivalente permitido por el contrato de datos.

Una diferencia histórica constituye fallo hasta ser explicada por una regla explícita de snapshot.

---

## 13. No duplicación de lógica

La siguiente tabla es normativa:

| Concepto | Fuente única esperada | LTF puede recalcularlo |
|---|---|---|
| BOS/CHOCH | `engine.bos` / `engine.plan` | No |
| Context State | `engine.mtf_navigation` | No |
| AHF state | `engine.ahf` | No |
| FVG | detector canónico | No |
| OB | detector canónico | No |
| Lineage | `engine.lineage` | No |
| Sequence | `engine.sequential_events` / fuente canónica | No |
| Presentación LTF | adaptador LTF | Sí |
| Estado `WAIT_*` LTF | adaptador según este SDD | Sí |

La capa LTF puede transformar/normalizar datos de esas fuentes, pero no puede redefinir su semántica.

---

## 14. Perfil M15 actual

El perfil diario actual es:

```text
D1  → Context State
H4  → estructura / POI
H1  → contexto intermedio / sequence
M15 → confirmación / zona / retest
```

Esto es un **perfil**, no una regla universal para toda la tesis.

Antes de introducir otro perfil, el agente debe declarar:

```text
profile_id
htf
itf
context_tf
exec_tf
purpose
required_data
```

Y debe ejecutar de nuevo los gates PIT, lineage, determinismo y autoridad de capas.

---

## 15. Datos ausentes y degradación

La ausencia de un TF no permite inventar sustitutos.

Ejemplos:

```text
M15 ausente
  → NO_LTF_DATA / modo degradado explícito

FVG/OB ausente
  → WAIT_LTF_ZONE

Context State ausente
  → WAIT_CONTEXT

Retest no demostrado
  → WAIT_RETEST
```

No se permite convertir `UNKNOWN` en `PASS` mediante defaults silenciosos.

---

## 16. Seguridad de interfaz

Este SDD prohíbe que el componente LTF de lectura exponga una ruta de ejecución. No debe generar ni aceptar como salida normativa:

```text
order
fill
broker
position
sizing
entry_authorized=True
```

`OBSERVABLE_SETUP` no es una señal de broker.

---

## 17. Tests obligatorios

### PIT

- future-only HTF;
- future-only ITF;
- future-only EXEC;
- future-all;
- comparación exacta de snapshots históricos.

### Autoridad

- LTF contrario no cambia el bias heredado;
- M5/M1 no reescriben D1/H4;
- rollback solo por AHF;
- `SETUP_READY` no crea orden.

### Lineage

- toda zona resuelve a objeto;
- todo retest resuelve a zona/POI padre;
- cero ciclos;
- cero links a futuro;
- timestamps monotónicos.

### Retest

- zona sin touch → espera;
- touch no canónico → no promoción;
- retest canónico + contexto compatible → observable;
- invalidación superior → rollback.

### Determinismo

Mismo dataset + commit + configuración → mismo snapshot.

La salida del adaptador se normaliza a tipos JSON, ordena referencias y
expone los cuatro `asof_times_by_tf` del perfil diario.

### API

El test debe fallar si aparece `entry_authorized=True` o una ruta de `order/fill/sizing`.

---

## 18. Observabilidad y auditoría

Cada snapshot debe permitir reconstruir:

```text
HTF
  direction/location/regime

ITF
  structure/POI

Sequence
  depth/refs

LTF
  structure/confirmation/zone/retest/status

AHF
  state/active_tf/parent_state/transition_event
```

Cuando falte evidencia, el sistema debe conservar el vacío y la causa. No se permiten explicaciones retroactivas.

---

## 19. Gates de aceptación

### Gate LTF-1

PASS cuando:

- snapshot serializable;
- PIT probado;
- `entry_authorized=False`;
- integración del brief sin lógica paralela;
- determinismo sintético.

**Avance verificado:** los tests sintéticos de `tests/test_daily_motor.py`
cubren schema, futuro HTF/ITF/EXEC, serialización, determinismo, autoridad
LTF, zona canónica y retest. La suite completa pasa, pero el gate LTF-1 sigue
pendiente de evidencia histórica versionada y de la integración con las
fuentes productivas de Context State/AHF.

### Gate LTF-2

PASS cuando:

- FVG/OB son objetos canónicos;
- `active_zone_refs` resuelven;
- candidate/confirmation/tradable son temporales;
- retest proviene de estado canónico;
- Sequence/lineage son trazables;
- cero duplicación de FSM.

### Gate LTF-3

PASS cuando:

- LTF consume AHF;
- rollback es determinista;
- parent state e invalidation reason quedan registrados;
- LTF no reescribe ancestros.

### Gate LTF-4

PASS cuando:

- perfil histórico D1→H4→H1→M15 reproducible;
- truncation invariance PASS;
- cero PIT violations;
- cobertura de estados documentada;
- reporte versionado.

### Gate LTF-5

No se abre hasta que LTF-4 esté PASS y existan datos M5/M1 suficientes y versionados.

---

## 20. Estado de cierre

**Estado actual:** `LTF-READING IMPLEMENTADA / LTF-1 EN PROGRESO / LTF-2 INTERFAZ INICIADA / LTF-3..4 PENDIENTES`.

Este estado no implica fallo del motor. Significa que el adaptador existe, pero aún no tiene toda la evidencia requerida para declararse un componente LTF canónico completo según la tesis.

**Criterio final:** LTF Reading queda cerrada solo cuando la lectura `Context State → ITF POI → LTF structure → zone → retest` es íntegramente trazable, PIT, determinista y subordinada a AHF.

La ejecución (`entry/SL/TP/fill`) requiere otro SDD y otro gate.
