# Preregistro — EXP-AI-OUTCOME-FUNNEL-BACKTEST-01

**Estado:** PRE-REGISTRADO; no es una autorización de trading
**Fecha:** 2026-08-31
**Owner:** D3 IA / D4 Datos / D5 Assurance
**Modo:** `LOCAL_ONLY`
**Contrato de modelo:** `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md`

## 1. Pregunta

¿Puede un clasificador determinista aprender, sin información futura en sus
features, la clase de resultado de una unidad causal aceptada por el Funnel y
resuelta por el backtest canónico?

El objetivo es producir el primer artefacto de entrenamiento reproducible. No
es demostrar edge, rentabilidad, una señal ni autorización de órdenes.

## 2. Fuentes y separación

- **Investigación:** datos históricos Dukascopy y artefactos Funnel A7.
- **Outcome:** resultado causal del backtest canónico y/o su resolvedor de
  outcome, usando únicamente barras posteriores al evento.
- **Operación:** MT5 queda fuera del entrenamiento; solo podrá consumir un
  modelo congelado en una futura etapa Shadow.
- No se acepta `data/raw/*.parquet` MT5 como sustituto del dataset histórico.

## 3. Unidad y features

Una fila representa un evento o episodio aceptado por la cadena causal,
identificado de forma estable y observado en `event_time`. Las features se
congelan en ese instante y pueden incluir únicamente dirección, profundidad,
contexto MTF, etapas Funnel y relaciones ya publicadas.

Se prohíben labels, PnL, entry, SL, TP, `exit_time`, `outcome` y cualquier dato
posterior dentro de `features_at_t`. Las filas sin lineage completo, sin
timestamp, con conflicto de autoridad o con `can_trade != false` se rechazan.

## 4. Etiqueta congelada antes de entrenar

El generador debe documentar y aplicar una función determinista de etiqueta
antes de ajustar pesos. No se permite escoger el horizonte, la definición o
las exclusiones después de observar las métricas.

La taxonomía del clasificador es fija: `continuation`, `reversal`, `failure`.
Si el backtest no permite identificar las tres clases sin ambigüedad, el
dataset debe quedar `BLOCKED` y no se puede fabricar soporte sintético.

## 5. Gates

El entrenamiento solo puede ejecutar con todos estos estados:

1. Funnel A7 causal y FULL/PREFIX: `PASS`.
2. Backtest/resolvedor causal y reproducible: `PASS`.
3. Provenance de fuente, generador, hashes y snapshot: `PASS`.
4. Split temporal sin leakage: `PASS`.
5. Soporte mínimo por clase en TRAIN y filas mínimas en VALIDATION/TEST-OOS.
6. Gate externo explícito: `status=PASS`, `verdict=TRAINING_ELIGIBLE` y hash
   coincidente.

El generador debe devolver `BLOCKED` ante cualquier gate ausente; no puede
convertir `INSUFFICIENT_N`, `REVIEW` o `WAITING` en `TRAINING_ELIGIBLE`.

## 6. Métricas y lectura

Se reportan accuracy, log-loss, conteos por clase y cobertura de abstención en
TRAIN/VALIDATION/TEST-OOS. TEST/OOS no participa en ajuste ni selección.
Calibración y drift se ejecutarán en etapas separadas. Una métrica positiva no
autoriza promoción ni órdenes.

## 7. Reproducción y salida

La salida debe contener dataset hash, snapshot, schema, commits, semilla,
configuración, definición de label, conteos, métricas y `artifact_hash`.
Dos ejecuciones con el mismo snapshot y configuración deben producir el mismo
artefacto lógico.

## 8. Decisión prevista

- `TRAINING_ELIGIBLE`: permite obtener un baseline de investigación Shadow-only.
- Cualquier otro estado: no entrena y deja registrado el motivo.
- En ambos casos: `shadow_mode=true`, `can_trade=false`, sin broker, sin push y
  sin promoción automática.
