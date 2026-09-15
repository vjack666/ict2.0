# Worklog — Failure Anatomy v1 Materialization

**Fecha:** 2026-09-15  
**Agente:** Codex  
**Departamento:** D3 CAIO / D4 Datos / D5 Assurance  
**Estado:** COMPLETED  
**Modo:** LOCAL_ONLY  
**Politica:** `can_trade=false`

## Solicitud

Continuar con la nueva linea de aprendizaje abierta para que las neuronas
aprendan la anatomia del fallo y despues puedan unir ese conocimiento con la
red `tf_outcome_v1_003`.

## Plan ejecutado

1. Crear el contrato `FAILURE_TAXONOMY_V1`.
2. Crear el materializador `materialize_failure_anatomy_v1.py`.
3. Generar artefactos locales bajo `data/ml/tensorflow/failure_anatomy_v1/`.
4. Verificar que no se modifican datasets fuente y que `can_trade=false`
   permanece vigente.
5. Actualizar Graphify y cerrar con commit selectivo.

## Resultado

Se ejecuto:

```text
.venv\Scripts\python.exe scripts\lab\experiments\materialize_failure_anatomy_v1.py
```

Artefactos generados localmente:

```text
data/ml/tensorflow/failure_anatomy_v1/
```

Conteos:

```text
TRAIN      n=120 failure=25
VALIDATION n=96  failure=19
TEST_OOS   n=76  failure=26
```

Hashes:

```text
TRAIN      f34cc94cb50be5652ede901ba18e9a9c519834b8717be0750906bb51cf708863
VALIDATION 58e7ea4cc88b772c5734bb77c6096aec6545f46bec6aa5fbd281c9d76604b3ad
TEST_OOS   68e6b1e7a1792d93c6fe49ba49fbf113589d54a3c15c5d4f02ba90b5e3d11695
```

Estado del audit local:

```text
status = READY_FOR_TRAINING_REVIEW
source_data_modified = false
features_use_future_outcomes = false
merge_with_tf_outcome_v1_003 = DEFERRED
can_trade = false
```

## Limites

- No se ejecuta trading.
- No se activa MT5.
- No se descargan datos.
- No se fusiona aun con `tf_outcome_v1_003`.
- No se declara PASS cientifico.

## Siguiente accion

Entrenar `failure_risk_v1` sobre esta matriz, con VALIDATION para seleccion y
TEST_OOS reservado para dictamen final.
