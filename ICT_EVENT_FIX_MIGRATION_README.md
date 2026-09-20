# ICT SYSTEM ORIGINAL — paquete de corrección del sobreconteo (2026-09-20)

Origen: auditoría de código recuperado de CLEAN y datos EURUSD originales. Destino solicitado por Rubén: `C:\Users\v_jac\Desktop\ICT SYSTEM`. Este paquete solo contiene código, tests, bitácora, manifiesto y evidencia de detector; NO contiene datasets ni reemplaza por sí solo un sistema P1 certificado.

## Prueba ya realizada

Con el código recuperado del ORIGINAL (310 archivos fuente) aislado del Windows de Rubén, los CSV del `EURUSD.zip` original y el manifiesto seleccionado: `pytest tests/test_ict_event_inventory.py` **4 passed**, CONTROL A **154 ocurrencias** (M1 fuera de rango) y B **582 ocurrencias** (M1 cerrada hasta 20:35 UTC). El código de CLEAN recuperado produjo exactamente los mismos recuentos. Se validaron hashes SHA256 físicos 6/6. Los informes con `90 eventos` son 30 lecturas por 3 TF con `bos_dir=0`: observaciones de contexto, no 90 eventos nuevos.

## Archivos del paquete

- `scripts/audit/ict_event_inventory.py`: herramienta standalone de inventario **solo de detectores**, importando autoridades existentes del motor.
- `tests/test_ict_event_inventory.py`: cuatro tests focales.
- `control_a_real.py` / `control_b_real.py`: sustitutos **diagnósticos**, dejan de anunciar P1 PASS. Las versiones originales quedan en el historial Git y deben respaldarse antes de reemplazarlas.
- `benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json`: fuente exacta del paquete original, no sustituir su selección M5_3m.
- `.hermes-worklog/2026-09-20_ICT_EVENT_COUNT_AUDIT_AND_ORIGINAL_MIGRATION.md`: causa del error, límites y protocolo.
- `reports/audits/experiments/temporal/ICT_EVENT_INVENTORY_AB_20260920.json` y `...OCCURRENCES_AB_20260920.csv`: evidencia local de A/B, no son episodios.

## Instalación SOLO tras inventario y respaldo

1. En `ICT SYSTEM`, registrar `git status`, rama, HEAD, cambios sin commit, y crear copia externa verificable de ORIGINAL y CLEAN, incluyendo datos no rastreados y secretos por separado (no publicarlos).
2. Revisar rutas existentes y comparar SHA256 y diferencias de cada archivo. Copiar **selectivamente** desde este ZIP los módulos de auditoría, tests, bitácora y manifiesto, sin copiar ciegamente otras partes de CLEAN. Si existían `control_a_real.py` o `control_b_real.py` con trabajo local diferente, respaldar y reconciliar antes de sustituirlos; los wrappers son diagnósticos, NO el harness integral.
3. Instalar dependencias de `engine/` según el entorno de ORIGINAL. Verificar ruta del ZIP de mercado y ejecutar desde la raíz:

```powershell
python -m pytest -q tests/test_ict_event_inventory.py
python control_a_real.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip"
python control_b_real.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip"
```

4. Comprobar 6 SHA correctos, A=154 y B=582 en las ventanas y warm-ups **de esta auditoría**; si difiere, investigar causas (historia, dependencias, versiones), no forzar datos ni relajar tests. Registrar commit selectivo en una rama de trabajo del ORIGINAL y publicar según auditoría/autorización; conservar abiertas sin fusionar PR #14 y #15.
5. Integrar después estas ocurrencias con `MarketState`, `run_sequence_traced`, lifecycle y episodios; ejecutar controles P1 **reales** y P2/P3/P4. La salida del inventario indica `DETECTOR_INVENTORY_ONLY_NOT_P1_PASS`.
6. Solo tras verificar migración, respaldo, original funcionando y aprobación expresa de Rubén para el borrado irreversible, podrá evaluarse eliminar la carpeta CLEAN. El paquete NO incluye ni ejecuta instrucciones de borrado.

GitHub rama fuente de los cambios: `hermes/temporal-windows-validation-20260918`, PR #14, bitácora 2026-09-20. La PR #15 contiene otros archivos y no debe fusionarse/copiase íntegra para esta migración.
