# 2026-09-20 — Etapa de integración: inventario de detectores → MarketState (ORIGINAL)

**Objetivo:** aportar un puente de solo lectura desde las ocurrencias del inventario de A/B hacia objetos observables en `MarketState`, sin interpretar 154/582 como setups, secuencias, episodios ni señales. **Repo de destino operativo del usuario:** `C:\Users\v_jac\Desktop\ICT SYSTEM`. Este commit modifica GitHub y una copia de código recuperada en el entorno de auditoría, **no** la carpeta Windows del usuario.

## Causa y corrección

Atlas contaba lecturas de contexto D1/H4/H1 mediante la hora del poll: 30×3=90 aun con `bos_dir=0`. La primera corrección publicó el inventario de 154/582 ocurrencias por detector; aún faltaban dos datos para usar objetos con geometría real: `zone_high` de FVG/OB/desplazamiento y un identificador del evento independiente de la posición local de la ventana. Además, el detector de Order Blocks lleva `creation_time` de la vela fuente (anterior al follow-through): copiar esa marca directamente a `MarketState.ingest` haría visible el OB antes de confirmarse.

Se amplió `scripts/audit/ict_event_inventory.py` para conservar geometría y precio de la fuente de cada ocurrencia sin alterar detectores ni fuentes CSV. `engine/detector_event_bridge.py` crea un objeto con identidad estable `symbol|tf|kind|confirmation_time|direction`, lo ingiere una sola vez, y fija su nacimiento observable **en la confirmación**, incluso para OB. Rechaza `bos_dir=0`, geometría insuficiente, conflicto de identidad y eventos posteriores a T. Se añadió `ObjectType.MSS` para no tergiversar MSS como CHOCH. El puente **no inventa parent_object**, no ejecuta lifecycle ni convierte eventos aislados en secuencias. El estado ACTIVE del objeto puente significa *estado inicial no reprocesado*, no prueba que una zona siga activa a T; el metadato señala `lifecycle_status=NOT_REPLAYED`.

El runner `scripts/audit/ict_event_market_state.py` lee el CSV NUEVO del inventario y deja evidencia JSON con conteos, SHA del inventario, y gates explícitamente `NOT_RUN`. Los CSV de la auditoría anterior carecen de `zone_high`: **deben regenerarse**; el puente rechaza sus FVG/OB en lugar de inventar dimensiones.

## Pruebas realmente ejecutadas, entorno aislado (2026-09-20)

Código ORIGINAL recuperado del ZIP aportado por Rubén, enriquecido con los archivos de esta rama (verificación de hashes Git blob exactos de los seis archivos nuevos/actualizados). `python -m pytest -q tests/test_ict_event_inventory.py tests/test_detector_event_bridge.py tests/test_ict_event_market_state_cli.py tests/test_market_state.py tests/test_historical_event_objects.py` → **21 passed**. No se ejecutó un pipeline completo P1 ni CI Windows aquí.

Con `/mnt/data/EURUSD.zip` real: hashes físicos seleccionados 6/6; control A inventario=154 → MarketObjects visibles a T=154, M1 fuera de rango; B inventario=582 → MarketObjects visibles a T=582; en ambos `parent_object=None`, `lineage_linked_count=0`, `lifecycle_replayed_count=0`, `accepted_episodes_count=null`. El nuevo inventario A corrió ~3.7 s y B ~16.4 s en el entorno de auditoría; no son cotas de CPU Windows. Se probaron en unidades deduplicación por identidad, bloqueo de evento futuro, OB no visible antes de confirmarse, inversión del orden de las filas, geometría inválida y rechazo de CSV antiguo.

**NO SE HA CERTIFICADO** FULL/PREFIX integral de detectores ni de motor, calendario H4/D1 del broker, relaciones causalmente válidas entre eventos, replay real de lifecycle, funnel P1–P4, ni entrenamiento GRU. No se ejecutó trading.

## Comandos para reproducir en ORIGINAL (PowerShell)

Desde `C:\Users\v_jac\Desktop\ICT SYSTEM`:

```powershell
python -m pytest -q tests/test_ict_event_inventory.py tests/test_detector_event_bridge.py tests/test_ict_event_market_state_cli.py tests/test_market_state.py tests/test_historical_event_objects.py
python control_a_real.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip"
python control_b_real.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip"
python scripts/audit/ict_event_market_state.py --inventory reports/audits/experiments/temporal/detector_inventory_A/eventos_detectores_canonicos_controles.csv --control A --output reports/audits/experiments/temporal/DETECTOR_MARKET_STATE_A.json
python scripts/audit/ict_event_market_state.py --inventory reports/audits/experiments/temporal/detector_inventory_B/eventos_detectores_canonicos_controles.csv --control B --output reports/audits/experiments/temporal/DETECTOR_MARKET_STATE_B.json
```

## Siguiente trabajo que no se ha realizado

1. Validar checkpoint ORIGINAL en Windows, rama, status, SHA y seguridad de los cambios locales. No borrar CLEAN antes de demostrar paridad de componentes/artefactos y autorización explícita.
2. Conectar objetos a `build_historical_event_objects` donde exista evidencia geométrica y temporal suficiente (H4→M15), resolver lineage por identidad confirmada **sin emparejar simplemente por proximidad**. Cualquier temporalidad/categoría no soportada debe quedar `UNRESOLVED`.
3. Replay global por barras cerradas con autoridad de cada TF para obtener estados PIT en T. Probar FULL/PREFIX independientes y future injection sobre **detectores y motor**, no solamente sobre el puente.
4. Ejecutar `build_episodes`/funnel con snapshots y relaciones verificadas; reportar candidatos aceptados/rechazados con sus causas. Auditoría Vigil; no promocionar P1 ni entrenar con este puente aislado.

**GitHub:** actualizar este trabajo de la rama `codex/audit-hermes-cert-20260826` sin fusionar la PR #15, que sigue conteniendo modificaciones ajenas. La PR #14 es otra rama y sigue abierta.
