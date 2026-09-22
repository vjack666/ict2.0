# Mision 2 — Conector real seis-TF MarketObject -> Episodes

**Fecha:** 2026-09-21  
**Rama:** `preservation/before-lineage-hierarchical-integration-20260921`  
**Estado:** `PASS_SHADOW_DIAGNOSTIC`  
**No autoriza:** trading, MT5, edge, entrenamiento productivo ni promocion.

## Resultado

Se implemento el puente que faltaba entre la fabrica seis-TF existente y el
motor canonico:

```text
MTFNavigator / contexto seis-TF
  -> MarketObject seis-TF
  -> HierarchicalLineage(require_all_six_tfs=True)
  -> build_setups_at()
  -> build_episodes()
```

## Archivos

- `engine/sixtf_marketobject_connector.py`
- `tests/test_sixtf_marketobject_connector.py`
- `scripts/audit/run_sixtf_marketobject_connector.py`
- `reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json`

## Evidencia

Pruebas focales:

```text
python -m pytest -q tests/test_sixtf_marketobject_connector.py
4 passed
```

Regresion relacionada:

```text
python -m pytest -q tests/test_sixtf_marketobject_connector.py tests/test_lineage_hierarchy.py tests/test_setup_builder_integration.py tests/test_episodes.py
38 passed
```

Reporte con fuente local parquet:

```text
python scripts/audit/run_sixtf_marketobject_connector.py ^
  --data-dir data/raw/EURUSD ^
  --decision-time 2022-03-31T12:00:00Z ^
  --output reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json
```

Resultado:

```text
status=PASS
lineage.status=LINEAGE_VALID
six_tfs_complete=true
setup_count=2
episode_count=1
rejection_count=1
accepted_episode.component_tfs=D1/H4/M15/M5/M1
lineage.provenance_by_tf=D1/H4/H1/M15/M5/M1
can_trade=false
edge_claimed=false
diagnostic_only=true
```

## Nota tecnica

El conector no crea una fabrica paralela ni reemplaza el productor historico
H4/M15. Usa el contexto seis-TF existente como procedencia y publica una cadena
de objetos compatible con los contratos actuales de `setup_builder` y
`episodes`.

Para que ambos validadores pasen:

- H4 queda como POI raiz local del funnel.
- D1 queda como contexto relacionado.
- H1/M15/M5/M1 quedan en la procedencia global de lineage.
- M1 se publica como `ObjectType.DISPLACEMENT` con `Role.EXECUTION`, compatible
  con Episodes v1.
- Las velas se seleccionan causalmente de abajo hacia arriba: cada padre cierra
  antes que su hijo.

## Siguiente paso

Escalar de un `decision_time` auditado a una ventana historica completa:

```text
many decision_times
  -> episodios aceptados/rechazados reales
  -> FULL/PREFIX de ventana
  -> backtest economico aislado
  -> dataset IA shadow
```

Mantener `can_trade=false`.
