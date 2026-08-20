# Plan: Pipeline Científico de Aprendizaje y Laboratorio de Lectura ICT

**Fecha base:** 2026-08-16  
**Actualización:** 2026-08-20  
**Autor:** Hermes (bajo directiva del usuario)  
**Base:** propuesta del usuario + integración de auditoría autónoma, laboratorio de lectura ICT y capa Wyckoff.  

> **Propósito del documento:** este archivo es el **plan maestro de investigación** del repositorio. Une el pipeline científico de aprendizaje existente con una auditoría integral del motor de lectura de mercado y una batería de laboratorios reproducibles. No es un runner de tareas.

Cada bloque produce **RESULT -> GATE -> PASS / FAIL / INCONCLUSIVE**. Ningún bloque promociona automáticamente una hipótesis a producción.

**Regla de oro:** todo lo que afirme debe contrastarse con código/evidencia del repo. Los números de calidad se reportan tal cual, sin maquillar. Los resultados negativos y las hipótesis falsadas se conservan.

---

# 0. PRINCIPIOS RECTORES DEL PLAN MAESTRO

1. **Corrección > causalidad > reproducibilidad > evidencia > simplicidad > optimización.**
2. No optimizar una arquitectura incorrecta, un dataset defectuoso ni una hipótesis falsada.
3. No añadir indicadores o filtros sólo para aumentar métricas.
4. No confundir co-ocurrencia con causalidad.
5. No confundir PASS técnico con edge operativo.
6. No utilizar look-ahead, información futura o confirmaciones retroactivas.
7. No promocionar automáticamente ningún experimento a producción.
8. Separar estrictamente **PRODUCTION ENGINE**, **EXPERIMENTAL LAB** y **REPORTS / EVIDENCE**.
9. Un experimento debe poder terminar como `SUPPORTED`, `FALSIFIED`, `INCONCLUSIVE`, `INVALID_PIT` o `INVALID_DATA`.
10. Cuando `n` sea insuficiente, el resultado es **INCONCLUSIVE**, nunca "edge".

---

# 1. TRAMO A — AUDITORÍA AUTÓNOMA INTEGRAL DEL REPOSITORIO

Este tramo debe ejecutarse antes de diseñar nuevas reglas. Su objetivo es descubrir el estado real del sistema y detectar problemas que puedan invalidar experimentos posteriores.

## A1 — INVENTARIO COMPLETO

Inspeccionar todo el repositorio, incluyendo como mínimo:

- `engine/`
- `detectors/`
- `tools/`
- `analysis/`
- `agents/`
- `orchestration/`
- `governance/`
- `docs/`
- `tests/`
- `data/`
- `datasets/`
- `reports/`
- `scripts/`
- `.hermes/`
- `.hermes-worklog/`
- workflows CI/CD y cualquier carpeta adicional relevante.

Construir un mapa de:

1. módulos;
2. dependencias;
3. entradas y salidas;
4. autoridades canónicas;
5. implementaciones duplicadas;
6. código legacy;
7. wrappers;
8. módulos sin consumidores;
9. scripts experimentales;
10. tests;
11. datasets;
12. artefactos;
13. workflows;
14. documentación;
15. componentes productivos vs experimentales.

**GATE A1:** inventario reproducible y discrepancias documentadas.

## A2 — AUDITORÍA DE ARQUITECTURA

Determinar cuál es la autoridad real para cada concepto y si existe contradicción entre documentación y código.

Clasificar hallazgos como `CRITICAL / HIGH / MEDIUM / LOW / INFO`.

No corregir todavía salvo bloqueos que impidan continuar la auditoría.

**GATE A2:** arquitectura entendida; autoridades y duplicaciones identificadas.

## A3 — AUDITORÍA ICT

Revisar exhaustivamente:

- Swing
- BOS
- CHOCH / MSS
- Liquidity
- Sweep
- Displacement
- FVG
- Order Block
- POI
- Sequence
- Retest / Touch
- Killzones / timing
- Power of Three si existe
- Context State
- MTF navigation
- HTF bias
- LTF confirmation
- invalidation
- lineage
- sincronización temporal entre TF

