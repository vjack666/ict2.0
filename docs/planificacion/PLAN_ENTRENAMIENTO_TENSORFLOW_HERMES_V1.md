# Plan de trabajo — Entrenamiento IA TensorFlow Hermes v1

**Fecha:** 2026-09-15  
**Owner:** Codex / CEO operativo  
**Modo:** LOCAL_ONLY  
**Entorno objetivo:** `.venv` con Python 3.11.15 y TensorFlow 2.21.0  
**Estado:** PLAN OPERATIVO — NO EJECUTADO  
**Contrato vigente:** `docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md`  
**Contrato IA base:** `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md`  
**Frontera:** entrenamiento/evaluacion local sobre datos existentes e inmutables; `can_trade=false`

## 1. Explicacion como profesor

Una red neuronal no es una señal de trading. Es una funcion matematica con
pesos internos que aprende a transformar ejemplos historicos en una
probabilidad. En Hermes, el ejemplo historico debe ser un evento ICT ya
materializado con features disponibles en el momento de decision. La salida
puede ser algo como:

```text
continuation = 0.42
reversal     = 0.31
failure      = 0.27
```

Eso significa: "segun lo aprendido en los datos de investigacion, este evento
se parece en cierto grado a ejemplos pasados de cada clase". No significa
comprar, vender, abrir demo, mover SL ni cambiar `can_trade=false`.

La red aprende por comparacion. Primero recibe features de entrada, calcula una
prediccion, compara esa prediccion contra la etiqueta historica y ajusta pesos
para reducir el error. Ese ciclo se repite solo sobre TRAIN. VALIDATION sirve
para observar si el modelo empieza a generalizar. TEST/OOS se toca una sola vez
al final para evaluar honestamente.

La regla docente central es:

```text
features_at_t <= decision_time < outcome
```

Si una feature usa informacion posterior a la decision, la IA no esta
aprendiendo; esta copiando el futuro. Ese error se llama leakage y vuelve
inservible el resultado aunque las metricas parezcan buenas.

## 2. Objetivo de la mision

Preparar la continuacion del entrenamiento de redes neuronales con TensorFlow
para Hermes, partiendo de la infraestructura existente de `runtime/ai_learning`
y de los artefactos B1/V2 ya orientados a corpus causal.

El primer objetivo no es encontrar una estrategia rentable. El primer objetivo
es producir un ciclo reproducible:

1. corpus causal verificable;
2. split temporal congelado;
3. baseline determinista comparable;
4. modelo TensorFlow entrenado solo con TRAIN;
5. evaluacion VALIDATION y TEST/OOS separada;
6. calibracion, abstencion y drift;
7. reporte honesto con PASS, REVIEW o BLOCKED;
8. prediccion Shadow Mode con `can_trade=false`.

## 3. Principios no negociables

- No modificar, sobrescribir, rellenar, reetiquetar, redescargar ni regenerar
  datasets existentes.
- No usar MT5 para entrenar este modelo; MT5 queda para Shadow Mode posterior.
- No elegir horizonte, features, filtros o thresholds despues de mirar OOS.
- No mezclar entrenamiento IA con autorizacion operativa.
- No convertir una mejora de accuracy en edge economico.
- No cambiar `can_trade=false`.
- No publicar ni hacer `git push` sin auditoria independiente e instruccion
  explicita.

## 4. Arquitectura propuesta

```text
Datos inmutables
  -> Manifest + hashes
  -> Corpus causal B1/V2
  -> Feature matrix TensorFlow
  -> Split temporal TRAIN / VALIDATION / TEST_OOS
  -> Baseline determinista
  -> Red neuronal TensorFlow
  -> Calibracion + abstencion + drift
  -> Shadow prediction can_trade=false
```

El entrenamiento TensorFlow debe integrarse como una capa nueva sobre los
contratos existentes, no como sustituto de ellos. La registry, checkpoints,
calibracion, abstencion y drift deben seguir usando `runtime/ai_learning`.

## 5. Red neuronal inicial recomendada

Para el primer ciclo, usar una red pequena y auditable antes de intentar
arquitecturas complejas:

```text
Input: features numericas y categoricas codificadas
Dense(64) + ReLU
Dropout(0.10)
Dense(32) + ReLU
Dense(3) + Softmax
```

