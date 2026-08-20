# PLAN — Capa LTF / EXEC + Wyckoff: lectura canónica del motor

**Estado:** ACTIVO — lectura de mercado; ejecución financiera fuera de alcance  
**Fecha:** 2026-08-20  
**Autoridad base:** `docs/ict/SPEC_TESIS_FORMAL.md` + libros ICT 16/18  
**Padre MTF:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`  
**Contratos:** `docs/contratos/CONTRATO_MULTI_TF_LAYERS.md`, `docs/contratos/CONTRATO_AHF.md`, `docs/contratos/CONTRATO_CONTEXT_STATE.md`  
**SDD:** `docs/tesis/SDD_LTF_ENTRY_LAYER.md`

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