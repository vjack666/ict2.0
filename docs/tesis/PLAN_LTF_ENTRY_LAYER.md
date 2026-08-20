# PLAN — Capa LTF / EXEC: lectura canónica y futura ejecución

**Estado:** ACTIVO — FASE LTF-READING; ejecución de órdenes permanece fuera de este plan  
**Fecha:** 2026-08-20  
**Fuente de autoridad:** `docs/ict/SPEC_TESIS_FORMAL.md` + libros ICT de temporalidad/ejecución 16 y 18  
**Contexto MTF:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`  
**Contratos:** `docs/contratos/CONTRATO_MULTI_TF_LAYERS.md`, `docs/contratos/CONTRATO_AHF.md`, `docs/CONTRATO_CONTEXT_STATE.md`  
**SDD LTF:** `docs/tesis/SDD_LTF_ENTRY_LAYER.md`

## Objetivo

Construir una capa LTF/EXEC que una correctamente la lectura top-down de la tesis con el motor existente, sin crear una segunda estrategia, una segunda máquina de estados ni una segunda interpretación de FVG/OB/Sequence.

```text
HTF
  ↓
Context State / constraints
  ↓
ITF
  ↓
POI / zona / estructura
  ↓
EXEC-LTF
  ↓
confirmación estructural
  ↓
zona activa / retorno / retest
  ↓
estado observable del setup
```

La ejecución financiera es un contrato separado. Este plan no autoriza órdenes.

## Objetivo de cierre end-to-end — prueba MT5 real

La siguiente prueba de aceptación es normativa para el trabajo autónomo de Codex/Hermes:

> **"Ahora dame una muestra, ya está configurado el MT5 que se va a usar para este proyecto, dame lectura de mercado para esta semana y el día de hoy".**

La IA debe poder responderla usando el feed MT5 real configurado por el proyecto y el mismo motor canónico que alimenta el brief diario, sin inventar datos ni usar una segunda lógica de lectura.

### Condición de éxito

La respuesta debe poder reconstruir, para la semana y para el instante de decisión actual:

```text
MT5 feed
  ↓
D1 Context State
  ↓
H4 ITF / POI / location
  ↓
H1 Context / Sequence
  ↓
M15 LTF structure
  ↓
canonical FVG/OB zone
  ↓
touch / mitigation / retest
  ↓
