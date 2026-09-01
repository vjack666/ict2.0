# PLAN — Capa LTF / EXEC + Wyckoff: lectura canónica del motor

**Estado:** ACTIVO — lectura de mercado; ejecución financiera fuera de alcance  
**Fecha:** 2026-08-20  
**Autoridad base:** `docs/ict/SPEC_TESIS_FORMAL.md` + libros ICT 16/18  
**Padre MTF:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`  
**Contratos:** `docs/contratos/CONTRATO_MULTI_TF_LAYERS.md`, `docs/contratos/CONTRATO_AHF.md`, `docs/contratos/CONTRATO_CONTEXT_STATE.md`  
**SDD:** `docs/tesis/SDD_LTF_ENTRY_LAYER.md`

## Estado de implementación Wyckoff

| Fase | Estado | Evidencia |
|---|---|---|
| WYCKOFF-0 Inventario | `PASS` | `reports/audits/runtime/wyckoff_runtime_inventory_2026-08-20.md` |
| WYCKOFF-1 Runtime | `IN PROGRESS` | `engine/Wyckoff/` creado; wrappers legacy aún tienen consumidores |
| WYCKOFF-2 LTF/MTF | `IN PROGRESS` | `daily_motor` y `brief_lunes.py` consumen `WyckoffSnapshot` |
| WYCKOFF-3 Clasificación ICT | `IN PROGRESS` | PRO_TREND/COUNTERTREND y conflicto probados; transición/neutral requieren cobertura ampliada |
| WYCKOFF-4 Retest | `PARTIAL` | snapshot Wyckoff convive con zona/retest canónicos; lineage completo pendiente |
| WYCKOFF-5 Histórico/MT5 | `PENDING` | falta evidencia versionada con la nueva capa |

## Objetivo rector

Construir una sola lectura ICT/MTF/LTF en la que Wyckoff sea una **capa especializada de lectura**. No se crea un segundo motor, segunda FSM, segundo Context State ni segundo sistema de señales.

```text
MT5 / histórico
  ↓
HTF Context State
  ↓
ITF structure + POI
  ↓
Sequence / FVG / OB / lineage
  ↓
Wyckoff specialized reading
  ↓
EXEC-LTF confirmation
  ↓
zone / retest
  ↓
WAIT_* / OBSERVABLE_SETUP
```

La prueba final sigue siendo:

> **“Ahora dame una muestra, ya está configurado el MT5 que se va a usar para este proyecto, dame lectura de mercado para esta semana y el día de hoy”.**

La lectura debe reconstruirse desde el feed MT5 real, con `as_of(t)`, Context State, POI, Sequence, Wyckoff, LTF y retest trazables.

## 1. Perfil temporal

```text
HTF     = D1
ITF     = H4
CONTEXT = H1
EXEC    = M15
```

Wyckoff:

| TF | Rol | Autoridad |
|---|---|---|
| D1 | fase/régimen macro | muy alta |
| H4 | rango/causa/transición | alta |
| H1 | confirmación del proceso | media |
| M15 | comportamiento local | baja |
| M5/M1 | microcontexto | diferido |

La salida debe conservar `authority_tf`.

## 2. Inventario antes de implementación

La IA debe localizar el código en árbol actual, ramas e historia:

```bash
rg -n -i "wyckoff|spring|upthrust|utad|sos|sow|lpsy|lps" .
git log --all --name-only --pretty=format: -- '*wyckoff*'
git log --all -S'WyckoffAgent' --oneline -- analysis agents engine scripts docs || true
rg -n "analysis\.wyckoff_agent|agents\.wyckoff_agent|fase_wyckoff|WYCKOFF_RULEBOOK" .
```

La punta `main` actual no debe asumirse que contiene `smc/` o una carpeta runtime `ict/`; si el objetivo histórico menciona esas rutas, buscar su contenido en historia/ramas antes de declararlo perdido.

Clasificación obligatoria:

```text
CANONICAL_CANDIDATE | LEGACY_COMPAT | ANALYSIS_ONLY |
DOCUMENTATION | DUPLICATE | OBSOLETE
```

## 3. Consolidación en `engine/Wyckoff`

Si no existe una autoridad equivalente, crear:

```text
engine/Wyckoff/
  __init__.py
  types.py
  phases.py
  events.py
  effort_result.py
  classifier.py
  adapter.py