Para cada módulo registrar definición usada, causalidad, riesgo de look-ahead, dependencia de barras futuras, cobertura de tests, consumidores y limitaciones.

**GATE A3:** no quedan componentes críticos con semántica desconocida.

## A4 — AUDITORÍA WYCKOFF

Revisar de forma conjunta:

- `engine/Wyckoff/`
- `analysis/wyckoff_agent.py`
- `agents/wyckoff_agent.py`
- `docs/wyckoff/`
- `docs/reglas/WYCKOFF_RULEBOOK.md`
- integración con `daily_motor`
- integración MTF/LTF
- Context State
- lineage / retest
- tests / reports / worklogs

Determinar autoridad runtime, legacy, eventos implementados, cobertura, causalidad de fase, limitaciones de `tick_volume`, conflictos ICT ↔ Wyckoff y estado de gates `WYCKOFF-0..5`.

**Política Wyckoff:** sólo contexto, régimen, evidencia y conflicto. No segundo motor, no segundo Context State, no hard veto y no generador autónomo de entradas.

**GATE A4:** Wyckoff clasificado como componente experimental/contextual con límites explícitos.

## A5 — AUDITORÍA DE DATOS

Inspeccionar datasets, metadata, hashes, timestamps, timezone, gaps, duplicados, OHLC, tick volume, consistencia multi-TF y diferencias MT5 vs Dukascopy.

Determinar exactamente qué dataset puede usar cada experimento. No sustituir silenciosamente datos faltantes por proxies.

**GATE A5:** datasets autorizados y no autorizados documentados.

## A6 — AUDITORÍA POINT-IN-TIME

Este es un gate obligatorio.

Buscar especialmente:

- pivots `center=True`;
- rolling mal configurados;
- `shift` incorrecto;
- `merge_asof` incorrecto;
- resampling contaminado;
- labels filtrándose a features;
- confirmaciones retroactivas;
- MTF con barras aún no cerradas;
- BOS / CHOCH con pivotes futuros;
- FVG / OB confirmados con información futura.

Cada componente queda como:

`PIT_SAFE` / `PIT_UNSAFE` / `PIT_UNCLEAR`.

Un experimento `PIT_UNSAFE` no puede producir una conclusión de edge.

**GATE A6:** integridad temporal suficiente para continuar.

## A7 — AUDITORÍA DE EXPERIMENTOS EXISTENTES

Revisar todos los experimentos en:

- `docs/experimentos/`
- `data/learning/pipeline/experiments/`
- `reports/audits/`
- `.hermes-worklog/`
- scripts experimentales.

Por experimento registrar:

- hipótesis;
- dataset;
- universo;
- features;
- outcome;
- baseline;
- controles;
- ablaciones;
- horizonte;
- PIT;
- `n`;
- OOS;
- walk-forward;
- embargo / purging cuando corresponda;
- resultado;
- limitaciones;
- veredicto.

Clasificar como:

`VALIDATED / SUPPORTED / FALSIFIED / INCONCLUSIVE / INVALID_PIT / INVALID_DATA / DUPLICATE / OBSOLETE`.

**GATE A7:** inventario experimental completo y estados reconciliados.

---

# 2. TRAMO B — DESCUBRIMIENTO DEL LABORATORIO DE LECTURA DE MERCADO

Sólo después del Tramo A se diseñan o ejecutan experimentos nuevos.

## B1 — SEQUENTIAL ICT

Hipótesis central:

```text
LIQUIDITY
→ SWEEP
→ DISPLACEMENT
→ STRUCTURE
→ OB
→ FVG
→ RETEST
```

Estudiar también ablaciones por profundidad para descubrir en qué etapa aparece información incremental.

Comparar, como mínimo:

- `SWEEP → DISPLACEMENT`
- `SWEEP → DISPLACEMENT → STRUCTURE`
- `... → OB`
- `... → FVG`
- `... → RETEST`

No exigir la cadena completa si eso destruye la potencia estadística; medir profundidad mínima con `n` suficiente.

## B2 — WYCKOFF × ICT CONFLICT

