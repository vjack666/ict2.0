# 2026-09-20 — Corrección del conteo de eventos ICT y preparación para ICT SYSTEM original

**Responsable de esta entrega:** auditoría externa de ChatGPT, con ejecución local sobre la copia recuperada de CLEAN y el ZIP original de EURUSD. **Estado:** inventario de detectores ejecutado; P1/P2/P3/P4=NO CERTIFICADOS; revisión independiente Vigil=PENDIENTE. **Destino de trabajo solicitado por Rubén:** `C:\Users\v_jac\Desktop\ICT SYSTEM` (ORIGINAL); este commit no cambia ni borra ninguna carpeta Windows.

## Por qué fallaba el reporte de Atlas

El antiguo `control_b_real.py` consultaba 30 instantes y recorría D1/H4/H1. Creaba `evt_key=(tf,timestamp_del_poll,trend,bos_dir)` y añadía una fila aun cuando `bos_dir=0`: sus **90 registros son lecturas de contexto (30×3), no 90 eventos ICT únicos**. No enumeraba las detecciones individuales de M15/M5/M1. El control A anterior usaba `EURUSD_M5.csv` (la fuente reciente aprobada es `EURUSD_M5_3m.csv`). Además, ambos controles trataban la columna `time` de apertura como si fuese cierre y mostraban MD5 abreviado sin verificar físicamente SHA256 del manifiesto. Sus reportes anteriores con `resultado=PASS` deben clasificarse `LEGACY_UNVERIFIED`.

## Cambio de código

- `scripts/audit/ict_event_inventory.py`: ejecuta las autoridades existentes BOS/CHOCH/MSS, desplazamiento, FVG y OB por cada TF; utiliza únicamente velas cerradas a T con `bar_close_time=source_open_time+duracion_tf`; confirma SHA256 completo de los seis CSV seleccionados contra `benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json`; usa M5_3m para A/B, M1 no disponible en A y sí en B; identifica ocurrencias mediante **TF, tipo, hora de confirmación y dirección**, no mediante hora de consulta. No publica `bos_real`/outcome, que puede usar el futuro.
- `control_a_real.py` y `control_b_real.py` dejan de publicar un falso PASS y pasan a llamar el inventario del control respectivo. Su comportamiento antiguo permanece en el historial Git. Los nuevos resultados llevan `status=DETECTOR_INVENTORY_ONLY_NOT_P1_PASS` y no se escriben sobre los antiguos JSON de P1.
- `tests/test_ict_event_inventory.py` cubre el error del BOS con dirección cero, las fechas A/B, selección M5 reciente, la vela M1 en formación y rechazo de hashes incorrectos.

## Prueba ejecutada antes de publicar

Con `/mnt/data/EURUSD.zip` original, código recuperado del snapshot CLEAN, Python y dependencias funcionales: `python -m pytest -q tests/test_ict_event_inventory.py` → **4 passed**. Ejecución de A/B sobre los CSV originales del ZIP (6/6 hashes SHA256 correctos), inventario de **ocurrencias de detector** en las 24 h previas: A=154 (D1=1,H4=3,H1=10,M15=43,M5=97, M1 OUT_OF_RANGE); B=582 (D1=0,H4=2,H1=4,M15=23,M5=85,M1=468). Se verificó `last_used_close<=T`, ausencia de IDs duplicados por control y la última M1 de B cerrada a 2026-08-24 20:35 UTC. Código nuevo de `control_b_real.py` redirigió correctamente el inventario B y obtuvo 582 ocurrencias. **No son 154/582 episodios o señales; una misma vela puede producir tipos distintos.** Ventanas de calentamiento finitas y calendario D1/H4 de duración fija: hace falta validación de calendario broker/DST y FULL/PREFIX para certificación causal estricta.

Reproducción desde la raíz (la fuente se pasa explícitamente, no se guarda en GitHub):

```powershell
python -m pytest -q tests/test_ict_event_inventory.py
python control_a_real.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip"
python control_b_real.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip"
```

## Migración futura a ORIGINAL — NO borrar antes de comprobar

Rubén quiere trabajar solo en `C:\Users\v_jac\Desktop\ICT SYSTEM`. Hermes debe respaldar y examinar `git status`, ramas y diferencias de ORIGINAL y CLEAN; copiar selectivamente código, tests, manifiesto y esta bitácora; verificar las dependencias y repetir las pruebas con los CSV originales en ORIGINAL. No copiar a ciegas módulos `engine/sequence.py`, `engine/episodes.py` ni `engine/market_object.py` (existen versiones distintas). No arrastrar toda la PR #15: contiene modelos y datos de otra misión. Mantener sin fusionar las PR #14 y #15. **No borrar CLEAN hasta contar con copia de seguridad verificable, paridad de pruebas y conformidad expresa de Rubén para la eliminación irreversible.**

**Siguiente acción:** integrar el inventario como productor de eventos/objetos con lineage y lifecycle en el harness P1; comparar en ORIGINAL y ejecutar FULL/PREFIX, future injection y Order Reversal en etapas correspondientes; solicitar auditoría independiente. `READY_FOR_GRU=NO`, `CAN_TRADE=NO` para esta misión.

## Validación adicional sobre copia recuperada del ORIGINAL

Antes de entregar la migración, el script y las cuatro pruebas se ejecutaron también contra **310 archivos de código** extraídos del paquete original `ICT_SYSTEM_ORIGINAL_AUDITORIA_CHATGPT_reconstruido.zip`, en un directorio temporal separado (no se modificó el repositorio Windows): **4/4 tests PASS; A=154, B=582 ocurrencias de detector, hashes 6/6**, idénticos a la ejecución sobre el snapshot CLEAN. Esto demuestra funcionalidad del inventario en la copia del ORIGINAL suministrada, **no** certifica la carpeta Windows actual ni el funnel completo.
