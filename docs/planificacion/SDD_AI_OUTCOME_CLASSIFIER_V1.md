# SDD — IA de outcomes ICT v1

**Estado:** IMPLEMENTADO COMO BASELINE; ENTRENAMIENTO CIENTÍFICO PENDIENTE
**Contrato:** `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md`
**Alcance:** clasificador histórico de `continuation/reversal/failure`.

La línea intradía Wyckoff×ICT se especifica en el addendum
`docs/experimentos/EXP_WYCKOFF_ICT_INTRADAY_ADDENDUM.md`. Reutiliza este
clasificador y `TrainingPipeline` con el perfil explícito
`INTRADAY_FEATURE_NAMES`; no crea una segunda registry ni una política nueva.

## 1. Arquitectura

```text
Dukascopy histórico
        ↓
DatasetSnapshot certificado
        ↓
TrainingPipeline INF-4 (split temporal y lineage)
        ↓
Softmax multinomial determinista
        ↓
VALIDATION + TEST/OOS
        ↓
INF-6 calibración → INF-7 abstención → INF-8 drift
        ↓
Shadow Mode MT5 (futura etapa, can_trade=false)
```

MT5 no se mezcla con el entrenamiento histórico. Su papel posterior será
actualizar la punta y probar el modelo congelado en observación.

## 2. Componentes implementados

- `runtime/ai_learning/outcome_classifier.py`: baseline, serialización,
  predicción y bloqueo por autorización científica.
- `runtime/ai_learning/training_pipeline.py`: certificación del snapshot,
  lineage del modelo y split temporal reutilizados.
- `runtime/ai_learning/abstention.py`: decisión fail-closed INF-7.
- `runtime/ai_learning/calibration.py` y `drift.py`: interfaces posteriores,
  aún no aplicadas a un modelo real.

## 3. Secuencia de trabajo

### A0 — Dataset científico

Crear o seleccionar un nuevo experimento pre-registrado usando Dukascopy,
resolver la insuficiencia de muestra y producir un snapshot certificado. No se
puede usar el snapshot pequeño actual para declarar aprendizaje.

Para Wyckoff intradía, A0 exige datos H1 y M15 históricos sincronizados. El
primer bloque diagnóstico 2006–2010 puede producir un artefacto de prueba, pero
permanece fuera de `TRAINING_ELIGIBLE` hasta cerrar provenance, causalidad y la
separación cronológica con HOLDOUT 2021–2025.

### A1 — Entrenamiento baseline

Registrar un modelo compatible en `ModelRegistry`, suministrar autorización
`TRAINING_ELIGIBLE`, entrenar solo TRAIN y guardar el artefacto inmutable.

Para la línea intradía, antes de solicitar `TRAINING_ELIGIBLE` se ejecuta una
comparación diagnóstica con tres perfiles sobre el mismo corpus y split:
`ICT_ONLY`, `WYCKOFF_ONLY` y `WYCKOFF_ICT_COMBINED`. Esta comparación no elige
parámetros con TEST/OOS, no usa el HOLDOUT 2021–2025 y no crea una segunda
registry.

### A2 — Evaluación

Medir baseline, VALIDATION y TEST/OOS; calcular calibración y revisar que el
resultado no sea un efecto de una sola clase, período o horizonte.

La comparación intradía debe reportar también el baseline de clase mayoritaria,
la diferencia de cada perfil frente a ese baseline y si Wyckoff añade
información incremental a ICT. Un resultado cercano al baseline permanece en
`REVIEW`, aunque el ajuste técnico haya terminado.

### A1.5 — Optimización controlada intradía

Después de la comparación baseline y antes del HOLDOUT final se permite una
búsqueda acotada y pre-registrada. La búsqueda puede variar únicamente los
perfiles `ICT_ONLY`, `WYCKOFF_ONLY`, `WYCKOFF_ICT_COMBINED`, `learning_rate` y
`l2` dentro de la rejilla congelada en el addendum intradía. Cada candidato
entrena solo con TRAIN.

La selección se realiza exclusivamente por `validation.log_loss` menor; los
empates se resuelven por `validation.accuracy` mayor y después por orden
determinista de la rejilla. TEST/OOS puede quedar reportado como diagnóstico,
pero está prohibido usarlo para elegir el candidato. El HOLDOUT 2021–2025 no se
lee en esta fase. El candidato ganador se congela con su hash, configuración y
commit antes de cualquier evaluación final.

Si ningún candidato mejora materialmente al baseline, se conserva el baseline
y se registra `NO_MATERIAL_IMPROVEMENT`; cambiar la rejilla o la etiqueta exige
un nuevo pre-registro.

La selección automática del mejor valor de la métrica solo produce un
`technical_candidate`; no decide que la mejora sea material, no modifica el
baseline publicado y no concede `TRAINING_ELIGIBLE`. Esa decisión requiere
auditoría independiente y comparación fuera de muestra.

### A2.5 — HOLDOUT final del candidato congelado

Después de A1.5 se congela un único candidato y se evalúa una sola vez sobre
HOLDOUT 2021–2025. El runner no importa entrenamiento ni modifica pesos: solo
rehidrata el artefacto serializado y calcula métricas sobre observaciones cuyo
`event_time` pertenece al intervalo `[2021-01-01, 2026-01-01)`. Enero de 2026
puede usarse únicamente como warmup para completar el outcome de las últimas
12 velas de diciembre de 2025.

El HOLDOUT no puede seleccionar perfiles, hiperparámetros, etiquetas, features,
SL/TP ni reglas. Si la fuente presenta anomalías, licencia o lineage sin
resolver, el resultado mecánico se conserva como `REVIEW/BLOCKED` y no se
convierte en evidencia científica certificada. MT5 queda fuera de esta fase:
es el endpoint operativo futuro, no un sustituto de M15 histórico.

El informe debe incluir: hashes por archivo, cobertura y huecos, anomalías sin
corrección silenciosa, hash y commit del artefacto C10, `fit_executed=false`,
baseline mayoritario, métricas globales y por año, `shadow_mode=true` y
`can_trade=false`.

### A3 — Shadow MT5

Consumir el snapshot operativo MT5 actual con el modelo congelado, medir
coverage/confianza/abstención y drift. No alterar Context State, Lifecycle ni
la autoridad de órdenes.

### A4 — Promoción separada

Solo con evidencia suficiente y decisión explícita: crear contrato de
ejecución. Esta SDD no autoriza broker, órdenes ni `can_trade=true`.

## 4. Definition of Done v1

- código determinista y serializable;
- dataset certificado y lineage verificable;
- split temporal sin leakage;
- métricas TRAIN/VALIDATION/TEST separadas;
- HOLDOUT final evaluado con candidato congelado y sin reajuste;
- calibración, dominio y abstención documentados;
- Shadow Mode explícito;
- cero órdenes y cero promoción automática.