WAIT_* o OBSERVABLE_SETUP
```

La IA debe demostrar explícitamente:

1. símbolo, broker/servidor y timestamp del feed utilizado;
2. `as_of(t)` independiente para D1/H4/H1/M15;
3. Context State real, no únicamente `trend` D1/H4;
4. relación HTF→ITF→CONTEXT→EXEC en una sola navegación;
5. POI/FVG/OB procedentes de objetos/detectores canónicos, no de marcadores legacy;
6. Sequence y lineage trazables cuando existan;
7. retest/touch derivados de evidencia canónica;
8. razones de espera explícitas cuando no haya condiciones suficientes;
9. cero órdenes, entry, SL, TP, fill o sizing en la capa de lectura;
10. advertencia explícita cuando el feed MT5 difiera del feed histórico/versionado utilizado en auditorías.

**La prueba no pasa** si el sistema puede producir un texto convincente pero no puede resolver las referencias, timestamps y lineage que sostienen cada afirmación.

## 1. Responsabilidades de capas derivadas de la tesis

La tesis exige separar `htf`, `itf` y `exec_tf`; no se permite asumir `exec_tf == ltf` sin declararlo.

### Perfil diario vigente

```text
HTF     = D1
ITF     = H4
CONTEXT = H1
EXEC    = M15
```

Este es el perfil actual de lectura diaria, no una ley universal.

### Extensión fina de la tesis

```text
D1 → H4 → H1 → M15 → M5 → M1
```

M5/M1 quedan diferidos como perfiles productivos hasta disponer de datos, PIT, contratos y evidencia específica.

Regla fundamental:

```text
HTF/ITF definen contexto y restricciones.
EXEC/LTF observa confirmación y retest.
LTF jamás reescribe retrospectivamente HTF/ITF.
```

## 2. Estado real de implementación

### Implementado

- `engine/plan.py`: snapshots closed-only, bias estructural, dealing range D1/H4, `ltf_structure_at()`, `ltf_confirms()`, `build_context_stack()`.
- `engine/daily_motor.py`: `DailyMotorConfig` con `profile_id` explícito, snapshot serializable con `asof_times_by_tf`, navegación/contexto/Sequence/lineage y `entry_authorized=False`.
- `engine/daily_motor.py`: consume `MarketObject` canónicos de FVG/OB como entrada de solo lectura; no promueve flags arbitrarios del DataFrame ni crea detectores/FSM paralelos.
- `engine/daily_motor.py`: consume `MarketState` autoritativo de `MTFNavigator` mediante `context_state`; conserva capas, restricciones y `path` completos.
- `engine/ltf_canonical_feed.py`: adaptador read-only que reutiliza detectores FVG/OB, relaciones y `engine.sequential_events` para entregar zonas, touch/retest, refs y profundidad as-of(t). No es un detector ni una FSM nueva.
- `tests/test_daily_motor.py`: observación, futuro ignorado, contexto incompleto, esquema canónico, retest con touch, determinismo y autoridad LTF.
- `tests/test_ltf_canonical_feed.py`: prefijo/PIT, detectores canónicos y touch posterior a `tradable_time`.
- `scripts/brief_lunes.py`: consume el mismo snapshot y diferencia zonas canónicas de marcadores legacy.

### Parcial / pendiente

- El caller productivo ya conecta FVG/OB, relaciones y Sequence canónicos en la lectura M15; falta demostrar el mismo ensamblaje para POI ITF/AHF y el perfil histórico completo.
- `retest_observed` ya depende de `MarketObject.first_touch_time` + `touch_count` y orden temporal válido; el gate requiere evidencia histórica de esa cadena.
- Sequence ya se consume sin duplicarla desde `engine.sequential_events`; la cobertura de lineage debe ampliarse a Context State → POI ITF → zona LTF.
- AHF todavía no se inyecta como `navigation_snapshot` en el brief; el `MarketState` sí está conectado, pero LTF-3 permanece abierto.
- Debe materializarse un snapshot auditable único `Context State → POI ITF → LTF confirmation → retest`.
- Falta validación histórica extremo a extremo D1→H4→H1→M15.
- M5/M1 siguen diferidos.

## 3. Principios para una IA autónoma

1. Una sola fuente por concepto: estructura en `engine.bos`/`engine.plan`; Context State en `engine.mtf_navigation`; FVG/OB en detectores canónicos; lineage en `engine.lineage`; Sequence en su motor canónico; navegación en `engine.ahf`.
2. No crear detectores paralelos en `daily_motor.py`, `brief_lunes.py` o agentes.
3. No crear una segunda FSM para retest.
4. Toda observación debe ser `as-of(t)`.
5. Contexto, zonas, confirmación y retest conservan timestamps.
6. Ningún dato futuro puede modificar un snapshot histórico.
7. Estado observable nunca equivale a orden.
8. EMA/ATR/OTE/Fibonacci no pueden convertirse en bias o veto normativo.
9. Falta de datos se representa como espera/degradación explícita; nunca se inventa evidencia.
10. Una fase solo puede marcarse `PASS` con código, tests y evidencia versionada.
11. Si falta un módulo o interfaz canónica, la IA puede crearlo, pero debe justificar dónde encaja en la autoridad del motor, añadir tests y registrar el cambio en worklog.
12. Antes de cerrar una fase, la IA debe investigar primero los módulos existentes y demostrar por qué reutilizarlos o extenderlos; no debe duplicar capacidades ya presentes.

## 4. Contrato temporal

```text
as_of(tf, t) = última vela cerrada con time ≤ t
```

Debe cumplirse:

```text
context_htf_time   ≤ t
context_itf_time   ≤ t
sequence_time      ≤ t
zone_confirmation  ≤ t
ltf_structure_time ≤ t
retest_time        ≤ t
```

Cadena histórica completa:

```text
candidate_time
≤ confirmation_time
≤ tradable_time
≤ ltf_confirmation_time
≤ retest_time
≤ entry_time
```

`entry_time` pertenece a un contrato de ejecución futuro y no se produce desde esta capa.

## 5. Snapshot LTF mínimo

Debe conservar, como mínimo:

```text
profile_id
htf_tf / itf_tf / context_tf / exec_tf
decision_time
asof_times_by_tf
context_state
navigation_state
active_tf / parent_state
transition_event / transition_time / invalidation_reason
direction_hint
location
regime_stack
constraints
poi_refs
sequence_refs / sequence_depth
ltf_structure
ltf_confirmation
active_zone_refs
retest_state
lineage_refs
policy
```

Política:

```text
policy = OBSERVE_ONLY_NO_ORDER
entry_authorized = false
```

El snapshot debe ser serializable y reconstruible sin consultar datos posteriores a `decision_time`.

## 6. Máquina de lectura LTF

```text
NO_LTF_DATA
   │ datos disponibles
   ▼