Comparar:

```text
ICT ALIGNED / NEUTRAL / AGAINST
```

con:

```text
WYCKOFF PRO_TREND / COUNTERTREND / TRANSITION / NEUTRAL
```

Medir si Wyckoff aporta información incremental al Context State ICT.

## B3 — SWEEP × SPRING / UPTHRUST

Determinar si `SPRING` y `UPTHRUST` son únicamente otra etiqueta para determinados sweeps o si aportan información nueva.

Comparar:

```text
SWEEP
SWEEP + SPRING
SWEEP + UPTHRUST
SWEEP + otras evidencias Wyckoff
```

## B4 — DISPLACEMENT QUALITY

No tratar displacement como booleano.

Investigar intensidad y calidad mediante variables causales compatibles con el motor, por ejemplo:

- rango relativo;
- body/range;
- expansión frente a contexto previo;
- continuidad;
- velocidad;
- distancia recorrida;
- capacidad de ruptura de estructura.

Clasificaciones tentativas: `WEAK / NORMAL / STRONG / EXTREME`, sujetas a validación.

## B5 — WYCKOFF EFFORT / RESULT

Investigar si esfuerzo alto con resultado bajo aporta información sobre absorción, agotamiento o transición.

`tick_volume` de FX se considera **relativo/exploratorio**, no volumen centralizado verdadero.

Comparar esfuerzo/resultado contra la secuencia ICT y contra baseline.

## B6 — FVG / OB FRESHNESS

Comparar:

```text
fresh
1-touch
multi-touch
partial mitigation
invalidated
```

para FVG y OB, siempre bajo una definición causal y consistente.

## B7 — TIMING / KILLZONES

Estudiar si una misma secuencia cambia de distribución según ventana temporal, incluyendo las killzones relevantes que existan en la arquitectura.

No introducir una nueva semántica horaria sin contrato documentado.

## B8 — MFE / MAE BEHAVIOUR

Avanzar desde el simple `end > 0` hacia una firma de comportamiento:

- MFE;
- MAE;
- MFE/MAE;
- time-to-MFE;
- time-to-MAE;
- continuación;
- reversión;
- mitigación.

Esto debe coexistir con outcomes simples para trazabilidad.

## B9 — SEQUENCE × CONTEXT STATE

Medir cómo cambia la distribución de outcomes de una misma secuencia según `CTX_ALIGNED`, `CTX_NEUTRAL`, `CTX_AGAINST`.

Si un bucket crítico tiene `n < 30`, marcar `INSUFFICIENT_N` y no declarar edge.

## B10 — ABLATION / INFORMACIÓN INCREMENTAL

Construir una matriz de componentes:

```text
BASELINE
BASELINE + SEQUENCE
SEQUENCE + OB
SEQUENCE + FVG
SEQUENCE + OB + FVG
SEQUENCE + CONTEXT
SEQUENCE + WYCKOFF
SEQUENCE + CONTEXT + WYCKOFF
```

Objetivo: determinar qué componente aporta información adicional y cuál sólo duplica información existente.

**REGLA:** no crear scores arbitrarios sumando flags. La suma de etiquetas no constituye setup.

---

# 3. TRAMO C — REGLAS DE METODOLOGÍA EXPERIMENTAL

Todos los experimentos de lectura de mercado deben:

- ser point-in-time;
- usar datos versionados;
- registrar baseline;
- usar controles y ablaciones;
- registrar `n` efectivo;
- guardar artefactos reproducibles;
- separar entrenamiento/validación/OOS cuando aplique;
- utilizar walk-forward cuando corresponda;
- registrar limitaciones y posibles explicaciones alternativas;
- conservar resultados negativos.

### Veredictos permitidos

- `SUPPORTED`
- `FALSIFIED`
- `INCONCLUSIVE`
- `INVALID_PIT`
- `INVALID_DATA`

### Política de muestra

Resultados favorables con muestra pequeña se clasifican como `INCONCLUSIVE`.

No se promueve una hipótesis por una única ventana temporal o por un win-rate atractivo con `n` insuficiente.

---

