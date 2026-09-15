# Plan de trabajo — Linea de aprendizaje Failure Anatomy v1

**Fecha:** 2026-09-15  
**Owner:** Codex / CAIO Hermes  
**Modo:** LOCAL_ONLY  
**Estado:** LINEA ABIERTA — NO ENTRENADA  
**Linea anterior relacionada:** `tf_outcome_v1_003`  
**Politica:** `can_trade=false`, `shadow_mode=true`  
**Frontera:** aprendizaje diagnostico sobre datos existentes e inmutables; no promocion, no trading, no descarga

## 1. Explicacion como profesor

La red `tf_outcome_v1_003` ya empezo a aprender la diferencia general entre
`continuation`, `reversal` y `failure`. Su avance mas importante fue que dejo
de ignorar completamente los fallos: `failure` paso de recall `0.0769` en
v1.002 a `0.2308` en v1.003.

Pero todavia no entiende bien la anatomia del fallo. Es decir: sabe reconocer
algunos eventos que parecen fallar, pero no tiene una linea especializada para
aprender por que fallan.

Esta nueva linea se abre para ensenarle una pregunta mas precisa:

```text
Cuando una secuencia ICT falla, que sintomas existian antes del resultado?
```

La linea actual `tf_outcome_v1_003` responde:

```text
Que resultado es mas probable: continuation, reversal o failure?
```

La nueva linea `failure_anatomy_v1` debe responder:

```text
Que riesgo de fallo tiene esta secuencia y que factores lo explican?
```

Primero se entrenan separadas. Despues, si la nueva linea demuestra evidencia
honesta, se une con la red de outcome como una senal auxiliar de riesgo.

## 2. Antes y ahora

### Antes: outcome general v1.003

La red mira una secuencia y reparte probabilidad entre tres clases:

```text
continuation
reversal
failure
```

Aprendio mejor continuation y reversal que failure:

```text
TEST_OOS = 76
accuracy = 0.5132
balanced_accuracy = 0.5158
failure recall = 0.2308
failure F1 = 0.2609
status = REVIEW
```

Lectura: la red ya encontro patrones utiles, pero el fallo sigue siendo la
clase mas debil y con soporte OOS bajo.

### Ahora: nueva linea Failure Anatomy

La nueva linea no intenta reemplazar la v1.003. Se abre como una rama de
aprendizaje separada para estudiar fallos con mas lupa.

La salida esperada inicial no es una orden ni una entrada; es diagnostica:

```text
failure_risk = 0.00 .. 1.00
failure_drivers = lista de causas candidatas observadas antes del resultado
abstain_reason = si la evidencia no alcanza
```

## 3. Que tiene que aprender ahora

La siguiente leccion de las neuronas es aprender precursores de fallo. La lista
inicial queda congelada como hipotesis de laboratorio:

1. **Conflicto HTF:** direccion de secuencia opuesta o debil frente a D1/H4/H1.
2. **Contexto adverso:** `context_bucket=AGAINST` o neutralidad persistente.
3. **Secuencia inmadura:** poca profundidad, etapas incompletas o estructura
   aun no confirmada.
4. **Restriccion contradictoria:** ejemplo, sesgo alcista con `allow_long=false`
   o bajista con `allow_short=false`.
5. **Debilidad de estructura:** ausencia o baja calidad de BOS/CHOCH,
   displacement, retest, FVG/OB o relacion causal cuando existan esas columnas.
6. **Regimen no aprendido:** segmentos con soporte bajo, drift temporal o
   combinaciones no vistas en TRAIN.
7. **Ambiguedad direccional:** `direction_hint` o bias de temporalidades
   mezclados sin autoridad clara.

La regla clave es que todos esos sintomas deben existir antes del resultado.
Nada de mirar el futuro.

## 4. Arquitectura de aprendizaje separada

```text
SEQ_CTX_01 / corpus causal
  -> matriz failure_anatomy_v1
  -> target binario: is_failure
  -> modelo failure_risk_v1
  -> explicacion de drivers
  -> calibracion + abstencion
  -> reporte REVIEW/PASS/BLOCKED
```

Target inicial:

```text
is_failure = 1 si label_end_6 == failure
is_failure = 0 si label_end_6 in {continuation, reversal}
```

El primer modelo recomendado debe ser conservador:

```text
Input: features causales disponibles en decision_time
Dense(48) + ReLU
Dropout(0.10)
Dense(24) + ReLU
Dense(1) + Sigmoid
```

Metricas minimas:

```text
recall_failure
precision_failure
balanced_accuracy
log_loss
brier
ECE
confusion_matrix
coverage_at_abstention
segment_support
```

## 5. Plan por fases

### Fase F0 — Contrato y procedencia

**Objetivo:** confirmar que el corpus usado para fallo es el mismo linaje
causal, sin descargas ni mutacion de data.

Evidencia:

- hashes de fuente;
- split temporal congelado;
- columnas usadas disponibles en `decision_time`;
- `can_trade=false`;
- bitacora de apertura.

Estado inicial: abierto con evidencia de `tf_outcome_v1_003`; no entrenado.

### Fase F1 — Taxonomia de fallo

**Objetivo:** escribir el contrato `FAILURE_TAXONOMY_V1`.

Categorias iniciales:

```text
HTF_CONFLICT
ADVERSE_CONTEXT
IMMATURE_SEQUENCE
CONSTRAINT_CONTRADICTION
WEAK_STRUCTURE
LOW_SUPPORT_REGIME
DIRECTIONAL_AMBIGUITY
UNKNOWN
```

La taxonomia no reetiqueta el outcome historico. Solo describe causas
candidatas observables antes del resultado.

### Fase F2 — Dataset failure_anatomy_v1

**Objetivo:** materializar una matriz nueva, separada de `tf_outcome_v1_003`.

Entregables:

- `feature_schema.json`;
- `split_manifest.json`;
- `source_manifest.json`;
- `failure_driver_manifest.json`;
- dataset local bajo `data/ml/tensorflow/failure_anatomy_v1/`.

Regla: no se modifica ningun dataset fuente.

### Fase F3 — Entrenamiento failure_risk_v1

**Objetivo:** entrenar un detector binario de riesgo de fallo.

Salida esperada:

```text
failure_risk
calibrated_failure_risk
abstain_flag
top_failure_drivers
```

Estado posible:

- `PASS`: mejora reproducible, calibrada y con soporte suficiente.
- `REVIEW`: aprende algo, pero soporte/calibracion aun no alcanzan.
- `BLOCKED`: corpus insuficiente, leakage, hashes inconsistentes o fallo de
  procedencia.

### Fase F4 — Auditoria independiente

**Objetivo:** verificar que el modelo no aprendio futuro ni ruido.

Checks:

- no leakage;
- FULL/PREFIX cuando el productor original este disponible;
- soporte por clase y segmento;
- calibracion;
- reproducibilidad;
- comparacion contra baseline simple.

### Fase F5 — Union futura con v1.003

La union se permite solo si `failure_anatomy_v1` cierra al menos en `REVIEW`
reproducible y sin fallos de procedencia.

Hay dos formas autorizadas de union:

1. **Late fusion:** mantener dos modelos separados. La salida de v1.003 se
   combina con `failure_risk_v1` en un calibrador final.
2. **Feature fusion:** usar `failure_risk` y drivers como features de una
   futura red `tf_outcome_v1_004` o `tf_outcome_v2`.

La primera union recomendada es `late fusion`, porque preserva trazabilidad:

```text
outcome_probs_v1_003 + failure_risk_v1 -> meta_calibrator_shadow
```

Ninguna union cambia `can_trade=false`.

## 6. Tareas por perfil Hermes

| Perfil | Departamento | Tarea | Entregable |
| --- | --- | --- | --- |
| Forge / Codex | D0-D1 Direccion y PMO | Mantener alcance, bitacora, Graphify y commits selectivos | plan, worklog, commit local |
| Helix / CAIO | D3 IA | Disenar matriz `failure_anatomy_v1` y entrenar `failure_risk_v1` | script, modelo, metricas |
| Dataset Experimental | D4 Datos | Verificar hashes, splits y fuente inmutable | manifest y dictamen de procedencia |
| ict_assurance | D5 Assurance | Auditar no leakage, soporte, calibracion y FULL/PREFIX | dictamen PASS/REVIEW/BLOCKED |
| Research / Lab | D6 Laboratorio | Definir hipotesis de drivers y segmentos | taxonomia y reporte experimental |
| Viewer Builder | D7 Interfaces | Preparar vista futura de riesgo/driver en Shadow Mode | propuesta UI, sin activacion |
| Red Team | D5 Riesgo | Buscar leakage, sobreajuste y falsas mejoras | reporte adversarial |

## 7. Criterio de cierre de esta linea

La linea `failure_anatomy_v1` no se considera lista para unir con v1.003 hasta
cumplir:

```text
PROVENANCE PASS
NO_LEAKAGE PASS
BASELINE_COMPARISON PASS o REVIEW documentado
FAILURE_RECALL mejora sobre v1.003
Brier/ECE no degradan materialmente
support por segmento suficiente o abstencion explicita
can_trade=false confirmado
```

## 8. Estado actual

```text
LINE = failure_anatomy_v1
STATUS = OPENED
TRAINING = NOT_STARTED
SOURCE = datos existentes e inmutables
MERGE_WITH_V1_003 = DEFERRED
SCIENTIFIC_PASS = NO
TRADING_AUTHORIZATION = NO
CAN_TRADE = false
```

Siguiente accion tecnica: crear el contrato de taxonomia `FAILURE_TAXONOMY_V1`
y luego materializar el dataset `failure_anatomy_v1` sin tocar HOLDOUT para
ajustar decisiones.