WAIT_CONTEXT
   │ Context State válido + capa superior locked
   ▼
WAIT_LTF_CONFIRMATION
   │ estructura LTF compatible
   ▼
WAIT_LTF_ZONE
   │ zona canónica FVG/OB/POI observable
   ▼
WAIT_RETEST
   │ touch/retest canónico observable
   ▼
OBSERVABLE_SETUP
```

Las invalidaciones superiores se procesan por AHF; LTF no muta localmente el contexto de D1/H4.

## 7. Integración MTF/HTF

### LTF recibe

```text
Context State confirmado
+ direction_hint
+ regime_stack
+ location
+ constraints
+ POI refs
+ parent navigation state
```

### LTF puede

- confirmar/no confirmar estructura compatible;
- observar displacement/momentum si el motor lo expone como hecho canónico;
- observar zona canónica activa;
- observar touch/retest;
- devolver razón de espera;
- emitir eventos que el AHF sea capaz de consumir.

### LTF no puede

- cambiar `direction_hint` de D1/H4;
- invalidar HTF por contradicción microestructural aislada;
- convertir `SETUP_READY` en orden;
- leer futuro;
- sustituir Context State por un bias LTF.

## 8. FVG / OB / Sequence / retest

```text
Sequence / structure
        ↓
PD array / FVG / OB canónicos
        ↓
POI / zone refs
        ↓
LTF observa estado
        ↓
