# 2026-09-20 — Auditoría del conteo ICT y preparación de migración a ICT SYSTEM original

**Estado:** detector_inventory=EXECUTED; P1/P2/P3/P4=NOT_CERTIFIED; auditoría independiente=PENDING. **Repositorio de origen:** ICT SYSTEM CLEAN, rama PR #14 `hermes/temporal-windows-validation-20260918`. **Destino pedido por Rubén:** `C:\Users\v_jac\Desktop\ICT SYSTEM` (repositorio ORIGINAL). Este documento NO acredita que se haya migrado o eliminado ningún directorio Windows.

## Defecto observado y por qué fallaba

`control_b_real.py` antiguo generaba 30 instantes y añadía una fila por cada lectura D1/H4/H1 usando `evt_key=(tf, timestamp_del_poll, trend, bos_dir)`. Con `bos_dir=0` se podían reportar **90 supuestos eventos** (30×3) que en realidad son 90 observaciones repetidas del estado del contexto; no son 90 BOS, ni 90 MarketObjects o episodios. El script no enumeraba las ocurrencias individuales de los detectores de M15/M5/M1. Los controles legados A/B tampoco constituyen por sí mismos una certificación del funnel canónico: `control_a_real.py` seleccionaba `EURUSD_M5.csv` en vez de `EURUSD_M5_3m.csv`, la verificación impresa usaba MD5 en lugar de contrastar SHA256 físico con el manifiesto, y tratar `time` (apertura CSV) como vela cerrada permite incorporar velas aún en formación. Los JSON antiguos con `resultado=PASS` deben marcarse `LEGACY_UNVERIFIED` hasta que se reproduzca el harness integral.

## Actualización implementada

`control_a_real.py` y `control_b_real.py` se sustituyeron por puntos de entrada explícitamente **diagnósticos** que llaman al inventario con `--control A`/`--control B`; **ya no generan falsos JSON `P1 PASS`**. Sus implementaciones históricas permanecen disponibles en el historial Git. Se debe construir otro runner P1 completo para contexto, lifecycle, lineage y episodios. `scripts/audit/ict_event_inventory.py` ejecuta las autoridades existentes `engine.bos.structure.detect_market_structure`, `detectors.displacement.detect_displacement`, `engine.detectors.fvg.detect_fvg` y `engine.detectors.ob.detect_order_blocks` sobre los CSV originales del paquete EURUSD. Verifica **SHA256 completo de los seis CSV** contra `benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json`; selecciona `EURUSD_M5_3m.csv` para ambos controles; filtra por `bar_close_time = source_open_time + TF <= decision_time` antes de invocar los detectores; M1 queda fuera de rango en A; el identificador de ocurrencia de detector usa temporalidad, familia, hora de confirmación y dirección, **nunca** el momento en que el replay vuelve a consultar el mismo estado. Un BOS con dirección cero no es una nueva ocurrencia. Se omite `bos_real`/outcome porque puede ser un etiquetado futuro, no atributo causal disponible al confirmar el BOS.

La herramienta es un **inventario de salidas de detectores**, no integra por sí sola `MarketState`, lifecycle, `run_sequence_traced`, funnel ni episodios aceptados, y no sustituye los controles P1 completos, FULL/PREFIX independientes ni la certificación de Vigil. Una ausencia de eventos puede ser resultado válido; no se fabrican eventos. El total de tipos de detectores puede contener familias distintas confirmadas sobre la misma vela; no representa setups u operaciones independientes.

## Ejecución reproducida con los CSV originales (2026-09-20)

Comando desde la raíz de código con Python y dependencias del motor:

```powershell
python scripts/audit/ict_event_inventory.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip" --clean-code . --manifest benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json --control AB --out reports/audits/experiments/temporal/detector_inventory
python -m pytest -q tests/test_ict_event_inventory.py
```

En la ejecución de auditoría externa, con fuente `/mnt/data/EURUSD.zip` y snapshot de código CLEAN recuperado en `/mnt/data/ict_clean_recovered`: **4/4 pruebas unitarias PASS**, hashes SHA256 **6/6**, inventario de ocurrencias confirmadas en las 24 h previas: **A=154** (D1=1,H4=3,H1=10,M15=43,M5=97; M1 fuera de rango), **B=582** (D1=0,H4=2,H1=4,M15=23,M5=85,M1=468). `B` incluye M1 con última vela abierta a 20:34 y cerrada a las 20:35 UTC; `A` incluye M5_3m con última vela cerrada a las 18:20 UTC. Se generan `ICT_EVENT_INVENTORY_AB_20260920.json` y `ICT_EVENT_OCCURRENCES_AB_20260920.csv` con timestamps e identidad de ocurrencia; no hay señal ni recomendación de trading. Ventanas de calentamiento D1=600d, H4=120d, H1=45d, M15=21d y M5/M1=12d; los conteos pueden variar con otra historia inicial. Cierres D1/H4 por duración fija requieren verificar calendario del proveedor y DST antes de certificar P1.

## Migración solicitada: sin pérdida de trabajo

Rubén quiere dejar de trabajar en la carpeta CLEAN y continuar solo en `C:\Users\v_jac\Desktop\ICT SYSTEM`. Hermes debe **respaldar ambos repositorios y datos, registrar `git status`, ramas PR #14/#15 y cambios sin commit, verificar diferencias y trasladar selectivamente al ORIGINAL los scripts de auditoría, tests, bitácora, manifiesto y dependencias pertinentes**. No sobrescribir los módulos distintos de `engine/sequence.py`, `engine/episodes.py` o `engine/market_object.py`; no arrastrar la PR #15 completa (contiene modelos/resultados de otra misión). No hacer `reset --hard`, `clean`, merge de las PR ni borrar CLEAN en una migración no auditada. Después de instalar y probar en ORIGINAL con los CSV originales, conservar respaldo comprobado y solicitar confirmación explícita a Rubén antes de cualquier borrado irreversible de CLEAN. `TRAINING_READY=NO; CAN_TRADE=NO` para esta misión.

**Siguiente acción:** ejecución de inventario en ORIGINAL y comparación de outputs por SHA256; integración del productor/lineage y validación P1 independiente. Si el inventario no se puede reproducir en ORIGINAL, marcar `MIGRATION_BLOCKED` y NO borrar CLEAN.