Perdida:

```text
sparse_categorical_crossentropy
```

Metricas minimas:

```text
accuracy
macro_f1
log_loss
brier
confusion_matrix
per_class_precision_recall
calibration_curve
```

Por que empezar simple: si una red pequena no supera de forma limpia al
baseline y no se calibra bien, una red mas grande probablemente solo memorice
ruido. Primero se prueba si hay senal aprendible; despues se decide si conviene
mas capacidad.

## 6. Plan por fases

### Fase T0 — Estado del entorno

**Objetivo:** certificar que el entorno local puede entrenar.

Evidencia requerida:

- `.venv` usa Python 3.11.15.
- TensorFlow importa correctamente.
- `tf.__version__ == 2.21.0`.
- operacion tensorial minima produce resultado estable.
- comando y salida quedan en reporte.

Estado actual: preparado manualmente el 2026-09-15. Falta registrar la evidencia
en un artefacto de mision si se va a iniciar el ciclo formal.

### Fase T1 — Corpus causal entrenable

**Objetivo:** elegir el corpus congelado para el primer entrenamiento
TensorFlow.

Entradas candidatas:

- `B1_DATA_MANIFEST_V1.json`;
- corpus B1 DESIGN si ya existe y pasa gates;
- materializaciones V2 existentes bajo `data/materialized/` si su manifest,
  hashes y causalidad pasan.

Gate:

```text
DATA_MANIFEST PASS
LINEAGE PASS
NO_HOLDOUT PASS
CAUSAL_AUDIT PASS
DUPLICATES PASS
REPRODUCIBILITY PASS
```

Si el corpus no tiene soporte suficiente por clase, el resultado es
`BLOCKED_INSUFFICIENT_CLASS_SUPPORT`; no se inventan filas ni se relajan clases.

### Fase T2 — Feature matrix TensorFlow

**Objetivo:** transformar el corpus causal en tensores sin perder lineage.

Reglas:

- normalizadores ajustados solo con TRAIN;
- categorias congeladas desde TRAIN;
- valores faltantes como `UNAVAILABLE` o mascara explicita, nunca como falso
  silencioso;
- feature schema versionado;
- hash de matriz TRAIN/VALIDATION/TEST_OOS.

Entregables:

- script de preparacion;
- `feature_schema.json`;
- `split_manifest.json`;
- `tensor_manifest.json`;
- test de no leakage.

### Fase T3 — Baseline

**Objetivo:** comparar la red contra algo simple y estable.

Baselines minimos:

- clase mayoritaria;
- regresion/softmax determinista existente;
- baseline por contexto si ya existe contrato.

Regla:

```text
sin baseline no hay lectura honesta de IA
```

Una red que gana por poco en accuracy pero empeora log-loss o calibracion queda
en `REVIEW`, no en PASS.

### Fase T4 — Entrenamiento TensorFlow

**Objetivo:** entrenar el primer modelo neuronal reproducible.

Configuracion inicial:

```text
seed = 20260915
epochs = 50
batch_size = 256
optimizer = Adam(learning_rate=0.001)
early_stopping = validation_loss patience 8
class_weight = solo si TRAIN muestra desbalance material y queda documentado
```

El entrenamiento escribe en ruta nueva:

```text
data/ml/tensorflow/<run_id>/
```

Contenido minimo:

- `model.keras`;
- `training_config.json`;
- `metrics_train.json`;
- `metrics_validation.json`;
- `metrics_test_oos.json`;
- `predictions_test_oos.parquet` o `.jsonl`;
- `source_manifest.json`;
- `environment.json`;
- `audit.md`.

### Fase T5 — Evaluacion OOS

**Objetivo:** medir generalizacion sin tocar los pesos ni ajustar thresholds.

Checks:

- confusion matrix 3x3;
- precision/recall/F1 por clase;
- log-loss y Brier;
- curva de calibracion;
- cobertura por segmento: sesion, regimen, direccion HTF, ano/trimestre;
- guardia `N >= 30` por celda para interpretar segmentos.

Estados:

```text
PASS   = mejora clara, causal, reproducible y calibrada frente a baseline
REVIEW = mejora parcial, soporte bajo o calibracion dudosa
BLOCKED = leakage, hash roto, soporte insuficiente, OOS invalido o no reproducible
```