```

La estructura exacta puede cambiar si el inventario justifica una mejor división, pero deben quedar separadas:

- tipos/contratos;
- fases;
- eventos;
- esfuerzo/resultado/volumen;
- clasificación contra ICT;
- adaptador read-only al motor.

No copiar agentes/UI a runtime. Extraer lógica pura. Mantener wrappers solo si hay consumidores reales.

## 4. Capa Wyckoff — contrato funcional

Fases:

```text
ACCUMULATION
MARKUP
DISTRIBUTION
MARKDOWN
RANGE_UNCLASSIFIED
TRANSITION
UNKNOWN
```

Estado integrado:

```text
PRO_TREND
COUNTERTREND
TRANSITION
NEUTRAL
```

Eventos:

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

Cada evento conserva `tf`, `event_time`, `source_ref`, `evidence_refs` y estado de confirmación.

## 5. Política ICT ↔ Wyckoff

### PRO_TREND

La fase/proceso Wyckoff está alineado con la dirección/estructura ICT.

### COUNTERTREND

Wyckoff detecta proceso opuesto o transición frente al contexto mayor. Esto **no autoriza** reversión por sí mismo; requiere confirmación ICT LTF.

### TRANSITION

Hay evidencia de cambio de proceso, pero todavía no suficiente para sustituir el contexto mayor.

### NEUTRAL

No hay evidencia suficiente; la lectura ICT continúa sin penalización artificial.

Wyckoff es `evidence_modifier`, nunca `hard_veto`.

## 6. Integración

La capa Wyckoff recibe de MTF/AHF:

```text
Context State
parent navigation
active_tf
direction_hint
location
regime_stack
constraints
POI refs
```

Y devuelve evidencia:

```text
phase
phase_state
authority_tf
events
evidence_refs
range_ref
volume_mode
effort_result
ict_alignment
conflict
explanation
```

Wyckoff no puede:

- cambiar `direction_hint` de D1/H4;
- crear una segunda FSM;
- escribir AHF directamente;
- crear otro Context State;
- leer futuro;
- convertir `OBSERVABLE_SETUP` en orden.

## 7. Volumen y normalización

MT5 aporta `tick_volume` relativo; no debe tratarse como volumen centralizado del mercado FX.

Si falta volumen:

```text
volume_mode = UNAVAILABLE
```

ATR puede servir para normalización/medición si lo exige el rulebook, pero nunca como bias normativo. EMA/OTE/Fibonacci quedan fuera.

## 8. Fases de trabajo

### WYCKOFF-0 — Inventario

- localizar código/docs/historia/ramas;
- mapear imports y consumidores;
- comparar código con rulebook;
- clasificar y documentar cada hallazgo.

**Gate:** inventario completo.

### WYCKOFF-1 — Consolidación runtime

- crear/reorganizar `engine/Wyckoff`;
- extraer lógica pura;
- definir API única;
- wrappers de compatibilidad solo si son necesarios;
- eliminar duplicación después de comprobar consumidores.

**Gate:** una única implementación runtime por concepto.

### WYCKOFF-2 — Integración LTF/MTF

- conectar `daily_motor` con la capa;
- transportar `authority_tf` y snapshot Wyckoff;
- integrar Context State/POI/Sequence/lineage;
- hacer explícita la precedencia temporal.

**Gate:** snapshot serializable y determinista.

### WYCKOFF-3 — Clasificación ICT

- implementar/validar PRO_TREND, COUNTERTREND, TRANSITION, NEUTRAL;
- conflicto transparente;
- no veto universal;
- tests de autoridad por TF.

**Gate:** conflicto no altera silenciosamente el contexto ICT.

### WYCKOFF-4 — LTF y retest

- M15 observa fase/eventos pertinentes;
- conectar zona/retest canónicos;
- conservar timestamps y lineage;
- `WAIT_*` cuando falte evidencia.

**Gate:** no-look-ahead + lineage.

### WYCKOFF-5 — Validación histórica + MT5

- prefijo/PIT;
- determinismo;
- comparación histórica/MT5;
- lectura semanal y diaria reproducible;
- reporte versionado.

**Gate:** cero violaciones PIT; evidencia completa.

### WYCKOFF-6 — Documentación y cierre

Actualizar Plan/SDD/biblioteca/índices/worklog; registrar módulos movidos, módulos nuevos, wrappers, tests, resultados y limitaciones.

## 9. Tests de cierre

- PIT D1/H4/H1/M15;
- truncation invariance;
- determinismo;
- `authority_tf` correcto;
- LTF no reescribe HTF;
- AHF sigue siendo única FSM;
- COUNTERTREND no genera orden;
- TRANSITION no invierte silenciosamente;
- NEUTRAL no penaliza ICT;
- eventos con timestamps y refs;
- tick-volume ausente no produce falsa confirmación;
- wrappers legacy no alimentan snapshot canónico con flags arbitrarios;
- cada `evidence_ref` resoluble o estado degradado auditable.

## 10. Cierre

El trabajo queda PASS solamente cuando la lectura semanal y diaria del MT5 puede mostrar, en una sola salida:

```text
D1 Context
H4 POI/location
H1 Sequence/context
Wyckoff phase + authority_tf + phase_state
M15 ICT structure
canonical zone
retest
WAIT_* / OBSERVABLE_SETUP
```

**PASS técnico no significa edge, entry ni rentabilidad.**

## 11. WYCKOFF-7 — CANONICAL PHASES + CME 6E

Esta extensión fija el contrato de fases y eventos sin crear un segundo motor.
Su estado inicial es `DRAFT — REVIEW PENDING`; no autoriza implementación,
descarga de datos ni experimentos.

Secuencias canónicas:

```text
Acumulación: PS → SC → AR → ST → FASE_B → SPRING → TEST → SOS → LPS → MARKUP
Distribución: PSY → BC → AR → ST → FASE_B → UTAD → TEST → SOW → LPSY → MARKDOWN
```

La representación canónica Wyckoff será un evaluador de transiciones por
`range_id`, causal y subordinado a AHF/Context State; AHF continúa siendo la
única FSM jerárquica de orquestación. No puede crear estados AHF, cambiar
`direction_hint`, autorizar una entrada ni convertirse en un segundo sistema
de señales.

Los tokens se clasifican antes de programar: `PS/SC/AR/ST/PSY/BC/SPRING/TEST/
UTAD/SOS/SOW/LPS/LPSY` son eventos; `FASE_B` es estado de causa;
`MARKUP/MARKDOWN` son estados de régimen. Cada transición debe estar vinculada
al rulebook; la falta de evidencia se registra, no se rellena con un salto de
secuencia.

Cada transición conserva `range_id`, `episode_id`, `from_state`,
`event_type`, `to_state`, `appeared_at`, `confirmed_at`,
`invalidated_at` (opcional), `source_ref`, `evidence_refs` y `reason`.
`appeared_at` es el primer instante observable con el prefijo disponible;
`confirmed_at` solo puede publicarse cuando la regla causal se cumple.
Saltos incompatibles, eventos sin rango o confirmaciones posteriores a
`decision_time` son inválidos. Las invalidaciones se registran y no se borran.

La unidad inferencial primaria futura será `range_id`, con un solo outcome por
rango y sin rangos solapados. Para validarlo se ordena por
`(symbol, venue, timeframe, range_start)` y se rechaza si
`next.range_start < previous.range_end_exclusive`, usando intervalos
`[range_start, range_end_exclusive)` y deduplicando antes los mismos
`range_id`. Rangos de distintos timeframes se agrupan y no son independientes.
`episode_id` será un subidentificador causal para lineage, no una forma de
multiplicar la muestra. El ancla del rango es
el primer PS/PSY observable y su cierre es la invalidación terminal o la
confirmación de MARKUP/MARKDOWN. Velas del mismo rango, marcos correlacionados,
duplicados y confirmaciones derivadas no son observaciones independientes.
Todo rango debe conservar límites, periodo, definición de frontera y
`dataset_snapshot_hash`.

Los fixtures mínimos deben demostrar rangos adyacentes aceptados, solapados
rechazados, duplicados deduplicados y rangos abiertos censurados/no inferibles.

Para CME `6E`, cada evento debe identificar símbolo/contrato, venue, mes,
timestamp y zona horaria, política de rollover, OHLCV, volumen, open interest,
sesión, `range_id` y `episode_id`. Los modos normativos son:

```text
CME_CENTRALIZED   volumen centralizado con procedencia verificable
TICK_VOLUME_PROXY conteo relativo, nunca presentado como volumen CME
UNAVAILABLE       ausencia o procedencia no verificable
```

`open_interest` ausente se representa como `null` con
`open_interest_status=UNAVAILABLE`; nunca se imputa ni se sustituye por
ticks. Deben conservarse `published_at`/`available_at` del OI. La unión
`6E ↔ EURUSD` requiere `join_id`, UTC, tolerancia temporal explícita, estado
de match y lineage de ambos lados. `RELATIVE_ONLY` es alias de entrada para
`TICK_VOLUME_PROXY`; `AVAILABLE` solo mapea a `CME_CENTRALIZED` con
procedencia CME verificable.

**Gate WYCKOFF-7:** `PASS` solo con evaluador Wyckoff único subordinado a la
FSM jerárquica AHF, secuencias, timestamps, invalidaciones, rango, volumen/OI,
lineage ICT separado y pruebas causales.
Falta documental acotada produce `REVIEW`; una autoridad duplicada,
procedencia insuficiente o look-ahead produce `BLOCKED`.

## 12. WYCKOFF-8 — CERTIFICATION / PREFLIGHT

WYCKOFF-8 es un preflight documental/PIT previo a cualquier ejecución futura.
En esta fase no se descargan datos, no se entrena IA y no se ejecuta
`EXP-WYCKOFF-CANONICAL-02`.

El manifest mínimo debe contener versión, `dataset_snapshot_id` y hash,
archivos con tamaño/SHA-256/esquema/cobertura/filas, símbolo/venue/contrato,
timeframes, timezone/sesiones/roll, `volume_mode`, fuente de OI,
`config_canonical_hash`, `code_commit`, `generator_commit`, comando
generador, `worktree_path`, rama/identificador, procedencia, rangos,
episodios, fecha de producción y `evidence_refs`. Los commits deben ser
resolubles; `HEAD` ambiguo, rutas sin hash o datos fuera del manifest bloquean.

La certificación compara la serie completa y el prefijo cerrado:

```text
FULL   = serie completa del snapshot certificado
PREFIX = prefijo disponible en decision_time
wyckoff(PREFIX, decision_time) == wyckoff(FULL, decision_time)
```

La comparación debe usar la proyección histórica
`snapshot_at(FULL,t) == snapshot_at(PREFIX,t)` y considerar solo
invalidaciones visibles hasta `t`; una invalidación posterior no puede
retroescribir el pasado. La igualdad cubre fase/estado, rangos, episodios,
timestamps, invalidaciones visibles y referencias, no solo la etiqueta final.
El mismo dataset, configuración, dependencias y commit en checkout limpio debe
producir el mismo manifest, evaluador, eventos y hashes.

| Gate | Criterio |
|---|---|
| `PASS` | manifest completo, hashes/commits resolubles, PIT/FULL-PREFIX causal, determinismo clean e independencia declarada |
| `REVIEW` | ambigüedad documental acotada, sin afirmar certificación |
| `BLOCKED` | falta de datos/procedencia, hash/ref inconsistente, look-ahead, no determinismo o rango/episodio irresoluble |

El PASS de WYCKOFF-8 certifica el artefacto y su reproducibilidad documental;
no demuestra edge, PnL, rentabilidad, entrenamiento, ejecución ni promoción.

### Secuencia de preflight read-only

1. Leer SDD, plan, rulebook y contratos.
2. Resolver commit, worktree, snapshot, hashes, rangos, episodios y refs sin descargar ni generar datos.
3. Auditar FULL/PREFIX, timestamps, invalidaciones, volumen/OI e independencia.
4. Emitir `PASS`, `REVIEW` o `BLOCKED` con `evidence_refs`.
5. Mantener experimento y entrenamiento pendientes de autorización y gates separados.

## 13. Siguiente fase — integración ICT/Wyckoff sobre el motor existente

La siguiente fase no crea un motor Wyckoff independiente. Completa el módulo
`engine/Wyckoff` existente y parte de los contratos ICT/AHF ya construidos.

```text
AHF / Context State (autoridad única)
        ↓
