# Auditorías ICT 2.0

Esta carpeta contiene el subsistema normativo de auditoría previo al backtest.

## Arranque obligatorio

El primer paso de Hermes es siempre:

```bash
python start_hermes.py
```

Ese comando ejecuta primero `python -m audits.codigo.bootstrap`. Si el estado no alcanza el umbral mínimo, Hermes debe corregir y volver a auditar antes de continuar.

## Orden de ejecución

```text
A0 Data Integrity
A1 Schema / Canonical Data
A2 Point-in-Time / Look-Ahead
A3 Semantic / Contract
A4 Detector / Metamorphic
A5 Cross-Timeframe Alignment
A6 Lineage / Causal
A7 Funnel
A8 Coverage / Regime / Concentration
A9 Selection / Experiment Governance
```

No se ejecuta backtest de performance hasta superar los Gates A0-A9 según el contrato vigente.

## Estructura

- `codigo/` — **única ubicación para código ejecutable de auditorías**.
- `reports/` — reportes derivados; no se versionan reportes grandes salvo decisión explícita.
- `MANIFEST.md` — mapa de componentes y estado de implementación.

Las antiguas rutas `contracts/`, `core/`, `checks/` y `funnel/` quedan fuera de servicio como ubicaciones de código.

## Loop Hermes

```text
AUDIT
 ↓
FINDINGS
 ↓
FIX
 ↓
TEST
 ↓
UPDATE SDD / INDEX / WORKLOG
 ↓
AUDIT AGAIN
 ↓
PASS MEDIANAMENTE BUENO
 ↓
CONTINUE
```

## Reglas

1. Las auditorías son deterministas y point-in-time.
2. Una auditoría nunca relaja una regla para conseguir PASS.
3. Un FAIL debe producir diagnóstico, razón y artefacto reproducible.
4. Cada Gate actualiza `.hermes-index.md`, SDD y worklog.
5. Esta carpeta audita el motor; no contiene lógica de trading ni optimización de performance.
