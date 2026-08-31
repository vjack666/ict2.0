# SDD — Puente de estado operativo MT5 v1

**Estado:** NORMATIVO PARA LA SIGUIENTE IMPLEMENTACIÓN LOCAL
**Fecha:** 2026-08-31
**Contrato:** `docs/contratos/CONTRATO_MT5_OPERATIONAL_SNAPSHOT_V1.md`
**Padres:** `docs/tesis/SDD_LTF_ENTRY_LAYER.md`,
`docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`

## 1. Misión

Completar la lectura MT5 semanal/diaria sobre las autoridades ya existentes.
El puente ensambla; no inventa semántica y no reemplaza ningún motor.

## 2. Diseño aprobado

```text
data/raw/<symbol>/<symbol>_<tf>.parquet
        ↓ closed-only loader
frames normalizados + provenance
        ↓
MTFNavigator → Context State
        ↓
detectores/relations → canonical feed
        ↓
Lifecycle → Object MarketState/projection_at(T)
        ↓
Wyckoff adapter → evidence snapshot
        ↓
daily_motor → brief OBSERVE_ONLY_NO_ORDER
```

El puente no importa `backtest/`, no crea detectores, no crea otra FSM y no
escribe sobre las entradas. Si una capa no tiene evidencia suficiente, devuelve
`UNKNOWN`, `WAIT_*` o `BLOCKED` con razón explícita.

## 3. Orden de implementación

### M0 — preflight

Confirmar rutas, contratos, consumidores, estado Git y write set. Reusar
`update_mt5_ict.py`, `brief_lunes.py` y `ltf_canonical_feed.py`.

### M1 — contrato de ensamblaje

Definir el objeto serializable del snapshot, nombres no ambiguos para Context
State/Object MarketState, provenance y política de error.

### M2 — adaptador read-only

Implementar el ensamblaje mínimo sobre APIs existentes. No debe cambiar el
estado de entrada ni duplicar la lógica de detección o lifecycle.

### M3 — pruebas causales

Añadir fixtures para vela abierta, TF faltante, objeto futuro, autoridad
cruzada, observación LTF, `projection_at(T)`, FULL/PREFIX y determinismo.

### M4 — brief y evidencia

Integrar solo si el snapshot supera sus gates; producir reporte local con
hashes, commit, timestamps, configuración y `OBSERVE_ONLY_NO_ORDER`.

### M5 — auditoría y cierre

Autoauditar, corregir cualquier fallo, ejecutar suite focal y completa,
actualizar worklog/índice/Graphify y crear commit selectivo sin push.

## 4. Definition of Done

- una única ruta MT5 → snapshot → brief;
- dos `MarketState` existentes claramente separados por responsabilidad;
- cero look-ahead en varios cortes;
- entradas no mutadas;
- provenance mecánica visible;
- tests y compilación PASS;
- ningún backtest, descarga Dukascopy, entrenamiento, orden o push;
- auditoría independiente pendiente antes de publicar.
