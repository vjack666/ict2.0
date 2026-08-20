# OBJETIVO AUTÓNOMO — Integración Wyckoff en el motor canónico ICT/MTF/LTF

**Fecha:** 2026-08-20  
**Estado:** OBJETIVO ACTIVO — Codex/Hermes debe trabajarlo hasta cerrar sus gates  
**Plan padre:** `docs/tesis/PLAN_LTF_ENTRY_LAYER.md`  
**SDD padre:** `docs/tesis/SDD_LTF_ENTRY_LAYER.md`  
**Biblioteca:** `docs/wyckoff/**` + `docs/reglas/WYCKOFF_RULEBOOK.md`

## 1. Misión

Localizar todo el código Wyckoff existente en el repositorio, en ramas e historia Git; separar lógica reutilizable de agentes/UI legacy; consolidar la lógica runtime autorizada en `engine/Wyckoff/`; conectar esa capa al motor de lectura diario ICT/MTF/LTF; conservar `docs/wyckoff/**` como biblioteca especializada; y producir una lectura integrada que pueda distinguir:

```text
PRO_TREND
COUNTERTREND
TRANSITION
NEUTRAL
```

según la relación entre la fase/eventos Wyckoff y el estado ICT/HTF/MTF, sin crear un segundo motor, una segunda FSM ni un veto universal.

## 2. Regla de oro

Antes de escribir código, **investigar y reutilizar**. Antes de mover un módulo, **clasificarlo**. Antes de declarar PASS, **probarlo**.

No copiar `analysis/wyckoff_agent.py` a `engine/Wyckoff/` sin auditoría: contiene heurísticas de fase, tick-volume, ATR y stochastic que pueden ser útiles como evidencia pero no deben convertirse automáticamente en autoridad normativa. El rulebook vigente describe conceptos, no reglas de trading. `docs/wyckoff/compras/06_relacion_ict.md` y `docs/wyckoff/ventas/06_relacion_ict.md` ya establecen el principio "Wyckoff como contexto, ICT como precisión" y el registro transparente del conflicto. 

## 3. Inventario obligatorio

Ejecutar y registrar resultados de:

```bash
rg -n -i "wyckoff|spring|upthrust|utad|sos|sow|lpsy|lps" .
git grep -n -i "wyckoff" $(git for-each-ref --format='%(refname)' refs/heads refs/remotes) || true
git log --all --name-only --pretty=format: -- '*wyckoff*'
git log --all -S'WyckoffAgent' --oneline -- analysis agents engine scripts docs || true
```

Revisar también referencias/imports:

```bash
rg -n "analysis\.wyckoff_agent|agents\.wyckoff_agent|wyckoff_agent|fase_wyckoff|WYCKOFF_RULEBOOK" .
```

La punta `main` actual no contiene una carpeta de código `smc/` ni un árbol `ict/` equivalente a una carpeta de módulos runtime. Si el objetivo histórico menciona `smc/`/`ict/`, buscar en historia/ramas antes de concluir que los módulos ya no existen.

### Clasificación por hallazgo

Cada archivo/clase/función debe quedar marcado como uno de:

```text
CANONICAL_CANDIDATE
LEGACY_COMPAT
ANALYSIS_ONLY
DOCUMENTATION
DUPLICATE
OBSOLETE
```

Y debe registrarse:

```text
source_path
symbol/class/function
consumer(s)
imports
source_commit
rulebook_mapping
runtime_eligibility
migration_action
```

## 4. Reubicación de código

Crear `engine/Wyckoff/` solo si no existe una autoridad equivalente. El objetivo preferido es:

```text
engine/Wyckoff/
├── __init__.py
├── types.py
├── phases.py
├── events.py
├── effort_result.py
├── classifier.py
└── adapter.py
```

No son nombres obligatorios si el inventario demuestra una arquitectura mejor.

### Separación de responsabilidades

`phases.py`: clasificación de fase/rango/proceso.  
`events.py`: Spring, Upthrust/UTAD, SOS, SOW, LPS, LPSY, tests y fallos.  
`effort_result.py`: evidencia de esfuerzo/resultado y volumen relativo.  
`types.py`: enums/records inmutables y serializables.  
`classifier.py`: relación Wyckoff ↔ ICT (`PRO_TREND`, `COUNTERTREND`, `TRANSITION`, `NEUTRAL`).  
`adapter.py`: integración read-only con `daily_motor`, Context State y LTF.

El módulo legacy debe quedar como wrapper solo cuando exista consumidor; no deben sobrevivir dos implementaciones activas del mismo detector.

## 5. Contrato Wyckoff runtime

Salida mínima:

```text
WyckoffSnapshot
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
```

`phase`:

```text
ACCUMULATION | MARKUP | DISTRIBUTION | MARKDOWN |
RANGE_UNCLASSIFIED | TRANSITION | UNKNOWN
```

`phase_state`:

```text
PRO_TREND | COUNTERTREND | TRANSITION | NEUTRAL
```

`events[]` usa únicamente vocabulario respaldado por la biblioteca/rulebook salvo extensión documentada:

```text
SPRING | UPTHRUST | UTAD | SOS | SOW | LPS | LPSY |
TEST | FAILED_TEST | RANGE_BREAK | EFFORT_RESULT_DIVERGENCE
```