Swing → BOS/CHOCH → Liquidez → FVG/OB → Sequence → lineage
        ↓
engine/Wyckoff (evaluador especializado de rango/fase/eventos)
        ↓
WyckoffEvidence integrada en el snapshot ICT
```

El evaluador Wyckoff consume snapshots y referencias de los módulos ICT; no
recalcula ni reemplaza Swing, BOS/CHOCH, liquidez, FVG/OB, Sequence o AHF.
Devuelve evidencia separada —fase, eventos, rango, volumen/OI y alineación—
sin modificar `direction_hint`, estados AHF, zonas canónicas ni autorización
de entrada.

Orden de trabajo:

1. Congelar las interfaces ICT/AHF existentes e inventariar sus referencias.
2. Completar el contrato de entrada read-only del evaluador Wyckoff.
3. Añadir eventos y transiciones faltantes dentro de `engine/Wyckoff`.
4. Unir evidencia ICT/Wyckoff mediante `source_ref`, `evidence_refs` y
   timestamps PIT, sin duplicar autoridad.
5. Ejecutar fixtures sintéticos de rango, secuencia, solapamiento y
   `FULL/PREFIX` antes de cualquier experimento.
6. Auditar la integración de forma independiente.

La falta de CME `6E`/OI mantiene bloqueados la certificación de datos y
`EXP-WYCKOFF-CANONICAL-02`; la implementación técnica no autoriza por sí sola
entrenamiento, backtest, promoción ni órdenes.