### Fase T6 — Calibracion, abstencion y drift

**Objetivo:** que el modelo sepa decir "no se".

Usar la infraestructura existente:

- `runtime/ai_learning/calibration.py`;
- `runtime/ai_learning/abstention.py`;
- `runtime/ai_learning/drift.py`;
- `runtime/ai_learning/model_registry.py`;
- `runtime/ai_learning/checkpoint_store.py`.

Una prediccion aceptada por la politica IA sigue siendo solo diagnostica:

```text
shadow_mode=true
can_trade=false
entry_authorized=false
```

### Fase T7 — Shadow Mode

**Objetivo:** comparar predicciones congeladas contra observaciones nuevas sin
intervenir en ejecucion.

Reglas:

- modelo congelado antes de Shadow;
- entrada MT5 solo como observacion actual;
- no entrenamiento online;
- no decision de trading;
- latencia, drift, abstencion y resultado posterior logueados.

### Fase T8 — Dictamen independiente

**Objetivo:** separar aprendizaje tecnico, edge economico y permiso operativo.

El dictamen D5 debe responder:

```text
La red entrena? si/no
Generaliza mejor que baseline? si/no/review
Esta calibrada? si/no/review
Tiene leakage? si/no
Tiene edge economico? no evaluado / no / review / si
Autoriza trading? no
```

## 7. Tareas especificas por perfil Hermes

### Codex / CEO operativo

```text
AGENTE: Codex
DEPARTAMENTO: D0 Direccion y gobierno
TAREA: abrir la mision TensorFlow, fijar alcance, verificar branch, dirty state, contratos y gates vivos.
STATUS: READY
EVIDENCIA: git status, contrato de enmienda, contrato IA v1, indice maestro.
ARCHIVOS: .hermes-index.md, docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md, docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md
RIESGOS: confundir entrenamiento exploratorio con TRAINING_ELIGIBLE o trading.
SIGUIENTE ACCION: emitir run_id de mision y asignar perfiles.
```

### Hermes / Director de laboratorio

```text
AGENTE: Hermes
DEPARTAMENTO: D6 Research / laboratorio
TAREA: definir el experimento TensorFlow preregistrado: target, horizonte, features, splits, baseline y criterio PASS/REVIEW/BLOCKED.
STATUS: READY
EVIDENCIA: preregistro con target congelado y prohibicion de OOS tuning.
ARCHIVOS: docs/experimentos/EXP_TENSORFLOW_AI_OUTCOME_V1_PREREGISTRATION.md
RIESGOS: cambiar horizonte o features despues de ver resultados.
SIGUIENTE ACCION: entregar preregistro antes de entrenar.
```

### Helix / Servidor de entrenamiento IA

```text
AGENTE: Helix
DEPARTAMENTO: D3 CAIO / IA
TAREA: implementar o ejecutar el trainer TensorFlow sobre corpus aprobado, guardar modelo, metricas, predicciones y entorno.
STATUS: WAITING_T1
EVIDENCIA: import TensorFlow, config, seed, logs, artefactos de run.
ARCHIVOS: scripts/lab/experiments/train_tensorflow_outcome_v1.py, data/ml/tensorflow/<run_id>/
RIESGOS: entrenar con corpus no causal, normalizar con VALIDATION/OOS, sobrescribir modelos previos.
SIGUIENTE ACCION: esperar corpus causal y split_manifest PASS.
```

### ict_assurance

```text
AGENTE: ict_assurance
DEPARTAMENTO: D5 CRO / assurance
TAREA: auditar causalidad, leakage, FULL/PREFIX, reproducibilidad, baseline y lectura honesta de metricas.
STATUS: READY
EVIDENCIA: reporte PASS/REVIEW/BLOCKED con pruebas y hashes.
ARCHIVOS: reports/audits/experiments/ai/tensorflow_outcome_v1_assurance.md
RIESGOS: aceptar accuracy como edge, aceptar OOS tocado durante diseno, aceptar soporte bajo por clase.
SIGUIENTE ACCION: revisar T1-T5 antes de cualquier Shadow Mode.
```

### ict_viewer_builder

