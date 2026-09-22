# Mision 3 — Ventana historica seis-TF + FULL/PREFIX

**Fecha:** 2026-09-21  
**Rama:** `preservation/before-lineage-hierarchical-integration-20260921`  
**Estado:** `PASS_SHADOW_DIAGNOSTIC`  
**No autoriza:** trading, MT5, edge, entrenamiento productivo ni promocion.

## Objetivo

Escalar el conector de Mision 2 desde un solo `decision_time` a una ventana
historica multi-decision_time, verificando que la salida FULL y PREFIX sea
literalmente identica para cada decision.

## Implementacion

Se extendio:

```text
scripts/audit/run_sixtf_marketobject_connector.py
```

Nuevo modo:

```text
window
```

Flujo:

```text
datos locales EURUSD seis-TF
  -> decision_times en ventana
  -> build_sixtf_episodes(FULL)
  -> build_sixtf_episodes(PREFIX truncado en T)
  -> hash causal por T
  -> agregados y gates de ventana
```

## Evidencia real local

Comando:

```text
python scripts/audit/run_sixtf_marketobject_connector.py window ^
  --data-dir data/raw/EURUSD ^
  --start-time 2022-03-31T00:00:00Z ^
  --end-time 2022-03-31T12:00:00Z ^
  --decisions 13 ^
  --step-minutes 60 ^
  --output reports/audits/experiments/mission3/sixtf_window_report.json
```

Resultado:

```text
status=PASS
decision_count=13
pass_count=13
episode_count=13
rejection_count=13
error_count=0
full_prefix_failure_count=0
window_checksum=77b70956af5e1d7036f97633229ade3f6ca05669728d359658698955e82d68df
can_trade=false
edge_claimed=false
diagnostic_only=true
```

Gates:

```text
all_runs_executed=true
full_prefix_all_pass=true
at_least_one_episode=true
at_least_one_rejection=true
all_lineage_valid=true
all_six_tfs_complete=true
```

## Pruebas

Focal:

```text
python -m pytest -q tests/test_sixtf_marketobject_connector.py
5 passed
```

Regresion relacionada:

```text
python -m pytest -q tests/test_sixtf_marketobject_connector.py tests/test_lineage_hierarchy.py tests/test_setup_builder_integration.py tests/test_episodes.py
39 passed
```

## Dictamen

Mision 3 queda en `PASS_SHADOW_DIAGNOSTIC`: la conexion seis-TF soporta una
ventana historica multi-decision_time sin divergencias FULL/PREFIX en la
ventana auditada. Esto no es edge ni backtest economico; solo habilita el
siguiente paso metodologico.

## Siguiente paso

Crear el backtest economico aislado sobre episodios reales aceptados/rechazados:

```text
episodios ventana
  -> reglas economicas aisladas
  -> costes/spread/slippage/comision
  -> PnL diagnostico
  -> dataset IA shadow solo despues de gates
```

Mantener `can_trade=false`.