# 4. TRAMO D — PROMOTION GATE

Separación obligatoria:

```text
PRODUCTION ENGINE
        ↓
EXPERIMENTAL LAB
        ↓
REPORTS / EVIDENCE
        ↓
PROMOTION GATE
```

Para promocionar una hipótesis a producción se exige, según corresponda:

- PIT seguro;
- datos fiables;
- `n` suficiente;
- baseline;
- estabilidad temporal;
- OOS;
- walk-forward;
- reproducibilidad;
- tests;
- evidencia de información incremental;
- ausencia de una explicación alternativa obvia.

El paso a producción debe ser explícito:

`SHADOW -> CANDIDATE -> CONTRACTED -> PRODUCTION`

Nunca automático.

---

# 5. TRAMO E — GESTIÓN DE WYCKOFF EN PRODUCCIÓN

Wyckoff permanece subordinado al motor ICT:

```text
HTF / Context State
        ↓
ITF / POI / Sequence
        ↓
Wyckoff evidence layer
        ↓
LTF ICT confirmation
```

La salida debe describir, cuando corresponda:

- fase;
- eventos;
- esfuerzo/resultado;
- estado `PRO_TREND / COUNTERTREND / TRANSITION / NEUTRAL`;
- `ALIGNED / CONFLICT / UNRESOLVED`;
- evidencia y `authority_tf`.

Wyckoff no modifica por sí mismo `direction_hint` y no genera órdenes.

---

# 6. TRAMO F — PIPELINE DE APRENDIZAJE EXISTENTE

Los bloques originales del pipeline de aprendizaje se mantienen como una segunda pista de investigación y deben ejecutarse después de que la auditoría maestra haya establecido la integridad de datos, contratos y temporalidad.

## BLOQUE 0 — BASELINE INMUTABLE 🧊

Ejecutar EXACTAMENTE el pipeline actual (sin modificar). Guardar:

- commit;
- hash de código (`git rev-parse`);
- hash de datasets (`sha256` de features_all);
- símbolos, TF y `n`;
- distribución de labels (`nature / teacher_class / label_ep`);
- features usadas;
- train/val/test actual;
- ROC-AUC;
- PR-AUC;
- Brier / calibración;
- matriz de confusión;
- métricas por período / símbolo / régimen cuando existan.

Genera:
`data/learning/experiments/BASELINE-001/{manifest,metrics,dataset_stats,environment}.json`

**GATE 0:** baseline reproducible grabado. NO se toca el pipeline hasta aquí.

## BLOQUE 1 — AUDITORÍA DE DATASET Y LABEL 🔬

Auditar `label_ep` y `nature` (`reclaim / bos_confirm / range`):

- ¿qué representa?
- ¿usa información futura?
- ¿cuánto futuro mira?
- ¿distribución por símbolo / TF / año?
- stability report: N, class dist, positive rate, duplicate rate, temporal coverage.

**GATE 1:** si label tiene leakage, inestabilidad extrema o definición incorrecta -> NO se entrena.

## BLOQUE 2 — DATASET FACTORY MULTI-PAR 🏭

8 símbolos x TF x períodos. Cada dataset = manifest inmutable:

`{dataset_id, symbol, tf, period, generator_commit, feature_schema, label_schema, rows, sha256}`

Orden acordado: EURUSD multi-TF + walk-forward primero; expansión multi-símbolo después para aislar variables.

## BLOQUE 3 — WALK-FORWARD REAL 📈

Eliminar `train_test_split` para el experimento. Folds temporales roll-forward y métricas por fold.

Prioridad: PR-AUC > ROC-AUC > Recall > Precision > F1 > Brier > base rate > estabilidad entre folds.

## BLOQUE 4 — NATURE HEAD 🧠

Comparar Majority / Random / LogisticRegression / current model / nature head. Si el modelo sofisticado no supera baselines de forma consistente -> NO se promociona.

## BLOQUE 5 — ABLATION LAB 🧪

A=teacher, B=nature, C=context; combinaciones A/B/C/A+B/A+C/B+C/A+B+C. Medir ΔPR-AUC, Δcalibration, Δprecision, Δrecall y ΔOOS stability.