```text
AGENTE: ict_viewer_builder
DEPARTAMENTO: D7 Delivery / interfaces
TAREA: preparar visualizacion diagnostica de predicciones Shadow: probabilidades, confianza, abstencion, drift y explicacion de features.
STATUS: WAITING_MODEL
EVIDENCIA: UI local mostrando can_trade=false y entry_authorized=false en todo momento.
ARCHIVOS: runtime/desktop_terminal/ui/src/App.jsx, runtime/desktop_terminal/
RIESGOS: que la UI parezca una recomendacion de entrada.
SIGUIENTE ACCION: disenar panel solo despues de modelo congelado y politica INF-7.
```

### ict_monitor

```text
AGENTE: ict_monitor
DEPARTAMENTO: D2 Ingenieria diaria / monitoreo
TAREA: checks livianos de entorno, existencia de artefactos, frescura de logs y estado Shadow Mode sin ejecutar entrenamiento pesado.
STATUS: READY
EVIDENCIA: snapshots locales de entorno, hashes y ultimos artefactos.
ARCHIVOS: reports/audits/experiments/ai/, data/ml/tensorflow/
RIESGOS: confundir monitoreo con auditoria o con entrenamiento.
SIGUIENTE ACCION: generar resumen solo ante cambio significativo o fallo.
```

### Departamento B / Dataset experimental

```text
AGENTE: Dataset Experimental
DEPARTAMENTO: D4 CDO / datos
TAREA: seleccionar corpus causal congelado y producir manifest de tensores sin modificar datos fuente.
STATUS: READY
EVIDENCIA: source_manifest, tensor_manifest, row counts, hashes, split temporal.
ARCHIVOS: B1_DATA_MANIFEST_V1.json, data/materialized/, data/ml/tensorflow/<run_id>/tensor_manifest.json
RIESGOS: tocar HOLDOUT, deduplicar sin regla, perder candidatos negativos.
SIGUIENTE ACCION: entregar T1/T2 con DATA_MANIFEST y LINEAGE.
```

### Red Team

```text
AGENTE: Red Team
DEPARTAMENTO: D5 Assurance adversarial
TAREA: intentar romper el pipeline buscando leakage, labels filtradas, duplicados, OOS tuning, clases colapsadas y features futuras.
STATUS: READY
EVIDENCIA: lista de ataques, resultados y veredicto por ataque.
ARCHIVOS: reports/audits/experiments/ai/tensorflow_outcome_v1_red_team.md
RIESGOS: revisar solo outputs felices y no inputs.
SIGUIENTE ACCION: atacar antes de aceptar cualquier mejora.
```

## 8. Orden recomendado de ejecucion

1. D0 abre mision y congela alcance.
2. D4 certifica corpus y split.
3. D5 audita causalidad pre-entrenamiento.
4. D6 registra preregistro.
5. D3 ejecuta entrenamiento TensorFlow.
6. D3 evalua VALIDATION y TEST/OOS sin retocar modelo.
7. D5 y Red Team auditan resultados.
8. D7 prepara vista Shadow si y solo si el modelo queda congelado.
9. D0 cierra con worklog, indice, Graphify y commit local selectivo si aplica.

## 9. Primer bloque ejecutable sugerido

Antes de entrenar, ejecutar solo checks de preparacion:

```powershell
.\.venv\Scripts\python.exe -c "import tensorflow as tf; print(tf.__version__)"
.\.venv\Scripts\python.exe -m pytest tests/test_ai_learning_training_pipeline.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_ai_learning_outcome_classifier.py -q
```

Si esos checks pasan, continuar con el script de auditoria de corpus. Si fallan,
el estado de la mision es `BLOCKED_TECHNICAL_ENVIRONMENT` y se corrige antes de
usar datos.

## 10. Criterio de cierre

La mision TensorFlow v1 puede declararse cerrada solo con:

- artefactos de entrenamiento reproducibles;
- hashes de entrada/salida;
- split temporal congelado;
- metricas separadas TRAIN/VALIDATION/TEST_OOS;
- baseline comparado;
- calibracion y abstencion evaluadas;
- auditoria D5;
- Red Team;
- `can_trade=false` confirmado en outputs;
- documentacion y worklog actualizados.

El cierre puede ser positivo aunque el resultado cientifico sea negativo. Un
`NO_EDGE`, `REVIEW` o `BLOCKED` honesto tambien es progreso si deja evidencia
reproducible y no fabrica permisos.