Cada evento debe incluir:

```text
event_id
event_type
tf
event_time
source_ref
evidence_refs
confirmation_status
```

## 6. Autoridad temporal

Perfil diario:

```text
D1  → fase/régimen macro
H4  → rango, causa y transición
H1  → confirmación del proceso
M15 → comportamiento local del setup
M5/M1 → solo perfiles explícitos
```

`authority_tf` debe viajar en el snapshot. Una observación M15 nunca puede sobrescribir una fase D1/H4.

## 7. Integración con ICT

Wyckoff interpreta el proceso; ICT conserva estructura, liquidez, location, POI, FVG/OB, Sequence y retest.

Relaciones esperadas, sin tratarlas como equivalencias exactas:

```text
Spring / reclaim      ↔ sweep SSL + reclaim ICT
Spring + Test         ↔ CHOCH/MSS bullish + confirmación
SOS                    ↔ desplazamiento/BOS bullish
LPS                    ↔ pullback/retest hacia POI
UTAD / failed UTAD    ↔ sweep BSL + rechazo / reversión
SOW                    ↔ desplazamiento/BOS bearish
LPSY                   ↔ pullback/retest bajista
```

El agente debe declarar explícitamente cuando existe analogía y nunca convertir una equivalencia conceptual en una identidad matemática.

## 8. Política pro-trend / countertrend

### PRO_TREND

ICT direction y proceso Wyckoff se alinean.

### COUNTERTREND

Wyckoff sugiere transición/acumulación/distribución opuesta al contexto mayor y existe evidencia ICT que empieza a confirmarla.

### TRANSITION

Hay señales de cambio de proceso, pero falta confirmación suficiente para considerar la nueva dirección compatible.

### NEUTRAL

No hay evidencia suficiente. No penalizar artificialmente la lectura ICT.

**Nunca:**

```text
Wyckoff bearish → bloquear todo long
Wyckoff bullish → bloquear todo short
```

Wyckoff es `evidence_modifier`, no `hard_veto`.

## 9. Volumen / ATR / indicadores

Para FX/MT5 el volumen se trata como `tick_volume` relativo al feed. No es volumen centralizado del mercado.

La IA puede usar ATR/rango únicamente para normalización o medición si el rulebook lo exige; **nunca como bias normativo**. EMA, OTE y Fibonacci permanecen prohibidos como sesgo/veto.

Si faltan columnas de volumen:

```text
volume_mode = UNAVAILABLE
```

y el sistema no debe inventar una confirmación de volumen.

## 10. Integración con el motor actual

El flujo obligatorio es:

```text
MTFNavigator / Context State
        ↓
AHF locked context
        ↓
Wyckoff adapter (read-only)
        ↓
ITF POI + Sequence + FVG/OB
        ↓
LTF confirmation + retest
        ↓
daily_motor snapshot
        ↓
brief_lunes.py
```

No crear:

```text
otro Context State
otra AHF
otra FSM
otro detector FVG/OB
otro detector Sequence
otro orquestador de trading
```

## 11. PIT obligatorio

Toda fase/evento Wyckoff debe calcularse con datos `time <= decision_time`.

Los tests deben demostrar:

```text
snapshot(prefix_to_t, t) == snapshot(full_series, t)
```

También se exige que `event_time <= confirmation_time <= decision_time` y que ningún test futuro cambie el evento histórico.

## 12. Modificación del snapshot LTF

Agregar, sin romper compatibilidad:

```text
wyckoff:
  phase
  phase_state
  authority_tf
  events
  range_ref
  evidence_refs
  effort_result
  volume_mode
  ict_alignment
  conflict
  explanation
```

El brief debe presentar esta capa como lectura especializada, no como señal.

## 13. Tests mínimos

### Unidad
- fases con ventanas sintéticas;
- Spring/Upthrust con reclaim;
- SOS/SOW;
- LPS/LPSY;
- esfuerzo/resultado;
- ausencia de volumen;
- autoridad temporal.

### Integración
- Context State → Wyckoff → LTF;
- Wyckoff no cambia `direction_hint`;
- conflicto = dato explicativo;
- `COUNTERTREND` no produce `entry_authorized`;
- AHF continúa siendo la única FSM.

### Migración
- todos los imports legacy resueltos;
- compat wrappers solo donde existan consumidores;
- ningún detector doble activo;
- `analysis/` queda solo como análisis o wrapper, no como autoridad silenciosa.

## 14. Gate de aceptación

PASS solo si:

1. inventario completo, incluido Git history/branches;
2. código runtime consolidado en `engine/Wyckoff/` o arquitectura equivalente documentada;
3. documentación especializada preservada y actualizada;
4. snapshot integrado al motor LTF/MTF;
5. `authority_tf` explícito;
6. PRO_TREND/COUNTERTREND/TRANSITION/NEUTRAL reproducibles;
7. cero veto universal;
8. cero look-ahead;
9. determinismo y prefijo PASS;
10. tests de integración PASS;
11. brief semanal + diario muestra la nueva capa;
12. worklog final lista archivos movidos, wrappers, módulos nuevos, tests, evidencia y limitaciones;
13. commit(s) trazables.

**No confundir PASS técnico con edge, PnL o entry.**