## BLOQUE 6 — SCORE FINAL ⚖️

NO pesos arbitrarios. Pesos sólo en TRAIN, congelados y evaluados OOS. Comparar teacher only / nature only / teacher+nature / +context.

## BLOQUE 7 — GENERALIZACIÓN Y REGÍMENES 🌎

FX majors / crosses / Gold x {Bull,Bear,Range,HighVol,LowVol} y análisis de estabilidad por régimen.

## BLOQUE 8 — GATE DE PRODUCCIÓN 🚦

Sólo si bloques previos PASS. El aprendizaje pasa por `SHADOW MODE` y sólo después puede convertirse en `CANDIDATE -> CONTRACTED -> bias_from_tools`.

---

# 7. ESTRUCTURA DE CARPETAS DEL LABORATORIO

La estructura existente se conserva y se utiliza como fuente de verdad experimental:

```text
data/learning/pipeline/
├── STATE.json
├── PAUSE
├── RUN.lock
├── manifests/
├── checkpoints/
├── experiments/
└── reports/
```

Experimentos de lectura de mercado:

```text
docs/experimentos/
reports/audits/
data/learning/pipeline/experiments/
```

Worklogs:

```text
.hermes-worklog/
```

Planes:

```text
.hermes/plans/
```

Cada experimento debe enlazar hipótesis -> código -> artefacto numérico -> reporte -> veredicto.

---

# 8. BLACK BOX / COMANDOS DE CONTROL

Mantener los comandos existentes cuando apliquen:

- `learning_pipeline.py status` -> bloque/step/symbol/tf/model/dataset/commit/Δ vs baseline
- `learning_pipeline.py explain` -> arquitectura y componentes activos
- `learning_pipeline.py why` -> por qué la calidad no subió, con evidencia

Agregar o mantener, si ya existen, equivalentes para el laboratorio de lectura:

- estado de auditoría;
- estado de experimentos;
- último gate;
- último artefacto;
- estado PIT;
- `n` por bucket.

---

# 9. CONTROL DE PAUSA / REANUDACIÓN

- `STATE.json`: `current_block`, `current_step`, `last_completed_step`, `dataset_id`, `experiment_id`, `git_commit`, `started_at`, `updated_at`.
- `PAUSE`: si existe, runner se detiene limpio al inicio del siguiente bloque y conserva checkpoint.
- `resume`: continúa desde `last_completed_step`.
- Los experimentos largos deben dejar artefactos parciales verificables y no sobreescribir resultados anteriores.

---

# 10. ORDEN DE EJECUCIÓN MAESTRO

### Primera prioridad — integridad

`A1 -> A2 -> A3 -> A4 -> A5 -> A6 -> A7`

### Segunda prioridad — lectura de mercado

`B1 -> B2 -> B3 -> B4 -> B5 -> B6 -> B7 -> B8 -> B9 -> B10`

### Tercera prioridad — aprendizaje ML

`B0 -> G0 -> B1(label) -> G1 -> B2 -> B3 -> B4 -> G4 -> B5 -> B6 -> B7 -> B8`

Si la auditoría descubre un bloqueo crítico o un problema PIT, debe detenerse la promoción y corregirse primero la causa.

**Sin saltar etapas. Sin promoción automática. Sin maquillar resultados.**

---

# 11. OBJETIVO FINAL

El objetivo del pipeline maestro no es producir más señales.

Es descubrir, mediante evidencia reproducible, **qué representación temporal del mercado realmente mejora la calidad de la lectura ICT**.

La salida deseada es:

```text
MENOS SEÑALES
      ↓
MÁS EVIDENCIA
      ↓
MEJOR CONTEXTO
      ↓
MEJOR SECUENCIA
      ↓
MAYOR ESTABILIDAD OOS
      ↓
REGLAS MÁS SIMPLES Y EXPLICABLES
```

El sistema debe poder explicar no sólo por qué una hipótesis funciona, sino también por qué otra fue falsada, por qué una muestra no tiene potencia suficiente y qué evidencia falta antes de promover una modificación.