retorno / retest
```

No se acepta `zone_present=True` por un string arbitrario del DataFrame si no existe un objeto/ref canónico auditable.

El snapshot debe poder responder:

```text
¿Qué zona?
¿Quién la creó?
¿Cuándo se confirmó?
¿Cuándo fue tradable?
¿Qué padre tiene?
¿Qué eventos/sequence la explican?
¿Fue tocada/mitigada/retestada?
¿Cuándo?
```

Si falta evidencia, el estado es `WAIT_*`/`NO_EVIDENCE`, nunca una promoción silenciosa.

## 9. Fases de trabajo

### LTF-0 — Normalización contractual

- Congelar perfil D1/H4/H1/M15.
- Congelar esquema del snapshot.
- Formalizar `as_of` por TF.
- Enlazar AHF/Context State/Sequence/Lineage.
- Separar explícitamente `EXEC`, `LTF` y `context_tf`.

**Gate:** sin contradicción con tesis ni contratos MTF/AHF.

### LTF-1 — Cierre integral del snapshot observacional

**Estado:** en progreso; contrato de salida reforzado, gate integral pendiente.

- Mantener `build_daily_motor_snapshot()`.
- Exponer `profile_id`, roles temporales y `asof_times_by_tf` de forma explícita.
- Exponer `navigation`, `context`, `sequence`, `ltf.zone_refs`, `retest_state` y `lineage_refs` sin crear una FSM paralela.
- Hacer que el snapshot sea JSON-serializable y determinista para entradas equivalentes.
- Tratar los marcadores legacy del DataFrame como diagnóstico; nunca como promoción canónica.
- Tests PIT mediante futuro añadido.
- Tests de serialización/determinismo.
- No existe salida de orden.
- Brief consume el mismo snapshot.

**Gate:** tests sintéticos + PIT + serialización + integración.

### LTF-2 — Integración canónica de zonas y retest

**Estado:** integración productiva inicial ejecutada; gate pendiente.

- Obtener FVG/OB/POI desde objetos/detectores canónicos.
- Resolver refs y lineage.
- Transportar candidate/confirmation/tradable.
- Conectar touch/mitigation/retest al estado canónico.
- Consumir Sequence sin duplicarla.
- Exponer `active_zone_refs` y `retest_state`.

**Gate:** cada zona/retest tiene identidad, timestamps y lineage.

### LTF-3 — Integración AHF

- Recibir snapshots locked de ancestros.
- Respetar `active_tf`.
- Emitir solo eventos permitidos por AHF.
- Probar rollback H1/H4/D1.
- Preservar historial y `parent_state`.

**Gate:** avance + rollback + revisita + no reescritura.

### LTF-4 — Validación histórica

- Dataset versionado D1/H4/H1/M15.
- Corridas deterministas.
- Invariancia por prefijo/truncación.
- Comparación antes/después de añadir futuro.
- Cobertura por estado y errores de navegación.
- Distribución `NO_LTF_DATA`, `WAIT_*`, `OBSERVABLE_SETUP`.
- Repetir una lectura actual sobre feed MT5 y documentar diferencias de símbolo/sesión/broker frente al snapshot histórico.

**Gate:** cero violaciones PIT, cero mutaciones históricas inexplicadas, reporte versionado.

### LTF-5 — M5/M1

Solo después de LTF-0..4: datos, perfil explícito, microestructura sin redefinir HTF/ITF y repetición de todos los gates.

### LTF-6 — Ejecución separada

No pertenece al actual trabajo de lectura. Un futuro plan/SDD separado deberá definir trigger, entry, SL, TP, fill, sizing, hold_limit, timing y fallos.

## 10. Tests obligatorios

### PIT

Añadir futuro HTF, ITF, M15 y todos a la vez; el snapshot histórico debe permanecer idéntico.

### Prefijo

```text
snapshot(prefix, t) == snapshot(full, t)
```

### Autoridad de capas

- LTF contrario no cambia `direction_hint`.
- M15/M5/M1 no reescriben D1/H4.
- Solo AHF puede provocar rollback superior.
- Context State nunca se transforma en entry.

### Lineage

- `active_zone_ref` siempre resuelve.
- Retest siempre resuelve a zone/POI padre.
- Cero enlaces futuros/ciclos.

### Retest

- zona sin touch → `WAIT_RETEST`;
- touch sin evento canónico → no promover;
- retest válido + demás condiciones → `OBSERVABLE_SETUP`;
- invalidación superior → rollback + historial preservado.

### Ausencia de datos

- sin M15 → `NO_LTF_DATA`/degradación explícita;
- sin zona → `WAIT_LTF_ZONE`;
- sin Context State → `WAIT_CONTEXT`;
- nunca completar mediante supuestos.

### Determinismo

Mismo dataset + commit + configuración → mismo snapshot.

### Seguridad de API

No deben existir desde esta capa:

```text
order
fill
broker
sizing
position
entry_authorized=True
```

### Prueba de aceptación MT5 — lectura semanal + diaria

La IA debe poder ejecutar, con el terminal MT5 configurado y el símbolo real del proyecto:

```text
"Ahora dame una muestra, ya está configurado el MT5 que se va a usar para este proyecto, dame lectura de mercado para esta semana y el día de hoy"
```

y producir:

- identificación del símbolo/feed/servidor y timestamp;
- lectura semanal derivada de D1/H4/H1;
- lectura del día derivada del mismo Context State/navegación;
- M15 como capa EXEC de lectura;
- referencias canónicas de POI/FVG/OB cuando existan;
- retest/touch canónico cuando exista;
- estado `WAIT_*` o `OBSERVABLE_SETUP` con explicación;
- advertencias sobre diferencias entre feed MT5 y dataset histórico;
- cero entry/SL/TP/orden.

No se acepta una respuesta basada solo en `trend D1/H4`, texto libre o marcadores legacy.

## 11. Observabilidad

Cada snapshot debe explicar:

```text
HTF: direction / location / regime
ITF: structure / POI
Sequence: depth / refs
LTF: structure / zone / retest / status
Navigation: state / active_tf / parent_state / transition_event
```

La IA debe preferir `WAIT_*` con causa explícita frente a una clasificación no demostrable.

## 12. Cierre LTF Reading

`PASS` únicamente cuando:

1. D1→H4→H1→M15 sea explícito y reproducible;
2. Context State/AHF se consuman correctamente;
3. FVG/OB/Sequence lleguen por fuentes canónicas;
4. toda zona/retest tenga lineage + timestamps;
5. cero look-ahead cross-TF;
6. cero reescritura de ancestros por LTF;
7. rollback AHF sea determinista/auditable;
8. PIT/prefijo/lineage/determinismo pasen;
9. el brief consuma el mismo snapshot sin lógica paralela;
10. no exista ruta de orden en lectura LTF;
11. exista reporte histórico versionado;
12. índice/worklog coincidan con el estado;
13. la prueba MT5 semanal/diaria produzca una lectura basada en el snapshot canónico y no en una segunda implementación.

**PASS LTF Reading no significa edge, entry ni rentabilidad.**

## 13. Objetivo operativo para Codex/Hermes

**Objetivo único:** completar LTF end-to-end hasta que la prueba de aceptación MT5 semanal + diaria sea reproducible y auditable.

La IA debe trabajar de forma autónoma usando este plan y el SDD como autoridad. Debe investigar el repo antes de crear módulos, reutilizar primero las fuentes canónicas existentes, y crear nuevos módulos solo cuando falte una interfaz real y su creación sea necesaria para cerrar una brecha del contrato.

Orden obligatorio:

```text
1. localizar y mapear fuentes canónicas
2. verificar caller real del brief/MT5
3. conectar Context State/AHF → LTF
4. conectar detectores/objetos FVG/OB → POI/zona LTF
5. conectar Sequence/lineage → snapshot
6. conectar touch/mitigation/retest → estado LTF
7. cerrar PIT/prefijo/determinismo/autoridad
8. validar feed MT5 real
9. generar muestra semanal + diaria
10. registrar evidencia y cerrar gates
```

Puede modificar `engine/`, `scripts/`, tests y contratos auxiliares cuando sea necesario, respetando siempre la jerarquía de autoridad. Si crea un módulo nuevo, debe registrar en el worklog: problema, motivo de creación, API, autoridad de datos, tests, archivos afectados y relación con este plan.

No está permitido declarar `PASS` por haber conseguido una respuesta de texto convincente. El gate exige que las afirmaciones de la muestra puedan resolverse a objetos, referencias, timestamps y lineage reales.

## 14. Bitácora obligatoria al finalizar

Crear o actualizar un worklog en `.hermes-worklog/` con:

```text
fecha / commit
estado final de LTF-0..6
módulos nuevos o modificados
fuentes canónicas utilizadas
brechas encontradas y cerradas
tests ejecutados y resultados
PIT/prefijo/determinismo
integración AHF/Context State
integración FVG/OB/Sequence/lineage/retest
feed MT5 usado: símbolo / broker / servidor / timestamps
muestra semanal y diaria
limitaciones restantes
PASS/FAIL/BLOCKED de cada gate
```

La bitácora debe distinguir hechos observados, hipótesis y deuda pendiente. Nunca ocultar fallos ni marcar una fase como completa sin evidencia.
