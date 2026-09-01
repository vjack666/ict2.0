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
- calibración, dominio y abstención documentados;
- Shadow Mode explícito;
- cero órdenes y cero promoción automática.
